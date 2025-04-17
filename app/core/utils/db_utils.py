from typing import Dict
from fastapi import Depends, logger, HTTPException, status
from sqlalchemy import and_, func, or_, tuple_,  update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models import STATUS, Base, FinalStatus, FinalValidatedStatus, OribisMatchStatus
from app.api import deps
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import aliased
from datetime import datetime, timedelta
async def get_dynamic_ens_data(
    table_name: str, 
    required_columns: list, 
    ens_id: str = "", 
    session_id: str = "", 
    session=None, 
    **kwargs
):
    try:
        extra_filters = kwargs.get('extra_filters', {})

        # Validate if table exists
        table_class = Base.metadata.tables.get(table_name)
        if table_class is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Table '{table_name}' does not exist in the database schema."
            )

        # Prepare columns to select
        columns_to_select = [getattr(table_class.c, column) for column in required_columns]
        query = select(*columns_to_select)

        # Apply filters
        if ens_id:
            query = query.where(table_class.c.ens_id == str(ens_id)).distinct()
        if session_id:
            query = query.where(table_class.c.session_id == str(session_id))
        query = query.order_by(table_class.c.update_time.desc(), table_class.c.id.desc())
        # Execute query to check if session_id or ens_id exists
        exists_query = select(func.count()).select_from(table_class)

        if ens_id:
            exists_query = exists_query.where(table_class.c.ens_id == str(ens_id))
        if session_id:
            exists_query = exists_query.where(table_class.c.session_id == str(session_id))

        exists_result = await session.execute(exists_query)
        record_count = exists_result.scalar()

        if record_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No data found for the given session_id or ens_id."
            )

        # Apply validation status filter
        if extra_filters:
            final_validation_status = extra_filters.get("final_validation_status", "").strip().lower()
            if final_validation_status:
                if final_validation_status == 'review':
                    query = query.where(table_class.c.final_validation_status == FinalValidatedStatus.REVIEW)
                elif final_validation_status == 'auto_reject':
                    query = query.where(table_class.c.final_validation_status == FinalValidatedStatus.AUTO_REJECT)
                elif final_validation_status == 'auto_accept':
                    query = query.where(table_class.c.final_validation_status == FinalValidatedStatus.AUTO_ACCEPT)
                                
            # add additional filter[optional] where screening_ana_status != 'NOT_STARTED'
            screening_analysis_status = extra_filters.get("screening_analysis_status", "").strip().lower()
            if screening_analysis_status:
                if screening_analysis_status == 'active':
                    query = query.where(table_class.c.screening_analysis_status != STATUS.NOT_STARTED)
                elif screening_analysis_status == 'not_started':
                    query = query.where(table_class.c.screening_analysis_status == STATUS.NOT_STARTED)

            # Validate pagination inputs
            offset = extra_filters.get("offset", 0)
            limit = extra_filters.get("limit", 10000)

            if not isinstance(offset, int) or offset < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="'offset' must be a non-negative integer."
                )
            if not isinstance(limit, int) or limit <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="'limit' must be a positive integer."
                )

            # Count total rows before pagination
            total_count_query = select(func.count()).select_from(table_class)
            if query._where_criteria:
                total_count_query = total_count_query.filter(*query._where_criteria)

            total_count_result = await session.execute(total_count_query)
            total_count = total_count_result.scalar()

            # Apply offset and limit
            query = query.offset(offset).limit(limit)

        print("_______query____", query , "\n offset", offset, "\n limit", limit )
        # Execute query
        result = await session.execute(query)
        columns = result.keys()
        rows = result.all()

        formatted_res = [dict(zip(columns, row)) for row in rows]
        total_count = len(formatted_res) if not total_count else total_count

        print("formatted_res______", formatted_res)
        return formatted_res, total_count

    except HTTPException as http_err:
        raise http_err  # Pass FastAPI exceptions as they are

    except SQLAlchemyError as sa_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(sa_err)}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

async def update_dynamic_ens_data(
    table_name: str,
    kpi_data: dict,
    ens_id: str,
    session: AsyncSession = Depends(deps.get_session)
):
    """
    Update the specified table dynamically with the provided kpi_data based on ens_id.

    :param session: AsyncSession = Depends(deps.get_session) - The database session.
    :param table_name: str - The name of the table to update.
    :param kpi_data: dict - The dictionary of KPI data to update.
    :param ens_id: str - The ID to filter the record that needs to be updated.
    :return: dict - The result of the update operation.
    """
    try:
        # Get the table class dynamically
        table_class = Base.metadata.tables.get(table_name)
        if table_class is None:
            raise ValueError(f"Table '{table_name}' does not exist in the database schema.")
        
        # Prepare the update values
        update_values = {key: value for key, value in kpi_data.items() if value is not None}
        
        # Build the update query
        query = update(table_class).where(table_class.c.ens_id == str(ens_id)).values(update_values)
        
        # Execute the query
        result = await session.execute(query)
        
        # Commit the transaction
        await session.commit()
        
        # Return success response
        return {"status": "success", "message": "Data updated successfully."}

    except ValueError as ve:
        # Handle the case where the table does not exist
        print(f"Error: {ve}")
        return {"error": str(ve), "status": "failure"}
    
    except SQLAlchemyError as sa_err:
        # Handle SQLAlchemy-specific errors
        print(f"Database error: {sa_err}")
        return {"error": "Database error", "status": "failure"}
    
    except Exception as e:
        # Catch any other exceptions
        print(f"An unexpected error occurred: {e}")
        return {"error": "An unexpected error occurred", "status": "failure"}

async def insert_dynamic_ens_data(
    table_name: str,
    kpi_data: list,
    ens_id: str,
    session_id: str,
    session: AsyncSession = Depends(deps.get_session)
):
    try:
        # Get the table class dynamically
        table_class = Base.metadata.tables.get(table_name)
        if table_class is None:
            raise ValueError(f"Table '{table_name}' does not exist in the database schema.")
        
        # Add `ens_id` and `session_id` to each row in `kpi_data`
        rows_to_insert = [
            {**row, "ens_id": ens_id, "session_id": session_id}
            for row in kpi_data
        ]
        
        # Build the insert query
        query = insert(table_class).values(rows_to_insert)
        
        # Execute the query
        await session.execute(query)
        
        # Commit the transaction
        await session.commit()
        
        # Return success response
        return {"status": "success", "message": f"Inserted {len(rows_to_insert)} rows successfully."}

    except ValueError as ve:
        # Handle the case where the table does not exist
        print(f"Error: {ve}")
        return {"error": str(ve), "status": "failure"}
    
    except SQLAlchemyError as sa_err:
        # Handle SQLAlchemy-specific errors
        print(f"Database error: {sa_err}")
        return {"error": "Database error", "status": "failure"}
    
    except Exception as e:
        # Catch any other exceptions
        print(f"An unexpected error occurred: {e}")
        return {"error": "An unexpected error occurred", "status": "failure"}
    
async def insert_dynamic_data(
    table_name: str,
    data: list,
    session: AsyncSession = Depends(deps.get_session)
):
    """
    Insert data dynamically into the specified table without additional constraints.
    
    Args:
        table_name (str): Name of the table where data will be inserted.
        kpi_data (list): List of dictionaries containing the data to insert.
        session (AsyncSession): Async database session.
    
    Returns:
        dict: A dictionary with the status and message of the operation.
    """
    try:
        # Get the table class dynamically from metadata
        table_class = Base.metadata.tables.get(table_name)
        if table_class is None:
            raise ValueError(f"Table '{table_name}' does not exist in the database schema.")
        # Get valid column names from the table schema
        valid_columns = set(table_class.columns.keys())

        # Filter data: Keep only valid columns (ignore any extra columns)
        cleaned_data = [
            {key: value for key, value in row.items() if key in valid_columns}
            for row in data
        ]

        # If no valid data remains after filtering, return an error
        if not cleaned_data:
            return {"status": "failure", "message": "No valid data left after filtering extra columns."}

        # Insert filtered data into the table
        query = insert(table_class).values(cleaned_data)
        print(f"query:  {query}")
        # Execute the insert query
        result = await session.execute(query)  # `result` stores the execution details
        print(f"query:  {result.rowcount}")
        # Commit the transaction
        await session.commit()

        # Get the number of rows inserted
        rows_inserted = result.rowcount
        print(f"{rows_inserted} row(s) were inserted into the '{table_name}' table.")
        
        # Return success response
        return {"status": "success", "message": f"Inserted {rows_inserted} rows successfully.", "rows_inserted": rows_inserted}

    except ValueError as ve:
        # Handle cases where the table does not exist
        print(f"Error: {ve}")
        return {"error": str(ve), "status": "failure"}
    
    except SQLAlchemyError as sa_err:
        # Handle SQLAlchemy-specific errors
        print(f"Database error: {sa_err}")
        return {"error": "Database error", "status": "failure"}
    
    except Exception as e:
        # Catch any unexpected errors
        print(f"An unexpected error occurred: {e}")
        return {"error": "An unexpected error occurred", "status": "failure"}
    
async def upsert_session_screening_status(
    columns_data: list,
    session_id: str,
    session: AsyncSession = Depends(deps.get_session)
):
    try:
        # Get the table class dynamically
        table_class = Base.metadata.tables.get("session_screening_status")
        if table_class is None:
            raise ValueError(f"Table 'session_screening_status' does not exist in the database schema.")

        # Deduplicate the rows based on session_id
        unique_records = {}
        for record in columns_data:
            record["session_id"] = session_id
            # Use session_id as the key to deduplicate rows
            unique_records[record["session_id"]] = record

        # Convert the dictionary back to a list
        deduplicated_columns_data = list(unique_records.values())

        # Extract column names dynamically
        columns = list(deduplicated_columns_data[0].keys())

        # Prepare bulk insert statement using PostgreSQL ON CONFLICT
        stmt = insert(table_class).values(deduplicated_columns_data)

        # Modify ON CONFLICT to use session_id and update the non-unique fields
        stmt = stmt.on_conflict_do_update(
            index_elements=["session_id"],  # Index on session_id, no unique constraint
            set_={col: stmt.excluded[col] for col in columns if col != "session_id"}
        ).returning(table_class)

        # Execute bulk upsert
        result = await session.execute(stmt)
        await session.commit()

        # Fetch the inserted/updated rows
        return {"message": "Upsert completed", "data": result.fetchall()}

    except ValueError as ve:
        # Handle the case where the table does not exist
        print(f"Error: {ve}")
        return {"error": str(ve), "status": "failure"}
    
    except SQLAlchemyError as sa_err:
        # Handle SQLAlchemy-specific errors
        print(f"Database error: {sa_err}")
        return {"error": "Database error", "status": "failure"}
    
    except Exception as e:
        # Catch any other exceptions
        print(f"An unexpected error occurred: {e}")
        return {"error": "An unexpected error occurred", "status": "failure"}
async def update_supplier_master_data(session, session_id) -> Dict:
    try:
        # Fetch table metadata dynamically
        upload_supplier_master_table = Base.metadata.tables.get("upload_supplier_master_data")
        supplier_master_table = Base.metadata.tables.get("supplier_master_data")

        if upload_supplier_master_table is None or supplier_master_table is None:
            raise HTTPException(
                status_code=404,
                detail="Table 'upload_supplier_master_data' or 'supplier_master_data' does not exist in the database schema."
            )

        required_columns = [
            "name", "name_international", "address", "postcode", "city", "country",
            "phone_or_fax", "email_or_website", "national_id", "state", "ens_id", 
            "session_id", "bvd_id", "validation_status", "final_status"
        ]
        columns_to_select = [
            getattr(upload_supplier_master_table.c, column) for column in required_columns
        ]

        query = select(*columns_to_select).where(
            and_(
                or_(
                    upload_supplier_master_table.c.final_status == FinalStatus.ACCEPTED
                ),
                upload_supplier_master_table.c.session_id == session_id,
                upload_supplier_master_table.c.bvd_id.isnot(None)  # Ensure bvd_id is not NULL
            )
        )

        result = await session.execute(query)
        columns = result.keys()

        # Fetch all rows from the result
        rows = result.fetchall()

        # If no valid records are found, return success response and exit early
        if not rows:
            return {
                "status": "success",
                "message": f"No valid records found for session_id: {session_id}. No updates were performed."
            }

        # Prepare rows for insertion
        rows_to_insert = [dict(zip(columns, row)) for row in rows]

        # Insert or update the rows into the supplier_master_table
        query2 = insert(supplier_master_table).values(rows_to_insert)
        query2 = query2.on_conflict_do_update(
            index_elements=["ens_id", "session_id"],  # Unique constraint columns
            set_={col: query2.excluded[col] for col in columns if col not in ["ens_id", "session_id"]}
        ).returning(*supplier_master_table.c)  # Return inserted/updated rows

        result = await session.execute(query2)
        inserted_or_updated_rows = result.fetchall()

        # If no rows were inserted or updated, return a success message instead of an error
        if not inserted_or_updated_rows:
            return {
                "status": "success",
                "message": "No changes were made as no new data was available for insertion or update."
            }

        # Commit the transaction
        await session.commit()

        # Return success response
        return {
            "status": "success",
            "message": f"Inserted or updated {len(inserted_or_updated_rows)} rows successfully."
        }

    except HTTPException as http_err:
        raise http_err  # Re-raise known HTTP errors

    except SQLAlchemyError as db_err:
        # Handle database-specific errors
        raise HTTPException(
            status_code=500,
            detail=f"Database error occurred: {str(db_err)}"
        )

    except Exception as error:
        # Handle unexpected errors
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(error)}"
        )

async def validate_user_request(current_user, session: AsyncSession = Depends(deps.get_session)):
    # Get the tables from metadata
    supplier_screening_table = Base.metadata.tables.get("session_screening_status")
    upload_supplier_data = Base.metadata.tables.get("upload_supplier_master_data")
    user_table = Base.metadata.tables.get("users_table")
    if supplier_screening_table is None or upload_supplier_data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more required tables do not exist in the database schema."
        )

    # Alias for readability (optional)
    s = aliased(supplier_screening_table)
    u = aliased(upload_supplier_data)
    ut = aliased(user_table)
    # Extract user group & user ID correctly
    user_group, user_id = current_user[0], current_user[1]

    # Build the async query
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)

    query = select(func.count(func.distinct(tuple_(s.c.session_id, s.c.overall_status, ut.c.user_group)))).select_from(
        s.join(u, s.c.session_id == u.c.session_id).join(ut, u.c.user_id == ut.c.user_id)
    ).where(
        s.c.overall_status == STATUS.IN_PROGRESS.value,
        u.c.user_id == user_id,
        ut.c.user_group == user_group, 
        s.c.create_time >= one_hour_ago
    )
        
    result = await session.execute(query)
    print("result.scalar()", result)
    count = result.scalar_one_or_none()  # Returns None if no rows found
    print("Query Result:", count)
    return count
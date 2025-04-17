from typing import Dict

from fastapi import  HTTPException, status
from app.core.utils.db_utils import *
import pandas as pd
import uuid
import io
from app.models import *
import pycountry

def validate_and_update_data(data, user_id, session_id):
    """
    Validate the data for required fields, generate unique ens_id for each row, 
    and update each row with a session_id. Add 'upload_' prefix to every key.
    
    :param data: List of dictionaries representing rows of data.
    :param session_id: A session identifier to update in each row.
    :raises ValueError: If any row is missing required fields.
    """
    prefix = "uploaded_"

    for index, row in enumerate(data, start=1):
        # Add prefix to all keys
        prefixed_row = {
    f"uploaded_{key}": str(value) for key, value in row.items()
} | {
    f"unmodified_{key}": str(value) for key, value in row.items()
}
        prefixed_row['unmodified_country'] = prefixed_row['unmodified_country_copy']
        # prefixed_row.pop("uploaded_country_copy", None)
        # prefixed_row.pop("unmodified_country_copy", None)
        # Validate required fields with prefixed keys
        missing_fields = []
        if not prefixed_row.get(f"{prefix}name"):
            missing_fields.append(f"name")
        if not prefixed_row.get(f"{prefix}country"):
            missing_fields.append(f"country")
        if not prefixed_row.get(f"{prefix}national_id"):
            missing_fields.append(f"national_id")
        
        # If there are missing fields, raise an error with row number and the missing fields
        if missing_fields:
            raise ValueError(f"Name, Country, and National ID are mandatory. Please make sure your Excel file contains values in all three columns")
        
        # Generate a unique UUID for 'ens_id' and add 'session_id' to the row
        prefixed_row[f"ens_id"] = str(uuid.uuid4())
        prefixed_row[f"session_id"] = session_id
        prefixed_row[f"user_id"] = user_id
        # Update the data with the new prefixed row
        data[index - 1] = prefixed_row

    print("All rows are valid and updated with prefixed keys, ens_id, and session_id.")
    print("data_validate_and_update_data", data)
    
    return data

country_cache = {}
def get_country_code_optimized(country_name):
    if pd.isna(country_name):
        return country_name
    if country_name in country_cache:
        return country_cache[country_name]
    country = pycountry.countries.get(name=country_name)
    country_cache[country_name] = country.alpha_2 if country else country_name  # Keep original if not found
    return country_cache[country_name]

async def process_excel_file(file_contents, current_user, session) -> Dict:
    try:
        contents = await file_contents.read()
        excel_file = io.BytesIO(contents)
        df = pd.read_excel(excel_file)
        df = df.where(pd.notnull(df), "")  
        # Check if the row count exceeds 100
        allowed_rows = 100
        if len(df) > allowed_rows:
            raise ValueError(f"Only {allowed_rows} rows are allowed. Please upload a valid file.")
        df['country_copy'] = df['country']    
        df['country'] = df['country'].apply(get_country_code_optimized)

        sheet_data = df.to_dict(orient="records")
        session_id = str(uuid.uuid4())

        validate_and_update_data(sheet_data, current_user[1], session_id)

        is_inserted = await insert_dynamic_data("upload_supplier_master_data", sheet_data, session)

        res = {
            "rows_inserted": is_inserted.get('rows_inserted', 0),
            "session_id": session_id
        }

        data = [{
            "overall_status": STATUS.IN_PROGRESS,
            "list_upload_status": STATUS.COMPLETED,
            "supplier_name_validation_status": STATUS.NOT_STARTED,
            "screening_analysis_status": STATUS.NOT_STARTED
        }]

        try:
            # Call the function to update session screening status
            response = await upsert_session_screening_status(data, session_id, session)
            if response.get("message") == "Upsert completed":
                res["session_screening_status"] = "Updated"
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error updating session screening status: {str(error)}"
            )

        return res

    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format: {str(ve)}"
        )

    except HTTPException as http_err:
        raise http_err  # Re-raise FastAPI HTTP exceptions

    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing the Excel file: {str(error)}"
        )

async def get_session_supplier(sess_id, page_no, rows_per_page, final_validation_status, session) -> Dict:
    try:
        if not sess_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session ID is required.")

        offset = (page_no-1) * rows_per_page if page_no else 0
        limit = rows_per_page if rows_per_page else 10000
        extra_filters = {"offset": offset, "limit": limit, "final_validation_status": final_validation_status}

        select_column = ["id", "uploaded_name", "uploaded_name_international", "uploaded_address", "uploaded_postcode", 
                         "uploaded_city", "uploaded_country", "uploaded_phone_or_fax", "uploaded_email_or_website", 
                         "uploaded_national_id", "uploaded_state", "uploaded_address_type", "ens_id", "session_id", 
                         "bvd_id", "validation_status", "suggested_name", "suggested_name_international", 
                         "suggested_address", "suggested_postcode", "suggested_city", "suggested_country", 
                         "suggested_phone_or_fax", "suggested_email_or_website", "suggested_national_id", 
                         "suggested_state", "suggested_address_type", "orbis_matched_status", "final_status", "final_validation_status", "matched_percentage", "duplicate_in_session"]

        session_supplier_data = await get_dynamic_ens_data(
            table_name="upload_supplier_master_data", 
            required_columns=select_column, 
            ens_id="", 
            session_id=sess_id, 
            session=session, 
            extra_filters=extra_filters
        )

        if not session_supplier_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No data found for the given session ID.")

        # table_class = Base.metadata.tables.get("upload_supplier_master_data")
        # if table_class is None:
        #     raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database table not found.")

        # not_validated_query = select(func.count()).select_from(table_class).where(
        #     table_class.c.session_id == sess_id,
        #     table_class.c.validation_status == ValidationStatus.NOT_VALIDATED
        # )
        # not_validated_result = await session.execute(not_validated_query)
        # not_validated_count = not_validated_result.scalar()

        return {
            "total_data": session_supplier_data[1], 
            # "not_validated_count": not_validated_count, 
            "data": session_supplier_data[0], 
            "session_id": sess_id
        }

    except HTTPException as http_err:
        raise http_err  # FastAPI HTTP exceptions are raised directly

    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error retrieving session supplier data: {str(error)}"
        )
async def update_suggestions_bulk(payload, session) -> Dict:
    try:
        print("update_suggestions_bulk",type(payload))
        # Validate input payload
        if not payload.session_id:
            raise HTTPException(
                status_code=400, 
                detail="Missing required field: session_id"
            )

        # Get the table class dynamically
        table_class = Base.metadata.tables.get("upload_supplier_master_data")
        if table_class is None:
            raise HTTPException(
                status_code=404, 
                detail="Table 'upload_supplier_master_data' does not exist in the database schema."
            )

        # Step 1: Automatically accept all MATCH statuses
        accept_match_query = (
            update(table_class)
            .where(table_class.c.session_id == payload.session_id)
            .where(table_class.c.final_validation_status == FinalValidatedStatus.AUTO_ACCEPT)
            .values(final_status=FinalStatus.ACCEPTED)
        )
        accepted_rows = await session.execute(accept_match_query)
        print("Accepted Rows with MATCH status:", accepted_rows.rowcount)

        reject_match_query = (
            update(table_class)
            .where(table_class.c.session_id == payload.session_id)
            .where(table_class.c.final_validation_status == FinalValidatedStatus.AUTO_REJECT)
            .values(final_status=FinalStatus.REJECTED)
        )
        rejected_rows = await session.execute(reject_match_query)
        print("Accepted Rows with MATCH status:", rejected_rows.rowcount)

        # Step 2: Reject all others unless explicitly accepted in the payload
        final_response = (
            FinalStatus.ACCEPTED 
            if payload.status.replace(" ", "").strip().lower() in ['accept', 'accepted'] 
            else FinalStatus.REJECTED
        )
    
        reject_or_accept_others_query = (
            update(table_class)
            .where(table_class.c.session_id == payload.session_id)
            .where(table_class.c.final_validation_status == FinalValidatedStatus.REVIEW) 
            .values(
                name=table_class.c.suggested_name,
                name_international=table_class.c.suggested_name_international,
                address=table_class.c.suggested_address,
                postcode=table_class.c.suggested_postcode,
                city=table_class.c.suggested_city,
                country=table_class.c.suggested_country,
                phone_or_fax=table_class.c.suggested_phone_or_fax,
                email_or_website=table_class.c.suggested_email_or_website,
                national_id=table_class.c.suggested_national_id,
                state=table_class.c.suggested_state,
                address_type=table_class.c.suggested_address_type,
                final_status=final_response
            )
        )

        result = await session.execute(reject_or_accept_others_query)
        print("Updated Rows (Non-MATCH statuses):", result.rowcount)


        if (accepted_rows.rowcount + result.rowcount):
            # Step 3: Call update_supplier_master_data to process changes
            response_supplier_master_data = await update_supplier_master_data(session, payload.session_id)
        
        return {
            "status": "success",
            "message": f"Updated {accepted_rows.rowcount + rejected_rows.rowcount + result.rowcount} rows successfully.",
            "accepted_count": accepted_rows.rowcount,
            "rejected_count": rejected_rows.rowcount,
            "review_count": result.rowcount
        }

    except HTTPException as http_err:
        raise http_err  # Re-raise known HTTP exceptions

    except SQLAlchemyError as db_err:
        # Handle database errors
        raise HTTPException(
            status_code=500, 
            detail=f"Database error: {str(db_err)}"
        )

    except Exception as error:
        # Handle unexpected errors
        raise HTTPException(
            status_code=500, 
            detail=f"Unexpected error: {str(error)}"
        )

async def update_suggestions_single(payload, session_id, session: AsyncSession) -> Dict:
    """
    Update suggestions for a single session_id.

    :param payload: List of suggestion objects containing ens_id and status.
    :param session_id: Unique identifier for the session.
    :param session: AsyncSession instance for database operations.
    :return: Dictionary containing status, message, and lists of accepted and rejected ens_ids.
    """
    try:
        # Step 1: Get the table class dynamically
        table_class = Base.metadata.tables.get("upload_supplier_master_data")
        if table_class is None:
            raise HTTPException(
                status_code=500,
                detail="Table 'upload_supplier_master_data' does not exist in the database schema."
            )

        if not payload:
            raise HTTPException(
                status_code=400, 
                detail="Payload is empty. Please provide valid data."
            )

        if not session_id:
            raise HTTPException(
                status_code=404, 
                detail="No session_id provided."
            )

        print("Payload:", payload)

        # Step 2: Fetch all rows for the session_id
        query = select(table_class).where(table_class.c.session_id == session_id)
        result = await session.execute(query)
        rows = result.fetchall()

        if not rows:
            raise HTTPException(
                status_code=404, 
                detail=f"No records found for session_id: {session_id}"
            )

        accept_match_query = (
            update(table_class)
            .where(table_class.c.session_id == session_id)
            .where(table_class.c.final_validation_status == FinalValidatedStatus.AUTO_ACCEPT)
            .values(final_status=FinalStatus.ACCEPTED)
        )
        accepted_rows = await session.execute(accept_match_query)
        print("Accepted Rows with MATCH status:", accepted_rows.rowcount)

        reject_match_query = (
            update(table_class)
            .where(table_class.c.session_id == session_id)
            .where(table_class.c.final_validation_status == FinalValidatedStatus.AUTO_REJECT)
            .values(final_status=FinalStatus.REJECTED)
        )
        rejected_rows = await session.execute(reject_match_query)
        print("Accepted Rows with MATCH status:", rejected_rows.rowcount)
        # Step 3: Fetch accepted ens_ids from DB
        accepted_rows_query = (
            select(table_class.c.ens_id)
            .where(table_class.c.session_id == session_id)
            .where(table_class.c.final_validation_status == FinalValidatedStatus.AUTO_ACCEPT)
        )
        result_rows_query = await session.execute(accepted_rows_query)
        ac_ens_ids = result_rows_query.fetchall()
        accepted_ens_ids = list({row[0] for row in ac_ens_ids})  # Unique ens_ids

        print("Accepted ens_ids from DB:", accepted_ens_ids)

        # Step 4: Convert to list of dictionaries for further processing
        column_names = result.keys()
        data_dicts = [dict(zip(column_names, row)) for row in rows]

        # Step 5: Categorize ens_ids into accepted & rejected lists
        accepted_ensid = set()
        reject_ensid = set()

        for entry in payload:
            if entry.status.strip().lower() in ['accept', 'accepted']:
                accepted_ensid.add(entry.ens_id)
            else:
                reject_ensid.add(entry.ens_id)

        # Step 6: Update accepted ens_ids
        if accepted_ensid:
            accept_query = (
                update(table_class)
                .where(table_class.c.ens_id.in_(accepted_ensid))
                .where(table_class.c.final_validation_status == FinalValidatedStatus.REVIEW)
                .values(
                    name=table_class.c.suggested_name,
                    name_international=table_class.c.suggested_name_international,
                    address=table_class.c.suggested_address,
                    postcode=table_class.c.suggested_postcode,
                    city=table_class.c.suggested_city,
                    country=table_class.c.suggested_country,
                    phone_or_fax=table_class.c.suggested_phone_or_fax,
                    email_or_website=table_class.c.suggested_email_or_website,
                    national_id=table_class.c.suggested_national_id,
                    state=table_class.c.suggested_state,
                    address_type=table_class.c.suggested_address_type,
                    final_status=FinalStatus.ACCEPTED
                )
            )
            await session.execute(accept_query)

        # Step 7: Update rejected ens_ids (including those not in accepted_ensid)
        all_ens_ids = {str(row["ens_id"]) for row in data_dicts}  # Convert to string
        print("all_ens_ids", all_ens_ids)
        # Include already accepted ens_ids from DB
        if accepted_ens_ids:
            accepted_ensid.update(accepted_ens_ids)
        remaining_rejected = all_ens_ids - accepted_ensid
        reject_ensid.update(remaining_rejected)

        if reject_ensid:
            reject_query = (
                update(table_class)
                .where(table_class.c.ens_id.in_(reject_ensid))
                .values(final_status=FinalStatus.REJECTED)
            )
            await session.execute(reject_query)

        # Step 8: Commit the transaction
        await session.commit()

        print("Final Accepted ens_ids:", accepted_ensid)
        print("Final Rejected ens_ids:", reject_ensid)

        # Step 9: Update supplier master data
        if len(list(accepted_ensid)):
            response_supplier_master_data = await update_supplier_master_data(session, session_id)
            print("Response from update_supplier_master_data:", response_supplier_master_data)

        # Return the response
        return {
            "status": "success",
            "message": "Data updated successfully.",
            "accepted_ens_ids": list(accepted_ensid),
            "rejected_ens_ids": list(reject_ensid)
        }

    except HTTPException as http_err:
        raise http_err  # Propagate HTTP exceptions

    except Exception as error:
        print(f"Unexpected error: {error}")
        raise HTTPException(
            status_code=500, 
            detail=f"An unexpected error occurred: {str(error)}"
        )
        
async def get_main_session_supplier(sess_id, page_no, rows_per_page, session) -> Dict:
    try:
        print("sess_id", sess_id)

        # Calculate offset and limit based on page_no and rows_per_page
        offset = (page_no-1) * rows_per_page if page_no else 0
        limit = rows_per_page if rows_per_page else 10000
        print("offset", offset, "limit", limit)
        extra_filters = {"offset": offset, "limit": limit}

        select_column = [
            "id", "name", "name_international", "address", "postcode", "city", "country",
            "phone_or_fax", "email_or_website", "national_id", "state", "ens_id",
            "session_id", "bvd_id", "create_time", "update_time", "validation_status", "final_status", "report_generation_status"
        ]
        
        session_supplier_data = await get_dynamic_ens_data(
            table_name="supplier_master_data",
            required_columns=select_column,
            ens_id="",
            session_id=sess_id,
            session=session,
            extra_filters=extra_filters
        )

        print("session_supplier_data", session_supplier_data)

        # If no data is found, return a 404 response
        if not session_supplier_data or not session_supplier_data[0]:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for session_id: {sess_id}"
            )

        res = {
            "status": "success",
            "total_data": session_supplier_data[1],
            "data": session_supplier_data[0],
            "session_id": sess_id
        }

        return res

    except HTTPException as http_err:
        raise http_err  # Re-raise HTTP exceptions for proper FastAPI handling

    except Exception as error:
        print(f"Unexpected error: {error}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(error)}"
        )
    
async def get_session_screening_status(page_no: int, rows_per_page: int, screening_analysis_status, session) -> Dict:
    try:
        # Calculate offset and limit based on page_no and rows_per_page
        offset = (page_no-1) * rows_per_page if page_no else 0
        limit = rows_per_page if rows_per_page else 10000
        print("offset", offset, "limit", limit)
        extra_filters = {"offset": offset, "limit": limit, "screening_analysis_status": screening_analysis_status}

        select_column = [
            "id", "session_id", "overall_status", "list_upload_status", 
            "supplier_name_validation_status", "screening_analysis_status", 
            "create_time", "update_time"
        ]

        # Fetch data dynamically
        session_screening_status_data = await get_dynamic_ens_data(
            table_name="session_screening_status", 
            required_columns=select_column, 
            ens_id="", 
            session_id="", 
            session=session, 
            extra_filters=extra_filters
        )

        print("session_screening_status_data", session_screening_status_data)

        # Handle case where no data is found
        if not session_screening_status_data[0]:
            raise HTTPException(
                status_code=404, 
                detail="No screening status data found."
            )

        return {
            "status": "success",
            "total_data": session_screening_status_data[1], 
            "data": session_screening_status_data[0]
        }

    except HTTPException as http_err:
        raise http_err  # Re-raise HTTP exceptions to keep proper status codes

    except Exception as error:
        print(f"Unexpected error: {error}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to retrieve screening status data: {str(error)}"
        )
    

async def get_nomatch_count(sess_id, session) -> Dict:
    try:
        if not sess_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session ID is required.")

        table_class = Base.metadata.tables.get("upload_supplier_master_data")
        if table_class is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database table not found.")

        not_validated_query = select(func.count()).select_from(table_class).where(
            table_class.c.session_id == sess_id,
            table_class.c.final_validation_status == FinalValidatedStatus.REVIEW
        )
        not_validated_result = await session.execute(not_validated_query)
        not_validated_count = not_validated_result.scalar()

        return {
            "not_validated_count": not_validated_count, 
            "session_id": sess_id
        }

    except HTTPException as http_err:
        raise http_err  # FastAPI HTTP exceptions are raised directly

    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error retrieving session supplier data: {str(error)}"
        )

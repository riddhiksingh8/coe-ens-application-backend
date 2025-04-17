import asyncio
from typing import Dict
import pycountry
import requests
from app.core.config import get_settings
from app.core.security.jwt import create_jwt_token
from app.core.supplier.supplier import update_suggestions_bulk
from app.schemas.requests import BulkPayload
from fastapi import  HTTPException, status
from app.core.utils.db_utils import *
import pandas as pd
import uuid
import io
from app.models import *
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
from azure.storage.blob import generate_container_sas, ContainerSasPermissions, BlobClient

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
        print("current_user_id", current_user)
        validate_request = await validate_user_request(current_user, session)
        print("validate_request:", validate_request)

        if validate_request > 5:
            raise ValueError("Maximum 5 requests can run at one time")
        contents = await file_contents.read()
        excel_file = io.BytesIO(contents)
        df = pd.read_excel(excel_file)
        df = df.where(pd.notnull(df), "")  
        # Check if the row count exceeds 25
        allowed_rows = 25
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

def trigger_supplier_validation(session_id: str, auth_token: str):
    """
    Sends a POST request to trigger supplier validation.

    :param session_id: The session ID to be sent in the request body.
    :param auth_token: The Bearer token for authorization.
    :return: Response JSON or error message.
    """
    url = get_settings().urls.analysis_orchestration +"/analysis/trigger-supplier-validation"

    # Request payload
    payload = {
        "session_id": session_id
    }

    # Request headers
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }

    try:
        # Making the POST request
        response = requests.post(url, json=payload, headers=headers)

        # Check response status
        response.raise_for_status()  # Raise error for bad status codes

        # Return JSON response
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
    
def trigger_analysis(session_id: str, auth_token: str):
    """
    Sends a POST request to trigger supplier validation.

    :param session_id: The session ID to be sent in the request body.
    :param auth_token: The Bearer token for authorization.
    :return: Response JSON or error message.
    """
    url = get_settings().urls.analysis_orchestration +"/analysis/trigger-analysis"

    # Request payload
    payload = {
        "session_id": session_id
    }

    # Request headers
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }

    try:
        # Making the POST request
        response = requests.post(url, json=payload, headers=headers)

        # Check response status
        response.raise_for_status()  # Raise error for bad status codes

        # Return JSON response
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
    
async def run_full_pipeline_background(session_id, session):
    try:
        # Take session ID
        print("sheet_data_run_full_pipeline_background", session_id)
        
        try:
            # Generate JWT token
            jwt_token = create_jwt_token("application_backend", "development")
        except Exception as e:
            print("Error generating JWT token:", e)
            raise

        try:
            # Step 1: Make HTTP request to trigger supplier name validation
            trigger_supplier_validation_response = trigger_supplier_validation(session_id, jwt_token.access_token)
            print("response", trigger_supplier_validation_response)
        except Exception as e:
            print("Error triggering supplier validation:", e)
            raise
        extra_filters = {"offset": 0, "limit": 10}

        # Step 2: Poll for result using a do-while loop
        select_column = ['supplier_name_validation_status']
        max_retries = 30  # Limit retries (every 2 min = ~1 hour)
        retry_count = 0

        while True:
            try:
                session_screening_status_data = await get_dynamic_ens_data(
                    table_name="session_screening_status",
                    required_columns=select_column,
                    ens_id="",
                    session_id=session_id,
                    session=session,
                    extra_filters=extra_filters
                )
                supplier_status = session_screening_status_data[0][0]['supplier_name_validation_status']

                print("session_screening_status_data______", session_screening_status_data)
                print(f"Current supplier validation status: {supplier_status}")
                # Convert Enum to string (extract actual status value)
                if isinstance(supplier_status, STATUS):  # If it's an Enum, get its value
                    supplier_status = supplier_status.value
                else:
                    supplier_status = str(supplier_status)  # Fallback conversion
                print(f"Current supplier validation status: {supplier_status}")
                # print("session_screening_status_data[0]", session_screening_status_data[0])
                # supplier_status = session_screening_status_data[0].get('supplier_name_validation_status', '')
                # print("Supplier Status:", supplier_status)
                if supplier_status == "COMPLETED":
                    print(f"Supplier validation completed: {supplier_status}")
                    break  # Exit loop and proceed to Step 3

                print(f"Current status: {supplier_status}. Waiting for completion...")
 
                if retry_count >= max_retries:
                    print("Max retries reached. Supplier validation did not complete.")
                    raise TimeoutError("Supplier validation timeout exceeded.")

                retry_count += 1
                print(f"Retrying... Attempt {retry_count}/{max_retries}")
                await asyncio.sleep(30)  # Wait for 30 sec before retrying

            except Exception as e:
                print("Error polling session status:", e)
                raise

        # Step 3: Bulk accept all suggestions for this session_id
        bulk_payload = {
            "session_id": str(session_id),
            "status": "accept"
        }
        
        print("Bulk Payload:", bulk_payload)

        try:
            # Call the function to update suggestions in bulk
            accept_status = await update_suggestions_bulk(BulkPayload(**bulk_payload), session)
            print("accept_status", accept_status)
        except Exception as e:
            print("Error updating suggestions in bulk:", e)
            raise

        try:
            # Trigger analysis pipeline
            trigger_analysis_response = trigger_analysis(session_id, jwt_token.access_token)
            print("Analysis pipeline triggered successfully:", trigger_analysis_response)
        except Exception as e:
            print("Error triggering analysis pipeline:", e)
            raise

    except Exception as e:
        print("Pipeline execution failed:", e)


def generate_container_sas_url(storage_account_name, storage_account_key, container_name, expiry_weeks):
    """
    Generates a SAS URL for an Azure Storage container.

    :param storage_account_name: Name of the Azure Storage Account
    :param storage_account_key: Storage Account Key
    :param container_name: Name of the container
    :param expiry_weeks: Validity period of the SAS token (in weeks)
    :return: Full SAS URL for the container
    """
    expiry_time = datetime.utcnow() + timedelta(weeks=expiry_weeks)
    start_time = datetime.utcnow() - timedelta(minutes=5)  # Fix time skew

    # Generate the SAS token for the container (not a specific blob)
    sas_token = generate_container_sas(
        account_name=storage_account_name,
        account_key=storage_account_key,
        container_name=container_name,
        permission=ContainerSasPermissions(read=True, write=True, delete=True, list=True),
        expiry=expiry_time,
        start=start_time
    )

    # Construct the SAS URL pointing to the container (not a blob)
    storage_account_url = f"https://{storage_account_name}.blob.core.windows.net/{container_name}"
    sas_url = f"{storage_account_url}?{sas_token}&comp=list&restype=container"

    print("Generated SAS URL:", sas_url)
    # blob_client = BlobClient.from_blob_url(sas_url)
    # try:     
    #     blob_properties = blob_client.get_blob_properties()    
    #     print(f"Blob properties: {blob_properties}")
    # except Exception as e:     
    #     print(f"An error occurred: {e}")
    return {"sas_url": sas_url, "sas_token":sas_token}

async def get_session_screening_status_static(
        session_id: str,
        session: AsyncSession = Depends(deps.get_session)
):
    try:
        required_columns = ["id", "session_id","overall_status","list_upload_status","supplier_name_validation_status","screening_analysis_status","create_time","update_time"]
        table_class = Base.metadata.tables.get("session_screening_status")
        if table_class is None:
            raise ValueError(
                f"Table session_screening_status does not exist in the database schema."
            )

        columns_to_select = [
            getattr(table_class.c, column) for column in required_columns
        ]

        query = select(*columns_to_select)

        if session_id:
            query = query.where(table_class.c.session_id == str(session_id))

        result = await session.execute(query)

        columns = result.keys()

        rows = result.all()
        # Example usage
        storage_account_name = get_settings().storage.storage_account_name
        storage_account_key = get_settings().storage.storage_account_key
        session_sas = generate_container_sas_url(storage_account_name, storage_account_key, session_id, 2)
        print("SAS URL:", session_sas)
        # sas_url = generate_sas_url(storage_account_name, storage_account_key, session_id)
        # print("Generated SAS URL:", sas_url)
        formatted_res = [
            dict(
                zip(columns, row)
            )  # zip the column names with their corresponding row values
            for row in rows
        ]
        merged_data = {**formatted_res[0], **session_sas}

        # Return the formatted result
        await session.close()

        print("______merged_data_____", merged_data)
    
        return merged_data

    except ValueError as ve:
        # Handle the case where the table does not exist
        print(f"Error: {ve}")
        return []

    except SQLAlchemyError as sa_err:
        # Handle SQLAlchemy-specific errors
        print(f"Database error: {sa_err}")
        return []

    except Exception as e:
        # Catch any other exceptions
        print(f"An unexpected error occurred: {e}")
        return []
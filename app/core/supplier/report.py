from typing import Dict
from fastapi import HTTPException
import urllib
from app.core.utils.db_utils import *
import io
from app.core.config import get_settings  # Import settings
from azure.storage.blob import BlobServiceClient
import zipfile
from app.schemas.logger import logger

async def report_download(session_id: str, ens_id: str, type_of_file: str)->Dict:
    try:
        # Retrieve storage settings
        storage_url = get_settings().storage.storage_account_url
        container_name = session_id  # Session ID is the container name
        sas_token = str(get_settings().storage.sas_token)

        # Initialize BlobServiceClient with SAS token
        blob_service_client = BlobServiceClient(account_url=storage_url, credential=sas_token)
        container_client = blob_service_client.get_container_client(container_name)

        # Define folder path based on ens_id (no leading slash)
        folder_path = f"{ens_id}/"

        # List blobs inside the specific folder
        blob_list = container_client.list_blobs(name_starts_with=folder_path)


        # Filter blobs that match session_id, ens_id, and type_of_file
        matching_blobs = [
            blob for blob in blob_list 
            if ens_id in blob.name and blob.name.endswith(f".{type_of_file}")
        ]

        # Ensure at least one matching file exists
        if not matching_blobs:
            raise HTTPException(status_code=404, detail=f"No matching {type_of_file} file found for session_id {session_id} and ens_id {ens_id}")

        # Sort blobs by last modified date to get the latest file
        latest_blob = max(matching_blobs, key=lambda b: b.last_modified)

        # URL decode the latest filename
        decoded_filename = urllib.parse.unquote(latest_blob.name)

        # Get the latest file's blob client
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=decoded_filename)

        # Download the blob data
        stream = blob_client.download_blob()
        file_data = stream.readall()

        return file_data, decoded_filename
    
    
    except Exception as e:
        logger.error(f"Error in report_download: {str(e)}")
        return {"error": str(e)}
    

async def report_bulk_download(session_id: str) -> Dict:
    try:
        # Retrieve storage settings
        storage_url = get_settings().storage.storage_account_url
        container_name = session_id
        sas_token = str(get_settings().storage.sas_token)

        # Initialize BlobServiceClient with SAS token
        blob_service_client = BlobServiceClient(account_url=storage_url, credential=sas_token)
        container_client = blob_service_client.get_container_client(container_name)

        
        # List all blobs inside the container
        blob_list = list(container_client.list_blobs())  # Convert generator to list

        # Ensure there are files to download
        if not blob_list:
            raise HTTPException(status_code=404, detail=f"No files found for session_id {session_id}")

        # Create an in-memory ZIP file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for blob in blob_list:
                blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob.name)
                file_data = blob_client.download_blob().readall()
                zip_file.writestr(blob.name, file_data)  # Add file to ZIP with original path

        # Seek to the beginning of the ZIP file
        zip_buffer.seek(0)
        
        return zip_buffer.getvalue(), f"{session_id}.zip"

    except Exception as e:
        logger.error(f"Error in report_bulk_download: {str(e)}")
        return {"error": str(e)}
        
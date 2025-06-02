from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.requests import BulkPayload, ClientConfigurationRequest, SinglePayloadItem
from app.schemas.responses import *
from app.core.supplier.supplier import *
from app.api import deps
import pandas as pd
import io
from app.schemas.logger import logger

router = APIRouter()


# @router.post("/upload-supplier-list", response_model=UserResponse, description="Get current user")
# async def read_current_user(
#     current_user: User = Depends(deps.get_current_user),
# ) -> User:
#     return current_user

@router.post("/upload-excel", response_model=ResponseMessage, status_code=status.HTTP_201_CREATED)
async def upload_excel(
    client_id: Optional[str] = Query(None),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(deps.get_session),
    current_user_id: User = Depends(deps.get_current_user),
):
    try:
        # Check if a file was uploaded
        if not file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file uploaded"
            )
        
        client_id = '5b638302-73cb-4a69-b76d-1efa5c00797a'
        sheet_data = await process_excel_file(file, client_id,current_user_id, session)
        response = ResponseMessage(
            status="success",
            data=sheet_data,  
            message="Excel file processed successfully"
        )
        return response

    except HTTPException as http_err:
        # Return structured error responses for HTTP exceptions
        raise http_err

    except Exception as error:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process the Excel file: {str(error)}"
        ) 
@router.get("/get-supplier-data", response_model=ResponseMessage, status_code=status.HTTP_200_OK)
async def get_supplier_data(
    session_id: str, 
    page_no: int = Query(1, ge=1),       
    rows_per_page: int = Query(10, le=1000), 
    final_validation_status: Literal["", "review", "auto_reject", "auto_accept"] = "",
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_user)
):
    try:
        # Validate session_id
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No session_id provided"
            )

        # Fetch data from DB
        sheet_data = await get_session_supplier(session_id, page_no, rows_per_page, final_validation_status, session)

        return ResponseMessage(
            status="success",
            data=sheet_data,
            message="Successfully retrieved data"
        )

    except HTTPException as http_err:
        raise http_err  # Pass FastAPI exceptions as they are

    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve data: {str(error)}"
        )
   
   
@router.put("/update-suggestions-bulk", response_model=ResponseMessage, status_code=status.HTTP_200_OK)
async def accept_suggestions_bulk(payload: BulkPayload, session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_user)):
    try:
        # Validate status field
        if payload.status.lower().strip() not in ["accept", "reject"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status. Use 'accept' or 'reject'."
            )

        # Call the function to update suggestions in bulk
        update_res = await update_suggestions_bulk(payload, session)

        # If update failed or no rows were updated, handle accordingly
        if not update_res or update_res.get("status") != "success":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process suggestions update."
            )

        # Return success response
        return ResponseMessage(
            status="success",
            data={"data": update_res},
            message=f"Suggestions for session {payload.session_id} have been {payload.status}."
        )

    except HTTPException as http_err:
        raise http_err  # Re-raise FastAPI exceptions with proper status codes

    except Exception as error:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error occurred: {str(error)}"
        )

@router.put("/update-suggestions-single", response_model=ResponseMessage)
async def accept_suggestions_single(
    session_id: str,
    payload: List[SinglePayloadItem], 
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_user)
):
    if not payload:
        raise HTTPException(
            status_code=400, 
            detail="Payload is empty. Please provide valid data."
        )

    # Validate each item's status
    for item in payload:
        if item.status.strip().lower() not in ["accept", "reject"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid status '{item.status}' for ens_id {item.ens_id}. Use 'accept' or 'reject'."
            )

    try:
        update_res = await update_suggestions_single(payload, session_id, session)

        if update_res.get("status") == "error":
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to update suggestions: {update_res.get('message')}"
            )

        return ResponseMessage(
            status="success",
            data=update_res,  # Include response data
            message=f"Suggestions have been updated successfully for {len(payload)} items."
        )

    except HTTPException as http_err:
        raise http_err  # Re-raise FastAPI-specific HTTP exceptions

    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise HTTPException(
            status_code=500, 
            detail=f"An unexpected error occurred: {str(error)}"
        )
   
@router.get("/get-main-supplier-data", response_model=ResponseMessage)
async def get_main_supplier_data(
    session_id: str, 
    page_no: int = Query(1, ge=1),       
    rows_per_page: int = Query(10, le=1000), 
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_user)
):
    try:
        # Validate session_id
        if not session_id:
            raise HTTPException(status_code=400, detail="No session_id provided.")

        # Fetch supplier data
        sheet_data = await get_main_session_supplier(session_id, page_no, rows_per_page, session)

        # If no data found, raise a 404 error
        if not sheet_data.get("data"):
            raise HTTPException(status_code=404, detail=f"No supplier data found for session_id: {session_id}")

        return ResponseMessage(
            status="success",
            data=sheet_data,  # Include data as a dictionary
            message="Successfully retrieved data."
        )

    except HTTPException as http_err:
        raise http_err  # Re-raise HTTP exceptions to maintain proper status codes

    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve data: {str(error)}"
        ) 

 
@router.get("/get-main-supplier-data-compiled", response_model=ResponseMessage)
async def get_main_supplier_data_compiled(
    session_id: str, 
    page_no: int = Query(1, ge=1),       
    rows_per_page: int = Query(10, le=1000), 
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_user)
):
    try:
        # Validate session_id
        if not session_id:
            raise HTTPException(status_code=400, detail="No session_id provided.")

        # Fetch supplier data
        sheet_data = await get_main_session_supplier_compiled(session_id, page_no, rows_per_page, session)

        # If no data found, raise a 404 error
        if not sheet_data.get("data"):
            raise HTTPException(status_code=404, detail=f"No supplier data found for session_id: {session_id}")

        return ResponseMessage(
            status="success",
            data=sheet_data,  # Include data as a dictionary
            message="Successfully retrieved data."
        )

    except HTTPException as http_err:
        raise http_err  # Re-raise HTTP exceptions to maintain proper status codes

    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve data: {str(error)}"
        ) 

@router.get("/get-session-screening-status", response_model=ResponseMessage)
async def get_session_screening_status_data(
    page_no: int = Query(1, ge=1),       
    rows_per_page: int = Query(10, le=1000), 
    screening_analysis_status: Optional[Literal["", "active", "not_started"]] = "",
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_user)
):
    try:
        # Fetch screening status data
        sheet_data = await get_session_screening_status(page_no, rows_per_page, screening_analysis_status, session)

        # Ensure the data exists
        if not sheet_data["data"]:
            raise HTTPException(
                status_code=404, 
                detail="No screening status data found."
            )

        return ResponseMessage(
            status="success",
            data=sheet_data,  
            message="Successfully Retrieved Data"
        )

    except HTTPException as http_err:
        # Raise FastAPI HTTPExceptions for correct status codes
        raise http_err

    except Exception as error:
        logger.error(f"Unexpected error: {error}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve data: {str(error)}"
        )


@router.get("/get-nomatch-count", response_model=ResponseMessage, status_code=status.HTTP_200_OK)
async def get_nomatch(
    session_id: str,
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_user)
):
    try:
        # Validate session_id
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No session_id provided"
            )

        # Fetch data from DB
        nomatch_data = await get_nomatch_count(session_id, session)

        return ResponseMessage(
            status="success",
            data=nomatch_data,
            message="Successfully retrieved data"
        )

    except HTTPException as http_err:
        raise http_err  # Pass FastAPI exceptions as they are

    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve data: {str(error)}"
        )
 
 
@router.post(
    "/client-configuration",
    description="Client Configuration",
    status_code=status.HTTP_201_CREATED,
)
async def client_configuration(
    client_configuration: ClientConfigurationRequest,
    current_user_id: User = Depends(deps.get_current_user),
    session: AsyncSession = Depends(deps.get_session)
):
    try:
        client_config_response = await client_config(client_configuration, session)
        response = ResponseMessage(
            status="success",
            data=client_config_response,  
            message="Client config processed successfully"
        )
        return response

    except HTTPException as http_err:
        # Return structured error responses for HTTP exceptions
        raise http_err

    except Exception as error:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to processing client config: {str(error)}"
        ) 
    

# @router.post(
#     "/session-configuration",
#     description="Session Configuration",
#     status_code=status.HTTP_201_CREATED,
# )
# async def client_configuration(
#     client_id: str,
#     session_id: str,
#     session: AsyncSession = Depends(deps.get_session)
# ):
#     try:
#         session_config_response = await upsert_session_config(client_id, session_id,session)
#         print("session_config_response", session_config_response)
#         response = ResponseMessage(
#             status="success",
#             data=session_config_response,  
#             message="Session config processed successfully"
#         )
#         return response

#     except HTTPException as http_err:
#         # Return structured error responses for HTTP exceptions
#         raise http_err

#     except Exception as error:
#         # Handle unexpected errors
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to processing client config: {str(error)}"
#         ) 
    
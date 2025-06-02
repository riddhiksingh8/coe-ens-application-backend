from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.responses import *
from app.core.tprp.tprp import *
from app.api import deps
from app.schemas.logger import logger

router = APIRouter()
@router.post(
    "/supplier-screening",
    response_model=ResponseMessage,
    status_code=status.HTTP_201_CREATED,
    description=(
        "**Supplier Screening File Upload** 📂\n\n"
        "This endpoint allows users to upload an Excel file for supplier screening. "
        "The file is processed asynchronously, and a background task executes the full screening pipeline. "
        "A user can have a maximum of **5 active requests** at any given time.\n\n"
        "### **Process Flow**\n"
        "1️⃣ **Upload an Excel file** containing supplier data.\n"
        "2️⃣ **System Validates the Request:** Ensures the user hasn't exceeded the max active requests.\n"
        "3️⃣ **Extract & Process Data:** Parses the Excel file for supplier screening.\n"
        "4️⃣ **Trigger Background Task:** Initiates an asynchronous screening pipeline.\n"
        "5️⃣ **Return Response:** Confirms successful processing or returns an error.\n\n"
        "### **Constraints & Validation**\n"
        "🔹 Only **Excel files** (`.xlsx`, `.xls`) are supported.\n"
        "🔹 Maximum **5 concurrent requests per user**.\n\n"
        "### **Possible Responses**\n"
        "✅ **201 Created** - File processed successfully.\n"
        "❌ **400 Bad Request** - No file uploaded or request limit exceeded.\n"
        "❌ **500 Internal Server Error** - Unexpected processing error."
    ),
)
async def upload_excel(
    background_tasks: BackgroundTasks,  # ✅ Move it before parameters with default values
    file: UploadFile = File(..., description="The Excel file (.xlsx or .xls) containing supplier screening data."),
    session: AsyncSession = Depends(deps.get_session),
    current_user_id: User = Depends(deps.get_current_user),
):
    """
    ## Upload Supplier Screening Excel File  
    - **Validates**: Ensures a file is uploaded.
    - **Checks User Limit**: Maximum 5 active requests per user.
    - **Processes Excel File**: Extracts and processes supplier data.
    - **Triggers Background Task**: Runs the screening pipeline asynchronously.

    **Responses:**
    - ✅ **201 Created**: File processed successfully.
    - ❌ **400 Bad Request**: No file uploaded or request limit exceeded.
    - ❌ **500 Internal Server Error**: Unexpected processing error.
    """
    try:
        # Check if a file was uploaded
        if not file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file uploaded"
            )
        

        sheet_data = await process_excel_file(file, current_user_id, session)
        response = ResponseMessage(
            status="success",
            data=sheet_data,  
            message="Excel file processed successfully"
        )
        
        background_tasks.add_task(run_full_pipeline_background, sheet_data['session_id'], session)

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
    
@router.get(
    "/session-status", response_model=ResponseMessage, description="**📡 Session Screening Status Check with SAS URL (Polling API)**\n\n"
        "This endpoint retrieves the latest screening status of a given `session_id` **and** generates a **Secure Access Signature (SAS) URL** for accessing session-related data securely from cloud storage.\n\n"
        "### **How It Works**\n"
        "🔹 **Clients send a `GET` request** with a valid `session_id`.\n"
        "🔹 **Server fetches the latest status** from the database.\n"
        "🔹 **A SAS URL is generated**, allowing temporary access to session data stored in Azure Blob Storage.\n\n"
        "### **Use Cases**\n"
        "✅ Check if a session is still **processing, completed, or failed**.\n"
        "✅ Track real-time updates in a **frontend dashboard**.\n"
        "✅ Fetch a **secure download link** for session-related files.\n\n"
        "### **Security & Expiry**\n"
        "🔒 The SAS URL is **time-limited** (2 hours by default) to prevent unauthorized access.\n"
        "🔒 Ensures **secure access** without exposing actual credentials.\n\n"
        "### **Possible Responses**\n"
        "🔹 **200 OK** - Returns session status & SAS URL successfully.\n"
        "🔹 **400 Bad Request** - Invalid `session_id`.\n"
        "🔹 **500 Internal Server Error** - Unexpected processing error."
)
async def get_sessionid_status_poll(
    session_id: str = Query(..., description="Session ID"),
    db_session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_user)
):
    """

    :param request:
    :return:
    """
    try:
        logger.debug(f"session_id, {session_id}")

        initial_state = await get_session_screening_status_static(session_id, db_session)

        logger.debug(f"{initial_state}")

        return {"status": "", "data": initial_state, "message": ""}

    except Exception as e:
        # Handle errors gracefully
        raise HTTPException(status_code=500, detail=f"Error running analysis: {str(e)}")

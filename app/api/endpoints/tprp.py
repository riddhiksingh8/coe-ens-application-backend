from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.responses import *
from app.core.tprp.tprp import *
from app.api import deps

router = APIRouter()

@router.post("/supplier-screening", response_model=ResponseMessage, status_code=status.HTTP_201_CREATED)
async def upload_excel(
    background_tasks: BackgroundTasks,  # ✅ Move it before parameters with default values
    file: UploadFile = File(...),
    session: AsyncSession = Depends(deps.get_session),
    current_user: User = Depends(deps.get_current_user),
):
    try:
        # Check if a file was uploaded
        if not file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file uploaded"
            )

        sheet_data = await process_excel_file(file, session)
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
    "/session-status", response_model=ResponseMessage, description="Stream Status SSE for Session ID Changes"
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
        print("session_id", session_id)

        initial_state = await get_session_screening_status_static(session_id, db_session)

        print(initial_state)

        return {"status": "", "data": initial_state, "message": ""}

    except Exception as e:
        # Handle errors gracefully
        raise HTTPException(status_code=500, detail=f"Error running analysis: {str(e)}")

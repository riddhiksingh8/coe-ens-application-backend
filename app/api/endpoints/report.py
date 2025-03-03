from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.requests import BulkPayload, SinglePayloadItem
from app.schemas.responses import *
from app.core.supplier.report import *
from app.api import deps
import pandas as pd
import io
from app.core.config import get_settings

router = APIRouter()
from fastapi import APIRouter, Query
from fastapi.responses import Response
from typing import Optional
from app.models import User

router = APIRouter()

@router.get("/download-report/")
async def download_report(
    session_id: str = Query(..., description="Session ID"),
    ens_id: str = Query(..., description="ENS ID"),
    type_of_file: str = Query(..., description="Type of file (e.g., docx, pdf, csv)"),
    current_user: User = Depends(deps.get_current_user)
):
    try:
        file_data, result = await report_download(session_id, ens_id, type_of_file)

        if file_data is None:
            return {"error": result}

        # Determine media type based on file type
        media_types = {
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pdf": "application/pdf",
            "csv": "text/csv"
        }
        media_type = media_types.get(type_of_file.lower(), "application/octet-stream")

        return Response(
            content=file_data,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={result}"}
        )

    except Exception as e:
        return {"error": str(e)}


@router.get("/bulk-download-report/")
async def bulk_download_report(session_id: str = Query(..., description="Session ID"),
    current_user: User = Depends(deps.get_current_user)):
    try:
        file_data, result = await report_bulk_download(session_id)

        if file_data is None:
            return {"error": result}

        return Response(
            content=file_data,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={result}"}
        )

    except Exception as e:
        return {"error": str(e)}

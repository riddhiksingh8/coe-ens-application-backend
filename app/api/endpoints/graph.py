from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from app.schemas.requests import *
from app.schemas.responses import *
from app.core.supplier.graph import *
from app.api import deps
from app.models import User
from app.schemas.requests import *

router = APIRouter()

@router.post("/get-network-graph")
async def get_graph(filter_request: SupplierFilterRequest):

    try:
        filter_request = filter_request.dict()

        transformed_data = await run_graph_retrieval(filter_request)

        # print(transformed_data)

        return transformed_data

    except HTTPException as http_err:
        # Return structured error responses for HTTP exceptions
        raise http_err

    except Exception as error:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate network graph: {str(error)}"
        )

@router.post("/get-submodal-profile")
async def get_profile(request: SubModalItem,
                      session: AsyncSession = Depends(deps.get_session),
                      current_user: User = Depends(deps.get_current_user)
                      ):
    try:
        request = request.dict()
        ens_id = request.get("ens_id","")

        transformed_data = await compile_company_profile(ens_id, session)

        return transformed_data

    except HTTPException as http_err:
        # Return structured error responses for HTTP exceptions
        raise http_err

    except Exception as error:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve profile for ens_id: {str(error)}"
        )

@router.post("/get-submodal-findings")
async def get_findings(request: SubModalItem,
                       session: AsyncSession = Depends(deps.get_session),
                       current_user: User = Depends(deps.get_current_user)):

    try:
        request = request.dict()
        ens_id = request.get("ens_id", "")

        transformed_data = await compile_company_findings(ens_id, session)

        return transformed_data

    except HTTPException as http_err:
        # Return structured error responses for HTTP exceptions
        raise http_err

    except Exception as error:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve findings for ens_id: {str(error)}"
        )

@router.post("/get-submodal-financials")
async def get_findings(request: SubModalItem,
                       session: AsyncSession = Depends(deps.get_session),
                       current_user: User = Depends(deps.get_current_user)):

    try:
        request = request.dict()
        ens_id = request.get("ens_id", "")

        transformed_data = await compile_company_financials(ens_id, session)

        return transformed_data

    except HTTPException as http_err:
        # Return structured error responses for HTTP exceptions
        raise http_err

    except Exception as error:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve findings for ens_id: {str(error)}"
        )

@router.get("/supplier-countries")
async def get_supplier_countries(client_id: str = Query(..., description="UUID of the company"), session: AsyncSession = Depends(deps.get_session),
                       current_user: User = Depends(deps.get_current_user)):
    try:

        transformed_data = await get_distinct_supplier_countries(client_id)

        return transformed_data

    except HTTPException as http_err:
        # Return structured error responses for HTTP exceptions
        raise http_err

    except Exception as error:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve findings for ens_id: {str(error)}"
        )
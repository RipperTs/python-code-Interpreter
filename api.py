import os
import logging
import mimetypes

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from starlette.responses import FileResponse, JSONResponse

from execution_service import ExecuteRequest, ExecutionService
from settings import Settings
from utils import UtilsClass

router = APIRouter()


class CodeRequest(BaseModel):
    code: str


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_utils(request: Request) -> UtilsClass:
    return request.app.state.utils


def get_execution_service(request: Request) -> ExecutionService:
    return request.app.state.execution_service


@router.post("/api/v1/execute")
async def execute(
    request: CodeRequest,
    service: ExecutionService = Depends(get_execution_service),
    utils: UtilsClass = Depends(get_utils),
    settings: Settings = Depends(get_settings),
):
    try:
        code = utils.format_python_code(request.code)
        exec_result = await service.execute(ExecuteRequest(code=code))
        payload = exec_result.to_legacy_dict(
            image_url_prefix=settings.image_url_prefix,
            file_url_prefix=settings.file_url_prefix,
        )
        status_code = 400 if payload.get("error") else 200
        return JSONResponse(content=payload, status_code=status_code)
    except Exception as e:
        logging.error(f"Error executing code: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/images/{filename}")
def get_image(
    filename: str,
    settings: Settings = Depends(get_settings),
):
    safe_name = os.path.basename(filename)
    if safe_name != filename:
        raise HTTPException(status_code=400, detail={"error": "Invalid filename"})

    try:
        path_or_file = os.path.join(settings.image_store_path, safe_name)
        return FileResponse(path_or_file, media_type="image/png")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "File not found"})


@router.get("/files/{filename}")
def get_file(
    filename: str,
    settings: Settings = Depends(get_settings),
):
    safe_name = os.path.basename(filename)
    if safe_name != filename:
        raise HTTPException(status_code=400, detail={"error": "Invalid filename"})

    try:
        path_or_file = os.path.join(settings.file_store_path, safe_name)
        media_type, _ = mimetypes.guess_type(path_or_file)
        return FileResponse(path_or_file, media_type=media_type or "application/octet-stream")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "File not found"})

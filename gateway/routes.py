import os
import logging
import mimetypes
import traceback
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.responses import FileResponse, JSONResponse

from common.capabilities import get_executor_runtime_info
from common.contracts import ExecuteRequest, ExecutionService
from common.settings import Settings
from common.utils import UtilsClass

router = APIRouter()


class CodeRequest(BaseModel):
    code: str
    files: list[str] = Field(default_factory=list)


class InstalledPackage(BaseModel):
    name: str
    version: str


class CapabilitiesResponse(BaseModel):
    pythonVersion: Optional[str] = None
    installedPackages: list[InstalledPackage] = Field(default_factory=list)
    limits: dict = Field(default_factory=dict)
    networkPolicy: dict = Field(default_factory=dict)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_utils(request: Request) -> UtilsClass:
    return request.app.state.utils


def get_execution_service(request: Request) -> ExecutionService:
    return request.app.state.execution_service


@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities(settings: Settings = Depends(get_settings)):
    runtime = get_executor_runtime_info(settings)

    limits = {
        "maxConcurrency": settings.max_workers,
        "executionTimeoutSeconds": settings.execution_timeout,
        "container": {
            "memory": "1g",
            "cpus": 1,
            "pidsLimit": settings.docker_pids_limit,
        },
        "input": {
            "maxFiles": settings.input_max_files,
            "maxFileBytes": settings.input_file_max_bytes,
            "totalMaxBytes": settings.input_total_max_bytes,
        },
        "output": {
            "maxFiles": settings.output_max_files,
            "maxFileBytes": settings.output_file_max_bytes,
            "totalMaxBytes": settings.output_total_max_bytes,
            "allowedExtensions": sorted(list(settings.output_allowed_extensions or set())),
        },
    }

    internet_access = (settings.docker_network_mode or "").strip().lower() != "none"
    network_policy = {
        "executorNetworkMode": settings.docker_network_mode,
        "internetAccess": internet_access,
        "supportsHttpInputFiles": True,
        "supportsPipInstall": internet_access,
        "introspection": {
            "ok": runtime.ok,
            "error": runtime.error,
        },
    }

    installed_packages = []
    for item in runtime.installed_packages or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        version = str(item.get("version", "")).strip()
        if not name:
            continue
        installed_packages.append(InstalledPackage(name=name, version=version))

    return CapabilitiesResponse(
        pythonVersion=runtime.python_version,
        installedPackages=installed_packages,
        limits=limits,
        networkPolicy=network_policy,
    )


@router.post("/api/v1/execute")
async def execute(
    request: CodeRequest,
    service: ExecutionService = Depends(get_execution_service),
    utils: UtilsClass = Depends(get_utils),
    settings: Settings = Depends(get_settings),
):
    try:
        code = utils.format_python_code(request.code)
        exec_result = await service.execute(ExecuteRequest(code=code, files=request.files))
        payload = exec_result.to_legacy_dict(
            image_url_prefix=settings.image_url_prefix,
            file_url_prefix=settings.file_url_prefix,
            public_base_url=settings.public_base_url,
        )
        # 下游仅通过 `error` 字段判断成功/失败，因此统一返回 200。
        return JSONResponse(content=payload, status_code=200)
    except Exception as e:
        logging.exception("Error executing code")
        payload = {
            "result": "",
            "error": traceback.format_exc(),
            "execution_time": 0,
            "image_url": None,
            "files": [],
            "inputs": [],
        }
        return JSONResponse(content=payload, status_code=200)


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

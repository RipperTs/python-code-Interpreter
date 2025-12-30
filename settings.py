import os
from dataclasses import dataclass


def _env_bool(key: str, default: bool) -> bool:
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(key: str, default: int) -> int:
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_csv_set(key: str, default: str) -> set:
    value = os.environ.get(key, default)
    items = [item.strip().lower() for item in value.split(",") if item.strip()]
    return set(items)


@dataclass(frozen=True)
class Settings:
    debug: bool = False
    port: int = 14564
    max_workers: int = 4
    execution_timeout: int = 30
    docker_image: str = "registry.cn-hangzhou.aliyuncs.com/ripper/python-executor:latest"
    docker_network_mode: str = "bridge"
    docker_pids_limit: int = 256
    image_store_path: str = "./images"
    image_url_prefix: str = "/images"
    file_store_path: str = "./files"
    file_url_prefix: str = "/files"
    input_max_files: int = 10
    input_file_max_bytes: int = 20 * 1024 * 1024
    input_total_max_bytes: int = 50 * 1024 * 1024
    output_max_files: int = 20
    output_file_max_bytes: int = 5 * 1024 * 1024
    output_total_max_bytes: int = 20 * 1024 * 1024
    output_allowed_extensions: set = None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            debug=_env_bool("DEBUG", False),
            port=_env_int("PORT", 14564),
            max_workers=_env_int("MAX_WORKERS", 4),
            execution_timeout=_env_int("EXECUTION_TIMEOUT", 30),
            docker_image=os.environ.get(
                "DOCKER_IMAGE",
                "registry.cn-hangzhou.aliyuncs.com/ripper/python-executor:latest",
            ),
            docker_network_mode=os.environ.get("DOCKER_NETWORK_MODE", "bridge"),
            docker_pids_limit=_env_int("DOCKER_PIDS_LIMIT", 256),
            image_store_path=os.environ.get("IMAGE_STORE_PATH", "./images"),
            image_url_prefix=os.environ.get("IMAGE_URL_PREFIX", "/images"),
            file_store_path=os.environ.get("FILE_STORE_PATH", "./files"),
            file_url_prefix=os.environ.get("FILE_URL_PREFIX", "/files"),
            input_max_files=_env_int("INPUT_MAX_FILES", 10),
            input_file_max_bytes=_env_int("INPUT_FILE_MAX_BYTES", 20 * 1024 * 1024),
            input_total_max_bytes=_env_int("INPUT_TOTAL_MAX_BYTES", 50 * 1024 * 1024),
            output_max_files=_env_int("OUTPUT_MAX_FILES", 20),
            output_file_max_bytes=_env_int("OUTPUT_FILE_MAX_BYTES", 5 * 1024 * 1024),
            output_total_max_bytes=_env_int("OUTPUT_TOTAL_MAX_BYTES", 20 * 1024 * 1024),
            output_allowed_extensions=_env_csv_set(
                "OUTPUT_ALLOWED_EXTENSIONS",
                "md,csv,txt,json,log",
            ),
        )

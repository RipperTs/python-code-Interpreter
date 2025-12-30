from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol


def _join_public_url(public_base_url: str, path: str) -> str:
    if not path:
        return path
    base = (public_base_url or "").strip()
    if not base:
        return path
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


@dataclass(frozen=True)
class ExecuteRequest:
    code: str
    files: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OutputFile:
    filename: str
    original_name: str
    size_bytes: int

    def to_dict(self, file_url_prefix: str = "/files", public_base_url: str = "") -> dict:
        url = _join_public_url(
            public_base_url,
            f"{file_url_prefix.rstrip('/')}/{self.filename}",
        )
        return {
            "filename": self.filename,
            "original_name": self.original_name,
            "size_bytes": self.size_bytes,
            "url": url,
        }


@dataclass(frozen=True)
class InputFile:
    url: str
    original_name: str
    local_name: str
    size_bytes: int

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "original_name": self.original_name,
            "local_name": self.local_name,
            "local_path": f"/code/input/{self.local_name}",
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class ExecuteResult:
    stdout: str
    stderr: Optional[str]
    execution_time: float
    image_filename: Optional[str] = None
    files: list[OutputFile] = field(default_factory=list)
    inputs: list[InputFile] = field(default_factory=list)

    def to_legacy_dict(
        self,
        image_url_prefix: str = "/images",
        file_url_prefix: str = "/files",
        public_base_url: str = "",
    ) -> dict:
        image_url = None
        if self.image_filename:
            image_url = _join_public_url(
                public_base_url,
                f"{image_url_prefix.rstrip('/')}/{self.image_filename}",
            )
        return {
            "result": self.stdout,
            "error": self.stderr,
            "execution_time": self.execution_time,
            "image_url": image_url,
            "files": [f.to_dict(file_url_prefix, public_base_url) for f in self.files],
            "inputs": [i.to_dict() for i in self.inputs],
        }


class ExecutionService(Protocol):
    async def initialize(self) -> None: ...

    async def shutdown(self) -> None: ...

    async def execute(self, request: ExecuteRequest) -> ExecuteResult: ...

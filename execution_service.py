from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol


@dataclass(frozen=True)
class ExecuteRequest:
    code: str


@dataclass(frozen=True)
class OutputFile:
    filename: str
    original_name: str
    size_bytes: int

    def to_dict(self, file_url_prefix: str = "/files") -> dict:
        url = f"{file_url_prefix.rstrip('/')}/{self.filename}"
        return {
            "filename": self.filename,
            "original_name": self.original_name,
            "size_bytes": self.size_bytes,
            "url": url,
        }


@dataclass(frozen=True)
class ExecuteResult:
    stdout: str
    stderr: Optional[str]
    execution_time: float
    image_filename: Optional[str] = None
    files: list[OutputFile] = field(default_factory=list)

    def to_legacy_dict(self, image_url_prefix: str = "/images", file_url_prefix: str = "/files") -> dict:
        image_url = (
            f"{image_url_prefix.rstrip('/')}/{self.image_filename}"
            if self.image_filename
            else None
        )
        return {
            "result": self.stdout,
            "error": self.stderr,
            "execution_time": self.execution_time,
            "image_url": image_url,
            "files": [f.to_dict(file_url_prefix) for f in self.files],
        }


class ExecutionService(Protocol):
    async def initialize(self) -> None: ...

    async def shutdown(self) -> None: ...

    async def execute(self, request: ExecuteRequest) -> ExecuteResult: ...

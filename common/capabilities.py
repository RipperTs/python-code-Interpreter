import json
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Optional

from common.settings import Settings


def _list_installed_packages() -> list[dict]:
    try:
        from importlib import metadata
    except ImportError:  # pragma: no cover
        import importlib_metadata as metadata  # type: ignore

    seen: dict[str, str] = {}
    for dist in metadata.distributions():
        name = (dist.metadata.get("Name") or "").strip()
        if not name:
            continue
        seen[name] = getattr(dist, "version", "") or ""

    items = [{"name": name, "version": version} for name, version in seen.items()]
    items.sort(key=lambda item: item["name"].lower())
    return items


@dataclass(frozen=True)
class ExecutorRuntimeInfo:
    ok: bool
    python_version: Optional[str]
    installed_packages: list[dict]
    error: Optional[str] = None


_CACHE_TTL_SECONDS = 300
_cache_lock = threading.Lock()
_runtime_cache: dict[str, tuple[float, ExecutorRuntimeInfo]] = {}


def _inspect_executor_image(settings: Settings) -> ExecutorRuntimeInfo:
    code = (
        "import json, platform\n"
        "pkgs={}\n"
        "metadata=None\n"
        "try:\n"
        "    from importlib import metadata as _m\n"
        "    metadata=_m\n"
        "except Exception:\n"
        "    try:\n"
        "        import importlib_metadata as _m\n"
        "        metadata=_m\n"
        "    except Exception:\n"
        "        metadata=None\n"
        "\n"
        "if metadata is not None:\n"
        "    for d in metadata.distributions():\n"
        "        n=(d.metadata.get('Name') or '').strip()\n"
        "        if n:\n"
        "            pkgs[n]=getattr(d,'version','') or ''\n"
        "else:\n"
        "    try:\n"
        "        import pkg_resources\n"
        "        for d in pkg_resources.working_set:\n"
        "            n=(getattr(d,'project_name','') or '').strip()\n"
        "            if n:\n"
        "                pkgs[n]=getattr(d,'version','') or ''\n"
        "    except Exception:\n"
        "        pkgs={}\n"
        "\n"
        "items=[{'name':k,'version':v} for k,v in pkgs.items()]\n"
        "items.sort(key=lambda x: x['name'].lower())\n"
        "print(json.dumps({'pythonVersion': platform.python_version(), 'installedPackages': items}, ensure_ascii=False))\n"
    )

    cmd = [
        "docker",
        "run",
        "--rm",
        "--network",
        settings.docker_network_mode,
        "--memory=1g",
        "--cpus=1",
        "--pids-limit",
        str(settings.docker_pids_limit),
        settings.docker_image,
        "python",
        "-c",
        code,
    ]

    process = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if process.returncode != 0:
        message = (process.stderr or process.stdout or "docker run failed").strip()
        return ExecutorRuntimeInfo(ok=False, python_version=None, installed_packages=[], error=message)

    try:
        payload = json.loads((process.stdout or "").strip())
    except json.JSONDecodeError:
        return ExecutorRuntimeInfo(
            ok=False,
            python_version=None,
            installed_packages=[],
            error="invalid json output from executor image",
        )

    python_version = payload.get("pythonVersion")
    installed = payload.get("installedPackages") or []
    if not isinstance(installed, list):
        installed = []

    return ExecutorRuntimeInfo(ok=True, python_version=python_version, installed_packages=installed, error=None)


def get_executor_runtime_info(settings: Settings) -> ExecutorRuntimeInfo:
    cache_key = settings.docker_image
    now = time.time()

    with _cache_lock:
        cached = _runtime_cache.get(cache_key)
        if cached and now - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]

    runtime = _inspect_executor_image(settings)
    if not runtime.ok:
        runtime = ExecutorRuntimeInfo(
            ok=False,
            python_version=None,
            installed_packages=_list_installed_packages(),
            error=runtime.error,
        )

    with _cache_lock:
        _runtime_cache[cache_key] = (now, runtime)

    return runtime

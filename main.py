from fastapi import FastAPI
import uvicorn
from dotenv import load_dotenv
from contextlib import asynccontextmanager

from executor import CodeExecutor
from api import router
from settings import Settings
from utils import UtilsClass

load_dotenv()


def create_app(settings: Settings = None) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    utils = UtilsClass(image_dir=resolved_settings.image_store_path)
    execution_service = CodeExecutor(settings=resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = resolved_settings
        app.state.utils = utils
        app.state.execution_service = execution_service
        await execution_service.initialize()
        yield
        await execution_service.shutdown()

    app = FastAPI(lifespan=lifespan)
    app.include_router(router)
    return app


app = create_app()


if __name__ == '__main__':
    try:
        import uvloop
    except ImportError:
        uvloop = None
    if uvloop:
        uvloop.install()

    settings = Settings.from_env()
    RELOAD = settings.debug
    LISTEN_PORT = settings.port
    uvicorn.run("main:app", host="0.0.0.0", port=LISTEN_PORT, workers=1, reload=RELOAD)

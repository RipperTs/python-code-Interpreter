from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from common.settings import Settings
from common.utils import UtilsClass
from executors.docker_executor import CodeExecutor
from gateway.routes import router


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


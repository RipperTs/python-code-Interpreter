import uvicorn
from common.settings import Settings
from gateway.app import create_app as _create_app

create_app = _create_app
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

from fastapi import FastAPI, HTTPException
import os
import uvicorn
from dotenv import load_dotenv
import logging

from starlette.responses import JSONResponse, FileResponse

from executor import CodeExecutor
from utils import UtilsClass
from pydantic import BaseModel

app = FastAPI()
load_dotenv()
utils = UtilsClass()
executor = CodeExecutor()


class CodeRequest(BaseModel):
    code: str


@app.post('/api/v1/execute')
async def execute(request: CodeRequest):
    try:
        # 格式化代码
        code = utils.format_python_code(request.code)

        # 执行代码
        result = await executor.execute_code(code)

        if result.get('error'):
            return JSONResponse(
                content=result,
                status_code=400
            )

        return JSONResponse(content=result)

    except Exception as e:
        logging.error(f"Error executing code: {str(e)}")
        return JSONResponse(
            content={'error': str(e)},
            status_code=500
        )


@app.get("/images/{filename}")
def get_image(filename):
    try:
        path_or_file = os.path.join(utils.get_image_dir(), filename)
        return FileResponse(
            path_or_file,
            media_type="image/png"
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error": "File not found"}
        )


if __name__ == '__main__':
    try:
        import uvloop
    except ImportError:
        uvloop = None
    if uvloop:
        uvloop.install()

    RELOAD = os.environ.get('DEBUG', 'False').lower() == 'true'
    LISTEN_PORT = int(os.environ.get('PORT', 14564))
    uvicorn.run("app:app", host="0.0.0.0", port=LISTEN_PORT, workers=1, reload=RELOAD)

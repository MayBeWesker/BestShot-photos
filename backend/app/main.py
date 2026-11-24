from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import router
from .config import APP_NAME
from .errors import BestShotError


app = FastAPI(title=APP_NAME, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BestShotError)
async def handle_bestshot_error(_: Request, exc: BestShotError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})


@app.exception_handler(Exception)
async def handle_unknown_error(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "处理失败，请查看后端日志。"}})


app.include_router(router)


# backend/app/middleware.py
# 【全队约定】业务响应一律 HTTP 200,错误经 body.code 表达(code=0 成功,非0失败)。
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.response import fail, BizError

logger = logging.getLogger("talentmind")

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BizError)
    async def _biz(request: Request, exc: BizError):
        # 业务异常为预期内错误,warning 级别记录,便于排查但不刷 error 噪声
        logger.warning("BizError code=%s msg=%s path=%s", exc.code, exc.message, request.url.path)
        return JSONResponse(status_code=200, content=fail(exc.code, exc.message))

    @app.middleware("http")
    async def _unhandled(request: Request, call_next):
        # Starlette 的 ServerErrorMiddleware 在调用 exception_handler(Exception) 生成
        # 响应后仍会重新抛出原始异常向上传播(供 ASGI 服务器记录),TestClient 会将其
        # 暴露为测试失败。故在此层直接 try/except 兜底,异常不再向外传播。
        try:
            return await call_next(request)
        except Exception as exc:
            logger.error("Unhandled exception at %s", request.url.path, exc_info=exc)
            return JSONResponse(status_code=200, content=fail(5000, "internal error"))

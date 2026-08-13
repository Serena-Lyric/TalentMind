from fastapi import FastAPI
from app.response import ok, BizError
from app.middleware import register_exception_handlers

app = FastAPI(title="TalentMind")
register_exception_handlers(app)

@app.get("/health")
async def health():
    return ok({"status": "up"})

@app.get("/_test_bizerror")
async def _test_bizerror():
    raise BizError(4001, "boom")

@app.get("/_test_crash")
async def _test_crash():
    raise RuntimeError("unexpected")

# 统一 API（A 集成层，阶段 6 MVP）
from app.routers.mvp import router as mvp_router
app.include_router(mvp_router, prefix="/api")


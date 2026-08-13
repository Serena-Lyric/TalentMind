from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.response import ok, BizError
from app.middleware import register_exception_handlers

app = FastAPI(title="TalentMind")
register_exception_handlers(app)

# 前端联调 CORS（Vite dev / preview）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
from app.routers.dashboard import router as dashboard_router
app.include_router(mvp_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")


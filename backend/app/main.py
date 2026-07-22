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

# 各人 router 挂载点(计划 A~E 在此 include_router)

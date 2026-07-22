from typing import Any

def ok(data: Any = None, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}

def fail(code: int, message: str) -> dict:
    return {"code": code, "message": message, "data": None}

class BizError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

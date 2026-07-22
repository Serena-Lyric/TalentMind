from app.response import ok, fail, BizError

def test_ok_wraps_data():
    assert ok({"x": 1}) == {"code": 0, "message": "ok", "data": {"x": 1}}

def test_fail_shape():
    assert fail(1001, "bad") == {"code": 1001, "message": "bad", "data": None}

def test_bizerror_carries_code():
    e = BizError(2001, "not found")
    assert e.code == 2001 and e.message == "not found"

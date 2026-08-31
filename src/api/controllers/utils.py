def make_response(data, detail: str = "success", status_code: int = 200):
    return {
        "data": data,
        "detail": detail,
        "status_code": status_code
    }

from typing import Any


def success_response(data: Any = None, message: str = "Success", status_code: int = 200) -> dict:
    return {"success": True, "message": message, "data": data}


def error_response(message: str, error_code: str = "ERROR", details: Any = None) -> dict:
    resp = {"success": False, "message": message, "error_code": error_code}
    if details:
        resp["details"] = details
    return resp

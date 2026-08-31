from fastapi import status
from pydantic import BaseModel

class ReadyResponse(BaseModel):
    status: int = status.HTTP_200_OK
    detail: str
    data: object
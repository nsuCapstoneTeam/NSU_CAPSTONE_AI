from pydantic import BaseModel


class LiveResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    database: str
    pgvector: str


class NotReadyResponse(BaseModel):
    status: str
    reason: str
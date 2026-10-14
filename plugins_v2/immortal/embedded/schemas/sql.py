from pydantic import BaseModel, Field


class SQLExecuteParam(BaseModel):
    sql: str = Field(..., min_length=1)
    max_rows: int | None = Field(default=200, ge=1, le=1000)


class SQLSchemaSyncParam(BaseModel):
    apply: bool = False

from pydantic import BaseModel, Field


class OperationRequest(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    qty: int = Field(gt=0)
    warehouse: str = Field(min_length=1, max_length=100)

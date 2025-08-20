from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ContractMetadata(BaseModel):
    contract_id: str
    filename: str
    lang: str = "eng"
    chunks: int
    text_length: int
    upload_date: Optional[datetime] = None

class ContractUploadResponse(BaseModel):
    contract_id: str
    chunks: int
    status: str

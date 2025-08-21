from pydantic import BaseModel
from typing import List, Optional

class ContractUploadResponse(BaseModel):
    contract_id: str
    filename: str
    chunks_processed: int
    document_ids: List[str]

class SearchQuery(BaseModel):
    text: str
    top_k: Optional[int] = 5
    contract_id: Optional[str] = None

class SearchResult(BaseModel):
    text: str
    contract_id: Optional[str]
    chunk_index: Optional[int]
    score: float

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total_results: int

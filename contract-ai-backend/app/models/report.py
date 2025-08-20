from pydantic import BaseModel
from typing import List, Dict, Any

class ValidationResult(BaseModel):
    clause: str
    match: str
    similarity: float

class ValidationReport(BaseModel):
    contract_id: str
    results: List[ValidationResult]

class SystemSummary(BaseModel):
    total_clauses: int
    total_vectors: int
    system_status: str

class ClauseAnalysis(BaseModel):
    total_clauses: int
    categories: Dict[str, int]
    clauses: List[Dict[str, Any]]

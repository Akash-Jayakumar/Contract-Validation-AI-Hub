from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class Clause(BaseModel):
    title: str
    text: str
    category: str
    description: Optional[str] = None
    tags: Optional[List[str]] = []
    created_at: Optional[datetime] = None

class ClauseResponse(BaseModel):
    id: str
    title: str
    text: str
    category: str
    description: Optional[str] = None
    tags: Optional[List[str]] = []

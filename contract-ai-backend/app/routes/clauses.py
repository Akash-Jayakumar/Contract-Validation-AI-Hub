from fastapi import APIRouter, Body, HTTPException
from app.db.mongo import save_clause, get_clauses, get_clause_by_id, update_clause, delete_clause
from bson import ObjectId

router = APIRouter()

@router.post("/add")
def add_clause(clause: dict = Body(...)):
    """Add a new clause to the library"""
    required_fields = ["title", "text", "category"]
    if not all(field in clause for field in required_fields):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    result = save_clause(clause)
    return {"status": "added", "clause_id": str(result.inserted_id)}

@router.get("/")
def list_clauses():
    """Get all clauses from the library"""
    clauses = get_clauses()
    # Convert ObjectId to string for JSON serialization
    for clause in clauses:
        clause["_id"] = str(clause["_id"])
    return clauses

@router.get("/{clause_id}")
def get_clause(clause_id: str):
    """Get a specific clause by ID"""
    try:
        clause = get_clause_by_id(clause_id)
        if not clause:
            raise HTTPException(status_code=404, detail="Clause not found")
        clause["_id"] = str(clause["_id"])
        return clause
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid clause ID")

@router.put("/{clause_id}")
def update_clause_endpoint(clause_id: str, clause: dict = Body(...)):
    """Update an existing clause"""
    try:
        result = update_clause(clause_id, clause)
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Clause not found")
        return {"status": "updated"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{clause_id}")
def delete_clause_endpoint(clause_id: str):
    """Delete a clause"""
    try:
        result = delete_clause(clause_id)
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Clause not found")
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

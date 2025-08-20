from fastapi import APIRouter, HTTPException
from typing import Dict, List
from app.db.mongo import get_clauses
from app.db.vector import get_collection_info

router = APIRouter()

@router.get("/summary")
def get_system_summary():
    """Get system summary and statistics"""
    try:
        clauses = get_clauses()
        
        # Get collection info
        try:
            collection_info = get_collection_info()
            vector_count = collection_info.points_count
        except:
            vector_count = 0
        
        return {
            "total_clauses": len(clauses),
            "total_vectors": vector_count,
            "system_status": "operational"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")

@router.get("/clause-analysis")
def get_clause_analysis():
    """Get analysis of clause library"""
    try:
        clauses = get_clauses()
        
        # Basic analysis
        categories = {}
        for clause in clauses:
            category = clause.get("category", "uncategorized")
            if category not in categories:
                categories[category] = 0
            categories[category] += 1
        
        return {
            "total_clauses": len(clauses),
            "categories": categories,
            "clauses": [{"id": str(c["_id"]), "title": c["title"], "category": c["category"]} for c in clauses]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")

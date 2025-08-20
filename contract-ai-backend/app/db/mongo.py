from pymongo import MongoClient
from app.config import MONGO_URI

client = MongoClient(MONGO_URI)
db = client["contracts_db"]

def save_contract_meta(meta):
    """Save contract metadata to the database"""
    return db.contracts.insert_one(meta)

def get_contract_meta(cid):
    """Get contract metadata by contract ID"""
    return db.contracts.find_one({"contract_id": cid})

def save_clause(clause):
    """Save a clause to the database"""
    return db.clauses.insert_one(clause)

def get_clauses():
    """Get all clauses from the database"""
    return list(db.clauses.find({}))

def get_clause_by_id(clause_id):
    """Get a specific clause by ID"""
    from bson import ObjectId
    return db.clauses.find_one({"_id": ObjectId(clause_id)})

def update_clause(clause_id, updates):
    """Update a clause"""
    from bson import ObjectId
    return db.clauses.update_one({"_id": ObjectId(clause_id)}, {"$set": updates})

def delete_clause(clause_id):
    """Delete a clause"""
    from bson import ObjectId
    return db.clauses.delete_one({"_id": ObjectId(clause_id)})

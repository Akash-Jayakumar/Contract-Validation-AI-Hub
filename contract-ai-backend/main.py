from fastapi import FastAPI
from app.routes.contracts import router as contracts_router
from app.routes.clauses import router as clauses_router
from app.routes.chat import router as chat_router
from app.routes.validation import router as validation_router
from app.routes.reports import router as reports_router

app = FastAPI(title="Contract AI Backend")
app.include_router(contracts_router, prefix="/contracts", tags=["contracts"])
app.include_router(clauses_router, prefix="/clauses", tags=["clauses"])
app.include_router(chat_router, prefix="/contracts/chat", tags=["chat"])
app.include_router(validation_router, prefix="/contracts", tags=["validation"])
app.include_router(reports_router, prefix="/reports", tags=["reports"])

@app.get("/")
async def root():
    return {"message": "Contract AI Backend is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

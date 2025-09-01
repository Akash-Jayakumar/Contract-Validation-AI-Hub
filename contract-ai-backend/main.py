from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware
 
from app.routes.contracts import router as contracts_router

from app.routes.clauses import router as clauses_router

from app.routes.chat import router as chat_router

from app.routes.validation import router as validation_router

from app.routes.reports import router as reports_router

from app.routes.checklist import router as checklist_router
from app.routes.policies import router as policies_router
from app.routes.compliance_docx import router as compliance_docx_router
 
app = FastAPI(title="Contract AI Backend")
 
# ✅ CORS Middleware

origins = [

    "http://localhost:3000",   # React/Next frontend

    "http://127.0.0.1:3000",

    "http://localhost:5173",   # Vite frontend

    "https://your-frontend-domain.com"  # production frontend

]
 
app.add_middleware(

    CORSMiddleware,

    allow_origins=origins,       # allowed frontend origins

    allow_credentials=True,

    allow_methods=["*"],         # allow all HTTP methods

    allow_headers=["*"],         # allow all headers

)
 
# ✅ Routers

app.include_router(checklist_router, prefix="/checklist", tags=["checklist"])

app.include_router(contracts_router, prefix="/contracts", tags=["contracts"])

app.include_router(clauses_router, prefix="/clauses", tags=["clauses"])

app.include_router(chat_router, prefix="/contracts/chat", tags=["chat"])

app.include_router(validation_router, prefix="/validation", tags=["validation"])

app.include_router(reports_router, prefix="/reports", tags=["reports"])
app.include_router(policies_router, prefix="/policies", tags=["policies"])
app.include_router(compliance_docx_router, prefix="/compliance", tags=["compliance"])

@app.get("/")
async def root():
    return {"message": "Contract AI Backend is running"}
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
 
# Contract AI Backend

A comprehensive backend service for contract analysis using OCR, vector embeddings, and AI-powered validation.

## Features

- **OCR Processing**: Extract text from PDFs and images
- **Vector Search**: Semantic search using Qdrant vector database
- **Clause Library**: Manage standard contract clauses
- **Contract Validation**: Validate contracts against clause library
- **Chat Interface**: Q&A with contracts using natural language
- **Report Generation**: Generate compliance and analysis reports

## Architecture

```
contract-ai-backend/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration settings
│   ├── services/            # Business logic services
│   │   ├── ocr.py          # OCR text extraction
│   │   ├── chunk.py        # Text chunking logic
│   │   ├── embeddings.py   # Vector embeddings
│   │   ├── matcher.py      # Similarity matching
│   │   ├── clause_lib.py   # Clause CRUD operations
│   │   └── llm.py          # LLM integration
│   ├── routes/             # API endpoints
│   │   ├── contracts.py    # Contract upload and management
│   │   ├── clauses.py      # Clause library management
│   │   ├── chat.py         # Chat/Q&A interface
│   │   ├── validation.py   # Contract validation
│   │   └── reports.py      # Report generation
│   ├── db/                 # Database connections
│   │   ├── mongo.py        # MongoDB operations
│   │   └── vector.py       # Qdrant vector operations
│   └── models/             # Pydantic models
│       ├── contract.py     # Contract models
│       ├── clause.py       # Clause models
│       └── report.py       # Report models
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
└── README.md             # This file
```

## Installation

1. **Clone the repository**
2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Start required services**
   - MongoDB: `mongod`
   - Qdrant: `docker run -p 6333:6333 qdrant/qdrant`

5. **Run the application**
   ```bash
   uvicorn app.main:app --reload
   ```

## API Endpoints

### Contracts
- `POST /contracts/upload` - Upload and process contract
- `GET /contracts/{contract_id}` - Get contract metadata

### Clauses
- `POST /clauses/add` - Add new clause
- `GET /clauses/` - List all clauses
- `GET /clauses/{clause_id}` - Get specific clause
- `PUT /clauses/{clause_id}` - Update clause
- `DELETE /clauses/{clause_id}` - Delete clause

### Chat
- `POST /contracts/chat` - Chat with contracts

### Validation
- `POST /contracts/{contract_id}/validate` - Validate contract against clauses

### Reports
- `GET /reports/summary` - System summary
- `GET /reports/clause-analysis` - Clause library analysis

## Usage Examples

### Upload a Contract
```bash
curl -X POST "http://localhost:8000/contracts/upload" \
  -F "file=@contract.pdf" \
  -F "lang=eng"
```

### Add a Clause
```bash
curl -X POST "http://localhost:8000/clauses/add" \
  -H "Content-Type: application/json" \
  -d '{"title": "NDA Clause", "text": "The parties agree to maintain confidentiality...", "category": "confidentiality"}'
```

### Validate a Contract
```bash
curl -X POST "http://localhost:8000/contracts/{contract_id}/validate"
```

### Chat with Contracts
```bash
curl -X POST "http://localhost:8000/contracts/chat" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the payment terms?"}'
```

## Development

### Adding New Features
1. Create service in `app/services/`
2. Add route in `app/routes/`
3. Update models in `app/models/`
4. Add tests

### Environment Setup
- Python 3.8+
- MongoDB 5.0+
- Qdrant 1.6+
- Tesseract OCR (for OCR functionality)

## License
MIT License

import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

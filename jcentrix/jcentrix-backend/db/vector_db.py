import chromadb
from chromadb.config import Settings as ChromaSettings
from core.config import settings
import os

# Ensure persistent directory exists
os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)

# Initialize ChromaDB client
chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)

# Get or create collections
resumes_collection = chroma_client.get_or_create_collection(
    name="resumes",
    metadata={"hnsw:space": "cosine"} # Using cosine similarity for matching
)

jobs_collection = chroma_client.get_or_create_collection(
    name="jobs",
    metadata={"hnsw:space": "cosine"}
)

def get_vector_db():
    return chroma_client

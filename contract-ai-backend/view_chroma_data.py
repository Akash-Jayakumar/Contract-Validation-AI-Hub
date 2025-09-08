import chromadb
from chromadb.config import Settings

def view_chroma_data(collection_name="contracts"):
    """View all extracted text data stored in ChromaDB"""
    # Initialize ChromaDB client
    client = chromadb.PersistentClient(
        path="./chroma_db",
        settings=Settings(anonymized_telemetry=False)
    )

    # Get the specified collection
    collection = client.get_or_create_collection(collection_name)

    # Get all documents, metadatas, and ids
    results = collection.get()

    documents = results.get('documents', [])
    metadatas = results.get('metadatas', [])
    ids = results.get('ids', [])

    print(f"Total documents in collection '{collection_name}': {len(documents)}")
    print("=" * 80)

    # Print each document
    for i, (doc_id, doc, meta) in enumerate(zip(ids, documents, metadatas)):
        print(f"Document {i+1}:")
        print(f"ID: {doc_id}")
        print(f"Metadata: {meta}")
        print(f"Extracted Text: {doc}")
        print("-" * 80)

if __name__ == "__main__":
    import sys
    collection = sys.argv[1] if len(sys.argv) > 1 else "contracts"
    view_chroma_data(collection)

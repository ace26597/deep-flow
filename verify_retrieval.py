import os
import logging
from src.rag.mongodb import MongoDBRetriever
from src.rag.retriever import Resource

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_retrieval():
    print("Starting retrieval verification...")
    
    # Ensure env vars are set (or set them here for testing)
    # os.environ["MONGODB_URI"] = "..." # Should be in .env
    # os.environ["OPENAI_API_KEY"] = "..." # Should be in .env
    os.environ["MONGODB_VECTOR_INDEX"] = "openai_vector_index"
    
    try:
        retriever = MongoDBRetriever()
        
        # Test query
        query = "summarize files in collection"
        
        # Test resource (simulating user selection)
        resources = [
            Resource(
                uri="mongodb://deep_flow/ACe_Default",
                title="ACe_Default",
                description="MongoDB Collection: ACe_Default"
            )
        ]
        
        print(f"Querying with: '{query}' against resources: {[r.title for r in resources]}")
        
        documents = retriever.query_relevant_documents(query, resources)
        
        print(f"\nFound {len(documents)} documents.")
        
        for i, doc in enumerate(documents):
            print(f"\n--- Document {i+1} ---")
            print(f"ID: {doc.id}")
            print(f"Title: {doc.title}")
            print(f"URL: {doc.url}")
            if doc.chunks:
                print(f"Content Preview: {doc.chunks[0].content[:200]}...")
            else:
                print("No content chunks.")
                
        if not documents:
            print("\nWARNING: No documents found. Check if collection exists, has data, and index is active.")
            
    except Exception as e:
        print(f"\nERROR: Verification failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_retrieval()

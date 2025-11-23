import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

mongodb_uri = os.getenv("MONGODB_URI")
mongodb_db = os.getenv("MONGODB_DB")

print(f"Checking MongoDB connection...")
print(f"URI: {mongodb_uri}")
print(f"DB: {mongodb_db}")

if not mongodb_uri:
    print("Error: MONGODB_URI not found in environment variables.")
    sys.exit(1)

if not mongodb_db:
    print("Error: MONGODB_DB not found in environment variables.")
    sys.exit(1)

try:
    client = MongoClient(mongodb_uri)
    # Force a connection verification
    client.admin.command('ping')
    print("Successfully connected to MongoDB!")
    
    db = client[mongodb_db]
    collections = db.list_collection_names()
    print(f"\nAvailable collections in database '{mongodb_db}':")
    for col in collections:
        print(f" - {col}")
        
    print("\nChecking for valid resource pairs (collection + collection_filemeta):")
    valid_pairs = []
    for col in collections:
        if f"{col}_filemeta" in collections:
            valid_pairs.append(col)
            print(f" [MATCH] Found pair: {col} and {col}_filemeta")
            
    if not valid_pairs:
        print("\nWARNING: No valid collection pairs found. The UI will not show any collections.")
        print("Expected naming convention: 'mycollection' and 'mycollection_filemeta'")
    else:
        print(f"\nFound {len(valid_pairs)} valid collection pairs.")

except Exception as e:
    print(f"\nConnection failed: {e}")
    sys.exit(1)

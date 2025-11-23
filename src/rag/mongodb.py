# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import logging
from typing import Any, Dict, List, Optional

from langchain_openai import OpenAIEmbeddings
from openai import OpenAI
from pymongo import MongoClient

from src.config.configuration import Configuration
from src.config.loader import get_str_env
from src.rag.retriever import Chunk, Document, Resource, Retriever

logger = logging.getLogger(__name__)



class MongoDBRetriever(Retriever):
    """Retriever implementation backed by MongoDB Atlas Vector Search."""

    def __init__(self) -> None:
        self.config = Configuration.from_runnable_config()
        self.uri = self.config.mongodb_uri or get_str_env("MONGODB_URI")
        self.db_name = self.config.mongodb_db or get_str_env("MONGODB_DB", "deep_flow")
        self.collection_name = self.config.mongodb_collection or get_str_env(
            "MONGODB_COLLECTION", "documents"
        )
        self.file_meta_collection_name = (
            self.config.mongodb_file_meta_collection or "_filemeta"
        )
        self.vector_field = self.config.mongodb_vector_field or "embedding"
        self.content_field = self.config.mongodb_content_field or "text"

        # Embedding configuration (reusing Milvus env vars for now or defaults)
        self.embedding_model_name = get_str_env("MILVUS_EMBEDDING_MODEL", "text-embedding-3-large")
        self.embedding_api_key = get_str_env("MILVUS_EMBEDDING_API_KEY") or None
        self.embedding_base_url = get_str_env("MILVUS_EMBEDDING_BASE_URL") or None
        self.embedding_provider = get_str_env("MILVUS_EMBEDDING_PROVIDER", "openai")
        
        # self._init_embedding_model() # Lazy init
        self.client: Optional[MongoClient] = None
        self.db = None
        self.collection = None
        self.embedding_model = None

    def _init_embedding_model(self) -> None:
        """Initialize the embedding model based on configuration."""
        if self.embedding_model:
            return
            
        kwargs = {
            "api_key": self.embedding_api_key,
            "model": self.embedding_model_name,
            "base_url": self.embedding_base_url,
            # "dimensions": 1536, # Optional, depends on model
        }
        self.embedding_model = OpenAIEmbeddings(**kwargs)

    def _connect(self) -> None:
        """Connect to MongoDB."""
        if not self.client:
            try:
                self.client = MongoClient(self.uri)
                self.db = self.client[self.db_name]
                self.collection = self.db[self.collection_name]
                # Send a ping to confirm a successful connection
                self.client.admin.command('ping')
                logger.info("Successfully connected to MongoDB")
            except Exception as e:
                # Log connection details (masking sensitive info) for debugging
                masked_uri = self.uri.replace(self.uri.split("@")[0].split("//")[-1], "***:***") if "@" in self.uri else "mongodb://***"
                logger.error(f"Connection parameters: URI={masked_uri}, DB={self.db_name}, Collection={self.collection_name}")
                logger.exception(f"Failed to connect to MongoDB: {e}")
                raise

    def _get_embedding(self, text: str) -> list[float]:
        """Return embedding for a given text."""
        self._init_embedding_model()
        return self.embedding_model.embed_query(text)

    def query_relevant_documents(
        self, query: str, resources: Optional[list[Resource]] = None
    ) -> list[Document]:
        """Perform vector similarity search."""
        try:
            self._connect()
            query_embedding = self._get_embedding(query)

            # Determine which collections to query
            collections_to_query = []
            if resources:
                for resource in resources:
                    # Assuming resource.uri contains the collection name or is the collection name
                    # For simplicity, let's assume the title or a specific part of URI is the collection name
                    # If resource.uri is "mongodb://db/collection/file_id", we might need to parse it.
                    # But for this specific requirement, let's assume we pass collection names as resources.
                    # Or we can parse the URI.
                    # Let's try to parse the collection name from the URI if it follows the standard format
                    # mongodb://db_name/collection_name/...
                    try:
                        parts = resource.uri.replace("mongodb://", "").split("/")
                        if len(parts) >= 2:
                            collections_to_query.append(parts[1])
                    except Exception:
                        pass
            
            if not collections_to_query:
                # Default to the main configured collection if no specific resources are provided
                collections_to_query.append(self.collection_name)

            all_documents = {}

            for col_name in set(collections_to_query):
                try:
                    collection = self.db[col_name]
                    
                    # Basic vector search pipeline
                    pipeline = [
                        {
                            "$vectorSearch": {
                                "index": "vector_index",
                                "path": self.vector_field,
                                "queryVector": query_embedding,
                                "numCandidates": 100,
                                "limit": 10,
                            }
                        },
                        {
                            "$project": {
                                "_id": 1,
                                self.content_field: 1,
                                "title": 1,
                                "source": 1,
                                "url": 1,
                                "score": {"$meta": "vectorSearchScore"},
                            }
                        },
                    ]

                    results = list(collection.aggregate(pipeline))
                    
                    for res in results:
                        doc_id = str(res.get("_id"))
                        content = res.get(self.content_field, "")
                        title = res.get("title", "Untitled")
                        url = res.get("url", "")
                        score = res.get("score", 0.0)
                        
                        # Use a unique key combining collection and doc_id to avoid collisions
                        unique_id = f"{col_name}:{doc_id}"

                        if unique_id not in all_documents:
                            all_documents[unique_id] = Document(
                                id=unique_id, url=url, title=title, chunks=[]
                            )
                        
                        chunk = Chunk(content=content, similarity=score)
                        all_documents[unique_id].chunks.append(chunk)

                except Exception as e:
                    logger.exception(f"MongoDB vector search failed for collection {col_name}: {e}")
                    continue

            return list(all_documents.values())

        except Exception as e:
            logger.exception(f"Failed to query relevant documents: {e}")
            return []

    def list_resources(self, query: Optional[str] = None) -> list[Resource]:
        """List available resources (collections that have a corresponding _filemeta collection)."""
        self._connect()
        resources = []
        
        try:
            # List all collection names
            all_collections = self.db.list_collection_names()
            
            # Filter for collections that have a corresponding _filemeta collection
            valid_collections = []
            for col in all_collections:
                if f"{col}_filemeta" in all_collections:
                    valid_collections.append(col)
            
            for col_name in valid_collections:
                # Optionally filter by query if it matches collection name
                if query and query.lower() not in col_name.lower():
                    continue

                resources.append(
                    Resource(
                        uri=f"mongodb://{self.db_name}/{col_name}",
                        title=col_name,
                        description=f"MongoDB Collection: {col_name}"
                    )
                )
        except Exception as e:
            logger.exception(f"Failed to list resources: {e}")
            
        return resources

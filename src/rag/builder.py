# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from src.config.tools import SELECTED_RAG_PROVIDER, RAGProvider
from src.rag.retriever import Retriever


def build_retriever() -> Retriever | None:
    import os
    if SELECTED_RAG_PROVIDER == RAGProvider.MONGODB.value:
        from src.rag.mongodb import MongoDBRetriever
        return MongoDBRetriever()
    elif not SELECTED_RAG_PROVIDER and os.getenv("MONGODB_URI"):
        # Fallback to MongoDB if URI is present but provider not explicitly set
        from src.rag.mongodb import MongoDBRetriever
        return MongoDBRetriever()
    elif SELECTED_RAG_PROVIDER:
        raise ValueError(f"Unsupported RAG provider: {SELECTED_RAG_PROVIDER}")
    return None

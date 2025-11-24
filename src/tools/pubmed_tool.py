# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
Direct PubMed search using NCBI E-utilities API.

This implementation uses NCBI's E-utilities API directly instead of langchain wrappers.
Documentation: https://www.ncbi.nlm.nih.gov/books/NBK25501/

Required environment variables:
- PUBMED_EMAIL: Your email address (required for high-volume usage)
- NCBI_API_KEY: Optional API key for higher rate limits (recommended)
"""

import json
import logging
import os
import time
from typing import List, Optional
from urllib.parse import urlencode
from urllib.request import urlopen

from langchain_core.tools import BaseTool
from pydantic import Field

logger = logging.getLogger(__name__)

# NCBI E-utilities base URL
EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Rate limiting: 3 requests per second without API key, 10 per second with API key
# We'll be conservative and use 0.35 seconds between requests
REQUEST_DELAY = 0.35


class PubMedSearchTool(BaseTool):
    """
    Direct PubMed search tool using NCBI E-utilities API.
    
    Uses ESearch to find articles and ESummary to get detailed information.
    """
    
    name: str = "pubmed_search"
    description: str = (
        "Search PubMed database for biomedical literature. "
        "Input should be a search query string. "
        "Returns formatted results with titles, authors, journals, abstracts, and PMIDs."
    )
    
    max_results: int = Field(default=10, description="Maximum number of results to return")
    email: Optional[str] = Field(default=None, description="Email address for NCBI API (required for high-volume usage)")
    api_key: Optional[str] = Field(default=None, description="NCBI API key for higher rate limits")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Get email and API key from environment if not provided
        if not self.email:
            self.email = os.getenv("PUBMED_EMAIL")
        if not self.api_key:
            self.api_key = os.getenv("NCBI_API_KEY")
        
        if not self.email:
            logger.warning(
                "PUBMED_EMAIL not set. NCBI recommends providing an email address "
                "for high-volume usage. Set PUBMED_EMAIL environment variable."
            )
    
    def _esearch(self, query: str, retmax: int = 100) -> List[str]:
        """
        Search PubMed using ESearch and return list of PMIDs.
        
        Args:
            query: Search query string
            retmax: Maximum number of IDs to return
            
        Returns:
            List of PMIDs (as strings)
        """
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": retmax,
            "retmode": "json",
            "usehistory": "y",  # Use history for efficient batch retrieval
        }
        
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key
        
        url = f"{EUTILS_BASE_URL}/esearch.fcgi?{urlencode(params)}"
        
            try:
                logger.debug(f"ESearch request: {url}")
                with urlopen(url) as response:
                    data = response.read().decode("utf-8")
                    result = json.loads(data)
                
                if "esearchresult" in result:
                    pmids = result["esearchresult"].get("idlist", [])
                    logger.info(f"ESearch found {len(pmids)} articles for query: {query}")
                    return pmids
                else:
                    logger.warning(f"Unexpected ESearch response structure: {result}")
                    return []
        except Exception as e:
            logger.error(f"Error in ESearch: {e}")
            return []
        finally:
            # Rate limiting
            time.sleep(REQUEST_DELAY)
    
    def _esummary(self, pmids: List[str]) -> List[dict]:
        """
        Get article summaries using ESummary.
        
        Args:
            pmids: List of PubMed IDs
            
        Returns:
            List of article summary dictionaries
        """
        if not pmids:
            return []
        
        # ESummary can handle up to 100 IDs at once
        all_summaries = []
        batch_size = 100
        
        for i in range(0, len(pmids), batch_size):
            batch_pmids = pmids[i:i + batch_size]
            id_string = ",".join(batch_pmids)
            
            params = {
                "db": "pubmed",
                "id": id_string,
                "retmode": "json",
            }
            
            if self.email:
                params["email"] = self.email
            if self.api_key:
                params["api_key"] = self.api_key
            
            url = f"{EUTILS_BASE_URL}/esummary.fcgi?{urlencode(params)}"
            
            try:
                logger.debug(f"ESummary request for {len(batch_pmids)} articles")
                with urlopen(url) as response:
                    data = response.read().decode("utf-8")
                    result = json.loads(data)
                    
                    if "result" in result:
                        # ESummary returns a dict keyed by PMID
                        summaries = []
                        for pmid in batch_pmids:
                            if pmid in result["result"]:
                                summaries.append(result["result"][pmid])
                        all_summaries.extend(summaries)
                    else:
                        logger.warning(f"Unexpected ESummary response structure")
            except Exception as e:
                logger.error(f"Error in ESummary: {e}")
            finally:
                # Rate limiting
                time.sleep(REQUEST_DELAY)
        
        return all_summaries
    
    def _format_result(self, article: dict) -> str:
        """
        Format a single article summary into a readable string.
        
        Args:
            article: Article summary dictionary from ESummary
            
        Returns:
            Formatted string
        """
        lines = []
        
        # Title
        title = article.get("title", "No title")
        lines.append(f"**Title:** {title}")
        
        # Authors
        authors = article.get("authors", [])
        if authors:
            author_list = []
            for author in authors[:10]:  # Limit to first 10 authors
                name = author.get("name", "")
                if name:
                    author_list.append(name)
            if author_list:
                lines.append(f"**Authors:** {', '.join(author_list)}")
                if len(authors) > 10:
                    lines.append(f"  *... and {len(authors) - 10} more authors*")
        
        # Journal
        source = article.get("source", "")
        if source:
            lines.append(f"**Journal:** {source}")
        
        # Publication date
        pubdate = article.get("pubdate", "")
        if pubdate:
            lines.append(f"**Published:** {pubdate}")
        
        # DOI
        elocationid = article.get("elocationid", "")
        if elocationid and elocationid.startswith("10."):
            lines.append(f"**DOI:** {elocationid}")
        
        # Abstract
        if "abstract" in article:
            abstract = article["abstract"]
            # Truncate long abstracts
            if len(abstract) > 1000:
                abstract = abstract[:1000] + "..."
            lines.append(f"**Abstract:** {abstract}")
        elif "abstracttext" in article:
            abstract = article["abstracttext"]
            if len(abstract) > 1000:
                abstract = abstract[:1000] + "..."
            lines.append(f"**Abstract:** {abstract}")
        
        # PMID
        pmid = article.get("uid", "")
        if pmid:
            lines.append(f"**PMID:** {pmid}")
            lines.append(f"**Link:** https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
        
        return "\n".join(lines)
    
    def _run(self, query: str) -> str:
        """
        Execute PubMed search and return formatted results.
        
        Args:
            query: Search query string
            
        Returns:
            Formatted string with search results
        """
        if not query or not query.strip():
            return "Error: Empty search query"
        
        logger.info(f"Searching PubMed for: {query}")
        
        # Step 1: Search for articles
        pmids = self._esearch(query, retmax=self.max_results)
        
        if not pmids:
            return f"No articles found for query: {query}"
        
        # Step 2: Get summaries for the found articles
        summaries = self._esummary(pmids[:self.max_results])
        
        if not summaries:
            return f"Found {len(pmids)} articles but could not retrieve summaries."
        
        # Step 3: Format results
        formatted_results = []
        formatted_results.append(f"Found {len(summaries)} article(s) for query: {query}\n")
        
        for i, article in enumerate(summaries, 1):
            formatted_results.append(f"### Article {i}\n")
            formatted_results.append(self._format_result(article))
            formatted_results.append("")  # Empty line between articles
        
        return "\n".join(formatted_results)
    
    async def _arun(self, query: str) -> str:
        """Async version - not implemented, falls back to sync."""
        return self._run(query)


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

import logging
import os
import time
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

import httpx
from langchain_core.tools import BaseTool
from pydantic import Field

logger = logging.getLogger(__name__)

# NCBI E-utilities base URL
EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Default rate limiting per NCBI guidelines (requests / second)
DEFAULT_DELAY_SECONDS = 0.35  # ~3 req/sec
API_KEY_DELAY_SECONDS = 0.12  # ~8-10 req/sec (with api_key)


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
    tool_name: str = Field(default="deerflow_pubmed", description="NCBI API 'tool' identifier")
    
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
        self._request_delay = API_KEY_DELAY_SECONDS if self.api_key else DEFAULT_DELAY_SECONDS
    
    def _make_params(self, overrides: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        params: Dict[str, str] = {
            "db": "pubmed",
            "tool": self.tool_name,
        }
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key
        if overrides:
            params.update(overrides)
        return params
    
    def _request_json(self, endpoint: str, params: Dict[str, str]) -> Dict:
        url = f"{EUTILS_BASE_URL}/{endpoint}"
        final_params = self._make_params(params)
        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.get(url, params=final_params)
                response.raise_for_status()
                return response.json()
        finally:
            time.sleep(self._request_delay)

    def _request_text(self, endpoint: str, params: Dict[str, str]) -> str:
        url = f"{EUTILS_BASE_URL}/{endpoint}"
        final_params = self._make_params(params)
        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.get(url, params=final_params)
                response.raise_for_status()
                return response.text
        finally:
            time.sleep(self._request_delay)
    
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
            "term": query,
            "retmax": min(retmax, 200),
            "retmode": "json",
            "usehistory": "y",
        }
        
        try:
            logger.debug("ESearch params: %s", params)
            result = self._request_json("esearch.fcgi", params)
            if "esearchresult" in result:
                pmids = result["esearchresult"].get("idlist", [])
                logger.info("ESearch found %d articles for query: %s", len(pmids), query)
                return pmids
            logger.warning("Unexpected ESearch response structure: %s", result)
            return []
        except Exception as e:
            logger.error(f"Error in ESearch: {e}")
            return []
    
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
            params = {
                "id": ",".join(batch_pmids),
                "retmode": "json",
                "version": "2.0",
            }
            
            try:
                logger.debug("ESummary request for %d PMIDs", len(batch_pmids))
                result = self._request_json("esummary.fcgi", params)
                if "result" in result:
                    summaries = []
                    for pmid in batch_pmids:
                        if pmid in result["result"]:
                            summaries.append(result["result"][pmid])
                    all_summaries.extend(summaries)
                else:
                    logger.warning("Unexpected ESummary response structure")
            except Exception as e:
                logger.error("Error in ESummary: %s", e)
        
        return all_summaries
    
    def _efetch_abstracts(self, pmids: List[str]) -> Dict[str, str]:
        """
        Retrieve abstracts via EFetch (XML) to supplement ESummary output.
        """
        if not pmids:
            return {}
        
        params = {
            "id": ",".join(pmids),
            "retmode": "xml",
            "rettype": "abstract",
        }
        
        try:
            xml_text = self._request_text("efetch.fcgi", params)
        except Exception as exc:
            logger.error("Error in EFetch: %s", exc)
            return {}
        
        abstracts: Dict[str, str] = {}
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as parse_err:
            logger.warning("Failed to parse EFetch XML: %s", parse_err)
            return {}
        
        for article in root.findall(".//PubmedArticle"):
            pmid_elem = article.find(".//PMID")
            if pmid_elem is None or not pmid_elem.text:
                continue
            pmid = pmid_elem.text.strip()
            abstract_texts = []
            for abstract_node in article.findall(".//AbstractText"):
                text = (abstract_node.text or "").strip()
                label = abstract_node.attrib.get("Label")
                if label:
                    abstract_texts.append(f"{label}: {text}" if text else label)
                else:
                    abstract_texts.append(text)
            abstract = " ".join(filter(None, abstract_texts)).strip()
            if abstract:
                abstracts[pmid] = abstract
        
        return abstracts
    
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
        
        # Limit to configured max results for downstream calls
        top_pmids = pmids[: self.max_results]
        
        # Step 2: Get summaries for the found articles
        summaries = self._esummary(top_pmids)
        
        if not summaries:
            return (
                f"Found {len(pmids)} article(s) on PubMed but could not retrieve summaries. "
                "Please check server logs for details."
            )
        
        # Step 3: Fetch abstracts (ESummary doesn't include them)
        abstracts = self._efetch_abstracts([summary.get("uid", "") for summary in summaries if summary.get("uid")])
        for summary in summaries:
            uid = summary.get("uid")
            if uid and uid in abstracts:
                summary["abstract"] = abstracts[uid]
        
        # Step 4: Format results
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


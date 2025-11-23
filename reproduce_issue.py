
import sys
from unittest.mock import MagicMock

# Mock missing dependencies
sys.modules["langchain_mcp_adapters"] = MagicMock()
sys.modules["langchain_mcp_adapters.client"] = MagicMock()
sys.modules["markdownify"] = MagicMock()
sys.modules["readabilipy"] = MagicMock()
sys.modules["playwright"] = MagicMock()
sys.modules["playwright.async_api"] = MagicMock()
sys.modules["langchain_experimental"] = MagicMock()
sys.modules["langchain_experimental.utilities"] = MagicMock()
sys.modules["langchain_tavily"] = MagicMock()
sys.modules["langchain_tavily._utilities"] = MagicMock()
sys.modules["langchain_tavily.tavily_search"] = MagicMock()
sys.modules["langchain.callbacks"] = MagicMock()
sys.modules["langchain.callbacks.manager"] = MagicMock()

# Fix for Pydantic ForwardRef issue with MagicMock
# We need to make sure that when Pydantic evaluates types, it doesn't crash on MagicMock
# This is hard to patch globally.
# Instead, let's try to patch the specific imports in src.tools.tavily_search

import asyncio
import logging
import os
from unittest.mock import patch

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

# Now import the modules that use the mocked dependencies
from src.config.configuration import Configuration
from src.graph.nodes import researcher_node
from src.rag.retriever import Resource

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_researcher_node_data_sources():
    print("Starting test_researcher_node_data_sources...")
    
    # Mock state
    state = {
        "messages": [HumanMessage(content="test query")],
        "resources": [Resource(uri="mongodb://test/test", title="test", description="test")],
        "locale": "en-US"
    }
    
    # Mock config with ONLY mongodb selected
    config = RunnableConfig(
        configurable={
            "data_sources": ["mongodb"],
            "max_search_results": 3,
            "resources": [Resource(uri="mongodb://test/test", title="test", description="test")]
        }
    )
    
    # Mock dependencies
    with patch("src.graph.nodes.get_web_search_tool") as mock_get_web_search, \
         patch("src.graph.nodes.crawl_tool") as mock_crawl_tool, \
         patch("src.graph.nodes.get_retriever_tool") as mock_get_retriever_tool, \
         patch("src.graph.nodes._setup_and_execute_agent_step") as mock_execute:
        
        # Setup mock return values
        mock_retriever_tool = MagicMock()
        mock_retriever_tool.name = "local_search_tool"
        mock_get_retriever_tool.return_value = mock_retriever_tool
        
        # Execute researcher node
        await researcher_node(state, config)
        
        # Verify tools passed to execute
        if mock_execute.called:
            args, _ = mock_execute.call_args
            tools = args[3] # tools is the 4th argument
            
            print(f"Tools passed to agent: {[t.name for t in tools]}")
            
            # Check if web search tool was created
            if mock_get_web_search.called:
                print("FAIL: get_web_search_tool was called!")
            else:
                print("PASS: get_web_search_tool was NOT called.")
                
            # Check if crawl_tool was used
            if mock_crawl_tool in tools:
                 print("FAIL: crawl_tool is in tools list!")
            else:
                 print("PASS: crawl_tool is NOT in tools list.")

            # Check if retriever tool is in tools
            if mock_retriever_tool in tools:
                print("PASS: retriever tool is in tools list.")
            else:
                print("FAIL: retriever tool is NOT in tools list.")
        else:
            print("FAIL: _setup_and_execute_agent_step was NOT called.")

if __name__ == "__main__":
    asyncio.run(test_researcher_node_data_sources())

#!/usr/bin/env python3
"""
MCP Research Service for AI Debate Club

This service provides research tools for debate agents, including web search
capabilities to find real-time evidence and data to support arguments.
"""

import asyncio
import logging
from typing import List, Dict, Any
import json

try:
    from fastmcp import FastMCP
    from duckduckgo_search import DDGS
    MCP_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: MCP dependencies not installed: {e}")
    print("INSTALL: For full functionality, install: pip install fastmcp duckduckgo-search mcp")
    print("CONTINUING: Using mock implementation for development...")
    MCP_AVAILABLE = False
    
    # Mock FastMCP for development
    class MockFastMCP:
        def __init__(self, name):
            self.name = name
            self.tools = []
        
        def tool(self):
            def decorator(func):
                self.tools.append(func)
                return func
            return decorator
        
        async def run(self):
            print(f"Mock MCP server '{self.name}' running with {len(self.tools)} tools")
            # Keep running for testing
            while True:
                await asyncio.sleep(1)
    
    FastMCP = MockFastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastMCP server
mcp = FastMCP("research_tools")

@mcp.tool()
async def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web for information relevant to a debate topic.
    
    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        A formatted string containing search results with titles, snippets, and sources
    """
    try:
        logger.info(f"Performing web search for: {query}")
        
        if not MCP_AVAILABLE:
            # Mock search results for development/testing
            mock_results = [
                {
                    'title': f'Sample Result 1 for "{query}"',
                    'body': f'This is a mock search result demonstrating how web search would work for the query "{query}". In a real implementation, this would contain actual web search results.',
                    'href': 'https://example.com/result1'
                },
                {
                    'title': f'Mock Data Source for {query}',
                    'body': f'Mock statistical data and evidence related to {query}. This would be replaced with real search results when MCP dependencies are installed.',
                    'href': 'https://example.com/result2'
                }
            ]
            results = mock_results[:max_results]
        else:
            # Use DuckDuckGo search (no API key required, privacy-focused)
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
        
        if not results:
            return f"No search results found for query: '{query}'"
        
        # Format results for debate context
        formatted_results = []
        formatted_results.append(f"SEARCH RESULTS for: '{query}'")
        formatted_results.append("=" * 60)
        
        for i, result in enumerate(results, 1):
            title = result.get('title', 'No title')
            snippet = result.get('body', 'No description')
            url = result.get('href', 'No URL')
            
            # Truncate long snippets for readability
            if len(snippet) > 200:
                snippet = snippet[:197] + "..."
            
            formatted_results.append(f"\n{i}. **{title}**")
            formatted_results.append(f"   {snippet}")
            formatted_results.append(f"   Source: {url}")
        
        formatted_results.append(f"\nFOUND: {len(results)} relevant sources")
        return "\n".join(formatted_results)
        
    except Exception as e:
        error_msg = f"Web search failed for query '{query}': {str(e)}"
        logger.error(error_msg)
        return f"ERROR: {error_msg}"

@mcp.tool()
async def search_statistics(topic: str) -> str:
    """
    Search for statistics and data related to a debate topic.
    
    Args:
        topic: The topic to search for statistical data
    
    Returns:
        Formatted statistical information and data points
    """
    try:
        # Create a more specific query for statistics
        stats_query = f"{topic} statistics data facts figures research study"
        
        logger.info(f"Searching for statistics on: {topic}")
        
        with DDGS() as ddgs:
            results = list(ddgs.text(stats_query, max_results=4))
        
        if not results:
            return f"No statistical data found for topic: '{topic}'"
        
        # Format statistical results
        formatted_stats = []
        formatted_stats.append(f"STATISTICAL DATA for: '{topic}'")
        formatted_stats.append("=" * 50)
        
        for i, result in enumerate(results, 1):
            title = result.get('title', 'No title')
            snippet = result.get('body', 'No description')
            url = result.get('href', 'No URL')
            
            # Look for numerical data in snippets
            if any(char.isdigit() for char in snippet):
                if len(snippet) > 250:
                    snippet = snippet[:247] + "..."
                
                formatted_stats.append(f"\n{i}. **{title}**")
                formatted_stats.append(f"   {snippet}")
                formatted_stats.append(f"   Source: {url}")
        
        if len(formatted_stats) == 2:  # Only header added
            formatted_stats.append(f"\nWARNING: Limited statistical data found. Try searching with web_search tool for general information.")
        
        return "\n".join(formatted_stats)
        
    except Exception as e:
        error_msg = f"Statistics search failed for topic '{topic}': {str(e)}"
        logger.error(error_msg)
        return f"ERROR: {error_msg}"

@mcp.tool()
async def fact_check(claim: str) -> str:
    """
    Search for fact-checking information about a specific claim.
    
    Args:
        claim: The claim to fact-check
    
    Returns:
        Fact-checking information and verification sources
    """
    try:
        # Create fact-checking specific query
        fact_query = f'"{claim}" fact check verification truth snopes politifact'
        
        logger.info(f"Fact-checking claim: {claim}")
        
        with DDGS() as ddgs:
            results = list(ddgs.text(fact_query, max_results=3))
        
        if not results:
            return f"No fact-checking sources found for claim: '{claim}'"
        
        # Format fact-check results
        formatted_check = []
        formatted_check.append(f"FACT-CHECK RESULTS for: '{claim}'")
        formatted_check.append("=" * 55)
        
        for i, result in enumerate(results, 1):
            title = result.get('title', 'No title')
            snippet = result.get('body', 'No description')
            url = result.get('href', 'No URL')
            
            if len(snippet) > 300:
                snippet = snippet[:297] + "..."
            
            formatted_check.append(f"\n{i}. **{title}**")
            formatted_check.append(f"   {snippet}")
            formatted_check.append(f"   Source: {url}")
        
        formatted_check.append(f"\nREVIEW: Check these sources carefully for verification")
        return "\n".join(formatted_check)
        
    except Exception as e:
        error_msg = f"Fact-checking failed for claim '{claim}': {str(e)}"
        logger.error(error_msg)
        return f"ERROR: {error_msg}"

@mcp.tool()
async def ping() -> str:
    """
    Simple ping tool to test MCP service connectivity.
    
    Returns:
        A simple pong response
    """
    logger.info("Ping received")
    return "PONG - Research service is running!"

async def main():
    """Run the MCP research service"""
    logger.info("STARTING: AI Debate Club Research Service")
    logger.info("Available tools: web_search, search_statistics, fact_check, ping")
    
    # Run the FastMCP server
    await mcp.run()

if __name__ == "__main__":
    asyncio.run(main())
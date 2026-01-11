#!/usr/bin/env python3
"""
Main entry point for MEDKG MCP Server

Run with: python main.py
"""

import asyncio
import logging
from typing import Any, Sequence

# MCP SDK imports (adjust based on your MCP library)
try:
    from mcp import Server
    from mcp.types import Resource, Tool
except ImportError:
    print("Warning: MCP library not installed. Install with: pip install mcp")
    print("This is a placeholder for MCP server integration.")
    Server = None

from medkg.server import MEDKGServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize the MEDKG server
medkg_server = MEDKGServer()


async def handle_search_pubmed(arguments: dict) -> list[dict]:
    """Handle PubMed search request."""
    query = arguments.get("query", "")
    max_results = arguments.get("max_results", 20)
    full_text_only = arguments.get("full_text_only", False)
    start_date = arguments.get("start_date")
    end_date = arguments.get("end_date")
    use_smart_query = arguments.get("use_smart_query", True)
    
    result = medkg_server.search_pubmed(
        query=query,
        max_results=max_results,
        full_text_only=full_text_only,
        start_date=start_date,
        end_date=end_date,
        use_smart_query=use_smart_query,
    )
    
    return result.get("results", [])


async def handle_get_graph_summary(arguments: dict) -> dict:
    """Handle graph summary request."""
    return medkg_server.get_graph_summary()


async def handle_search_umls(arguments: dict) -> list[dict]:
    """Handle UMLS search request."""
    term = arguments.get("term", "")
    max_results = arguments.get("max_results", 10)
    filter_semantic_types = arguments.get("filter_semantic_types", False)
    threshold = arguments.get("threshold")
    
    result = medkg_server.search_umls(
        term=term,
        max_results=max_results,
        filter_semantic_types=filter_semantic_types,
        threshold=threshold,
    )
    
    return result.get("results", [])


async def handle_get_umls_concept(arguments: dict) -> dict:
    """Handle UMLS concept lookup request."""
    cui = arguments.get("cui", "")
    return medkg_server.get_umls_concept(cui)


def main():
    """Main entry point."""
    if Server is None:
        print("MCP Server library not available.")
        print("This is a placeholder implementation.")
        print("\nTo run the server properly, install MCP SDK:")
        print("  pip install mcp")
        return
    
    # Create MCP server instance
    server = Server("medkg")
    
    # Register tools
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="search_pubmed",
                description=(
                    "Search PubMed for research papers. For best results, use specific medical terms "
                    "found via search_umls first. Supports date filtering for finding latest research "
                    "(e.g., 'latest treatments for X'). The smart query builder (default: enabled) "
                    "automatically converts natural language to optimized PubMed queries using UMLS/MeSH."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query (natural language or PubMed query string)"},
                        "max_results": {"type": "integer", "default": 20, "description": "Maximum number of results"},
                        "full_text_only": {"type": "boolean", "default": False, "description": "Filter to articles with full-text availability"},
                        "start_date": {"type": "string", "description": "Start date for filtering (YYYY/MM/DD, YYYY/MM, or YYYY)"},
                        "end_date": {"type": "string", "description": "End date for filtering (YYYY/MM/DD, YYYY/MM, or YYYY)"},
                        "use_smart_query": {"type": "boolean", "default": True, "description": "Use smart query builder (UMLS/MeSH conversion)"},
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="search_umls",
                description=(
                    "Search UMLS (Unified Medical Language System) for concept standardization and terminology lookup. "
                    "Use this to find standardized CUIs for medical concepts before searching PubMed. "
                    "The filter_semantic_types option (when enabled) restricts results to semantic types relevant to "
                    "neurovascular research (diseases, biological processes, molecular entities, anatomical structures, biomarkers). "
                    "This allows filtering by concept type (e.g., 'Find me drugs named X' vs 'Find me diseases named X')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "term": {"type": "string", "description": "Medical concept term to search for (e.g., 'intracranial aneurysm', 'inflammation')"},
                        "max_results": {"type": "integer", "default": 10, "description": "Maximum number of results to return"},
                        "filter_semantic_types": {
                            "type": "boolean",
                            "default": False,
                            "description": (
                                "If true, only return concepts with allowed semantic types "
                                "(T047: Disease, T039: Physiologic Function, T116: Protein, T023: Body Part, etc.). "
                                "Useful for filtering by concept type (diseases vs drugs vs anatomical structures)."
                            ),
                        },
                        "threshold": {"type": "number", "default": None, "description": "Minimum relevance score threshold (0.0-1.0). Higher values return more precise matches."},
                    },
                    "required": ["term"],
                },
            ),
            Tool(
                name="get_umls_concept",
                description=(
                    "Get detailed information about a UMLS concept by CUI (Concept Unique Identifier). "
                    "Returns definitions, semantic types, MeSH terms, and relations (parents/children) "
                    "which are essential for understanding concept hierarchies and building the knowledge graph. "
                    "Use this after search_umls to get full concept details including graph relationships."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "cui": {"type": "string", "description": "UMLS CUI (e.g., 'C0000001'). Get this from search_umls results."},
                    },
                    "required": ["cui"],
                },
            ),
            Tool(
                name="get_graph_summary",
                description="Get summary of the knowledge graph",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[dict]:
        if name == "search_pubmed":
            return await handle_search_pubmed(arguments)
        elif name == "search_umls":
            return await handle_search_umls(arguments)
        elif name == "get_umls_concept":
            return [await handle_get_umls_concept(arguments)]
        elif name == "get_graph_summary":
            return [await handle_get_graph_summary(arguments)]
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    # Run server (this will depend on your MCP library implementation)
    logger.info("Starting MEDKG MCP Server...")
    # server.run()  # Adjust based on your MCP library


if __name__ == "__main__":
    main()

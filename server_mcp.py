#!/usr/bin/env python3
"""
MCP Server for MEDKG - Compatible with MCP Inspector

Run with: npx @modelcontextprotocol/inspector python server_mcp.py
"""

import asyncio
import json
import logging
import sys
from typing import Any, Sequence

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("Error: MCP SDK not installed. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

from medkg.server import MEDKGServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the MEDKG server
medkg_server = MEDKGServer()

# Create MCP server instance
server = Server("medkg")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List all available tools."""
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
                    "threshold": {"type": "number", "description": "Minimum relevance score threshold (0.0-1.0). Higher values return more precise matches. Optional - if not provided, all results are returned."},
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
            name="query_patient_data",
            description="Query patient or aneurysm-level data using structured filters and controlled column access. Supports precise ID lookups, range filters, and column grouping.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "object",
                        "description": "Optional: Direct lookup for a specific entity (e.g., patient 119). If provided, both type and id should be specified.",
                        "properties": {
                            "type": {"type": "string", "enum": ["case", "aneurysm"]},
                            "id": {"type": ["string", "number"]}
                        }
                    },
                    "filters": {
                        "type": "array",
                        "description": "List of filtering conditions (AND logic)",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string"},
                                "operator": {"type": "string", "enum": ["==", "!=", "<", ">", "<=", ">=", "in", "contains", "between"]},
                                "value": {}, 
                                "value_type": {
                                    "type": "string", 
                                    "enum": ["numeric", "categorical", "boolean", "range"],
                                    "description": "Helps cast the value correctly before filtering"
                                }
                            },
                            "required": ["column", "operator", "value"]
                        }
                    },
                    "select": {
                        "type": "object",
                        "description": "Columns to return. Can specify groups (from metadata) or specific column names.",
                        "properties": {
                            "groups": {"type": "array", "items": {"type": "string"}},
                            "columns": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": []
                    },
                    "limit": {"type": "integer", "default": 1000}
                },
                "required": ["select"]
            }
        ),
        # Tool(
        #     name="get_graph_summary",
        #     description="Get summary of the knowledge graph",
        #     inputSchema={"type": "object", "properties": {}},
        # ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "search_pubmed":
            query = arguments.get("query", "")
            if not query:
                raise ValueError("query parameter is required")
            
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
            
            # Handle both dict (return_query=True) and list responses
            if isinstance(result, dict):
                results_data = result.get("results", [])
            else:
                results_data = result if isinstance(result, list) else []
            
            return [TextContent(
                type="text",
                text=json.dumps(results_data, indent=2, default=str)
            )]
        
        elif name == "search_umls":
            term = arguments.get("term", "")
            if not term:
                raise ValueError("term parameter is required")
            
            max_results = arguments.get("max_results", 10)
            filter_semantic_types = arguments.get("filter_semantic_types", False)
            threshold = arguments.get("threshold")
            
            result = medkg_server.search_umls(
                term=term,
                max_results=max_results,
                filter_semantic_types=filter_semantic_types,
                threshold=threshold,
            )
            
            # Handle both dict and list responses
            if isinstance(result, dict):
                results_data = result.get("results", [])
            else:
                results_data = result if isinstance(result, list) else []
            
            return [TextContent(
                type="text",
                text=json.dumps(results_data, indent=2, default=str)
            )]
        
        elif name == "get_umls_concept":
            cui = arguments.get("cui", "")
            if not cui:
                raise ValueError("cui parameter is required")
            
            result = medkg_server.get_umls_concept(cui)
            
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2, default=str)
            )]

        elif name == "query_patient_data":
            select = arguments.get("select", {})
            if not select:
                raise ValueError("select parameter is required")
                
            entity = arguments.get("entity")
            filters = arguments.get("filters")
            limit = arguments.get("limit", 100)
            
            result = medkg_server.query_patient_data(
                select=select,
                entity=entity,
                filters=filters,
                limit=limit
            )
            
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2, default=str)
            )]
        
        elif name == "get_graph_summary":
            result = medkg_server.get_graph_summary()
            
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2, default=str)
            )]
        
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    except Exception as e:
        logger.error(f"Error calling tool {name}: {e}", exc_info=True)
        error_msg = str(e)
        try:
            error_json = json.dumps({"error": error_msg, "tool": name}, indent=2)
        except Exception:
            error_json = json.dumps({"error": "An error occurred", "tool": name}, indent=2)
        return [TextContent(
            type="text",
            text=error_json
        )]


async def main():
    """Main entry point for the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

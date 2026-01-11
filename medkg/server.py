"""
MCP Server for Medical Knowledge Graph

Model Context Protocol server that provides access to:
- Graph operations (nodes, edges, queries)
- PubMed search
- UMLS validation
"""

from typing import Any, Dict, List, Optional
import logging

from medkg.graph import GraphStore
from medkg.api.umls_client import UMLSAPIClient
from medkg.api.pubmed_client import PubMedAPIClient

logger = logging.getLogger(__name__)


class MEDKGServer:
    """
    MCP Server for Medical Knowledge Graph operations.
    """
    
    def __init__(self):
        """Initialize the MCP server with graph store and API clients."""
        self.graph = GraphStore()
        self.umls_client = UMLSAPIClient()
        self.pubmed_client = PubMedAPIClient()
    
    def search_pubmed(
        self,
        query: str,
        max_results: int = 20,
        full_text_only: bool = False,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        use_smart_query: bool = True,
    ) -> Dict[str, Any]:
        """
        Search PubMed with optional date filtering.
        
        Args:
            query: Search query (natural language or PubMed query string)
            max_results: Maximum number of results
            full_text_only: Filter to articles with full-text signal
            start_date: Start date for filtering (YYYY/MM/DD, YYYY/MM, or YYYY)
            end_date: End date for filtering (YYYY/MM/DD, YYYY/MM, or YYYY)
            use_smart_query: If True, use smart query builder (UMLS/MeSH)
        
        Returns:
            Dictionary with 'results' key containing list of articles
        """
        return self.pubmed_client.search(
            query=query,
            max_results=max_results,
            full_text_only=full_text_only,
            start_date=start_date,
            end_date=end_date,
            use_smart_query=use_smart_query,
            return_query=True,
        )
    
    def get_graph_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current graph state.
        
        Returns:
            Dictionary with graph statistics
        """
        return {
            'num_nodes': len(self.graph.nodes),
            'num_edges': len(self.graph.edges),
            'seed_nodes': [n.node_id for n in self.graph.nodes.values() if n.is_seed],
        }
    
    def validate_node_with_umls(self, node_id: str, umls_cui: str) -> bool:
        """
        Validate a node with UMLS CUI.
        
        Args:
            node_id: Node identifier
            umls_cui: UMLS CUI to associate
        
        Returns:
            True if validation successful
        """
        try:
            self.graph.validate_with_umls(node_id, umls_cui)
            return True
        except Exception as e:
            logger.error(f"UMLS validation failed: {e}")
            return False

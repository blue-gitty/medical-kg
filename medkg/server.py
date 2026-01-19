"""
MCP Server for Medical Knowledge Graph

Model Context Protocol server that provides access to:
- Graph operations (nodes, edges, queries)
- PubMed search
- UMLS lookup and validation
"""

from typing import Any, Dict, List, Optional
import logging

from medkg.graph import GraphStore
from medkg.api.umls_client import UMLSAPIClient
from medkg.api.pubmed_client import PubMedAPIClient
from medkg.api.patient_query_engine import PatientQueryEngine

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
        self.patient_engine = PatientQueryEngine()
    
    def query_patient_data(
        self,
        select: Dict[str, List[str]],
        entity: Optional[Dict[str, Any]] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Query patient data using the PatientQueryEngine.
        """
        return self.patient_engine.query_patient_data(
            select=select,
            entity=entity,
            filters=filters,
            limit=limit
        )
    
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
    
    def search_umls(
        self,
        term: str,
        max_results: int = 10,
        filter_semantic_types: bool = False,
        threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Search UMLS for concepts matching a term.
        
        Useful for standardizing medical concepts and understanding terminology.
        Use this before searching PubMed to get standardized CUIs for medical terms.
        
        Args:
            term: Search term (medical concept name, e.g., "intracranial aneurysm")
            max_results: Maximum number of results to return
            filter_semantic_types: If True, only return concepts with allowed semantic types
                (T047: Disease, T039: Physiologic Function, T116: Protein, T023: Body Part, etc.)
                Useful for filtering by concept type (diseases vs drugs vs anatomical structures)
            threshold: Minimum score threshold (0.0-1.0). If None, returns all results.
                Higher values return more precise matches.
        
        Returns:
            Dictionary with 'results' key containing list of UMLS concepts
        """
        try:
            if filter_semantic_types or threshold is not None:
                # Use search_best_match for filtered/scored results
                # Get multiple results by using search_with_scores and filtering
                results = self.umls_client.search_with_scores(
                    term=term,
                    page_size=max(max_results, 25),
                    search_type="words",
                )
                
                filtered_results = []
                for result in results:
                    if threshold is not None and result['combined_score'] < threshold:
                        continue
                    
                    cui = result.get('cui')
                    if not cui:
                        continue
                    
                    # Get concept details for semantic types
                    details = self.umls_client.get_concept_details(cui)
                    if details:
                        semantic_types = details.get('semantic_types', [])
                        result['semantic_types'] = semantic_types
                        result['semantic_type_names'] = [
                            st['name'] for st in semantic_types if st.get('name')
                        ]
                        result['semantic_type_tuis'] = [
                            st['tui'] for st in semantic_types if st.get('tui')
                        ]
                        
                        if filter_semantic_types:
                            # Check if has allowed semantic type
                            if not self.umls_client._has_allowed_semantic_type(semantic_types):
                                continue
                    
                    # Get MeSH term if available
                    mesh_term = self.umls_client.get_mesh_for_cui(cui)
                    if mesh_term:
                        result['mesh_term'] = mesh_term
                    
                    filtered_results.append(result)
                    
                    if len(filtered_results) >= max_results:
                        break
                
                return {
                    'term': term,
                    'results': filtered_results[:max_results],
                    'total': len(filtered_results),
                }
            else:
                # Simple search without filtering
                results = self.umls_client.search_with_scores(
                    term=term,
                    page_size=max_results,
                    search_type="words",
                )
                
                return {
                    'term': term,
                    'results': results[:max_results],
                    'total': len(results),
                }
        except Exception as e:
            logger.error(f"UMLS search failed: {e}")
            return {
                'term': term,
                'results': [],
                'total': 0,
                'error': str(e),
            }
    
    def get_umls_concept(self, cui: str) -> Dict[str, Any]:
        """
        Get detailed information about a UMLS concept by CUI.
        
        This is essential for the knowledge graph: returns definitions and relations
        (parents/children) that help understand concept hierarchies and relationships.
        
        Args:
            cui: UMLS Concept Unique Identifier (e.g., "C0000001")
        
        Returns:
            Dictionary with concept details including semantic types, definitions,
            relations (parents/children), and MeSH terms.
        """
        try:
            details = self.umls_client.get_concept_details(cui)
            if not details or not isinstance(details, dict):
                return {
                    'cui': cui,
                    'error': 'Concept not found',
                }
            
            # Get additional information
            mesh_term = self.umls_client.get_mesh_for_cui(cui)
            definitions_response = self.umls_client.get_cui_definitions(cui, page_size=5)
            definitions = []
            if isinstance(definitions_response, dict) and definitions_response.get('result'):
                result = definitions_response['result']
                if isinstance(result, dict):
                    defs = result.get('definitions', [])
                    if isinstance(defs, list):
                        definitions = [d.get('value', '') for d in defs[:5] if isinstance(d, dict) and d.get('value')]
            
            # Get relations (parents/children) for graph construction
            relations_response = self.umls_client.get_cui_relations(cui, page_size=50)
            relations = []
            parents = []
            children = []
            
            try:
                if isinstance(relations_response, dict) and relations_response.get('result'):
                    result = relations_response['result']
                    if isinstance(result, dict):
                        rels = result.get('relations', [])
                        if isinstance(rels, list):
                            for rel in rels[:50]:
                                if not isinstance(rel, dict):
                                    continue
                            rel_type = rel.get('relationLabel', '') or rel.get('relation', '')
                            
                            # Extract related CUI from URI (format: /content/{version}/CUI/{CUI})
                            related_uri = rel.get('relatedIdName', '') or rel.get('relatedId', '') or rel.get('uri', '')
                            related_cui = ''
                            if related_uri:
                                # Extract CUI from URI (e.g., "/content/current/CUI/C0000001" -> "C0000001")
                                parts = related_uri.split('/')
                                if 'CUI' in parts:
                                    idx = parts.index('CUI')
                                    if idx + 1 < len(parts):
                                        related_cui = parts[idx + 1]
                            
                            # Get related name if available
                            related_name = rel.get('relatedIdName', '') or rel.get('additionalRelationLabel', '') or ''
                            
                            relation_info = {
                                'relation_type': rel_type,
                                'related_cui': related_cui,
                                'related_name': related_name,
                            }
                            relations.append(relation_info)
                            
                            # Categorize as parent or child based on relation type
                            # Common parent relations: "CHD" (has child), "RB" (broader), "PAR" (parent)
                            # Common child relations: "RN" (narrower), "CHD" (child)
                            rel_type_upper = rel_type.upper()
                            if any(x in rel_type_upper for x in ['CHD', 'HAS_CHILD', 'BROADER', 'PAR', 'RB']):
                                parents.append(relation_info)
                            elif any(x in rel_type_upper for x in ['RN', 'NARROWER', 'IS_CHILD', 'CHILD']):
                                children.append(relation_info)
            except Exception as rel_error:
                logger.warning(f"Error parsing relations for {cui}: {rel_error}")
                # Continue without relations rather than failing
            
            return {
                'cui': cui,
                'semantic_types': details.get('semantic_types', []),
                'semantic_type_names': [
                    st['name'] for st in details.get('semantic_types', []) if st.get('name')
                ],
                'semantic_type_tuis': [
                    st['tui'] for st in details.get('semantic_types', []) if st.get('tui')
                ],
                'mesh_term': mesh_term,
                'definitions': definitions,
                'relations': relations,
                'parents': parents,
                'children': children,
                'info': details.get('info', {}),
            }
        except Exception as e:
            logger.error(f"Error getting UMLS concept {cui}: {e}")
            return {
                'cui': cui,
                'error': str(e),
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

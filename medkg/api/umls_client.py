"""
Comprehensive UMLS API Client
Implements all UMLS REST API endpoints for accessing the Metathesaurus
"""
import os
import json
import requests
import logging
from difflib import SequenceMatcher
from dotenv import load_dotenv
from typing import Dict, List, Optional, Any, Set

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Allowed semantic types for filtering
ALLOWED_SEMANTIC_TYPES: Set[str] = {
    'T047', 'T046', 'T049', 'T039', 'T040', 'T042', 'T043',
    'T116', 'T129', 'T023', 'T024', 'T030', 'T029', 'T190',
    'T037', 'T034', 'T201'
}


def compute_similarity_score(search_term: str, result_name: str) -> float:
    """Compute string similarity score between search term and result."""
    search_lower = search_term.lower().strip()
    result_lower = result_name.lower().strip()
    
    if search_lower == result_lower:
        return 1.0
    
    base_score = SequenceMatcher(None, search_lower, result_lower).ratio()
    
    if search_lower in result_lower:
        base_score = min(1.0, base_score + 0.15)
    
    if result_lower in search_lower:
        base_score = min(1.0, base_score + 0.1)
    
    return round(base_score, 4)


class UMLSAPIClient:
    """Client for accessing UMLS REST API endpoints"""
    
    def __init__(self, version: str = "current"):
        """
        Initialize UMLS API Client
        
        Args:
            version: UMLS version (e.g., "current", "2025AB")
        """
        self.api_key = os.getenv('UMLS_API_KEY')
        if not self.api_key:
            raise ValueError("UMLS_API_KEY environment variable not set.")
        
        self.base_url = "https://uts-ws.nlm.nih.gov/rest"
        self.version = version
        self.session = requests.Session()
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a GET request to the UMLS API"""
        if params is None:
            params = {}
        params['apiKey'] = self.api_key
        
        url = f"{self.base_url}{endpoint}"
        response = self.session.get(url, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"API Error {response.status_code}: {response.text}")
    
    # ========== SEARCH ENDPOINTS ==========
    
    def search(self, term: str, partial_search: bool = True, page_size: int = 25, 
               page_number: int = 1, search_type: str = "words") -> Dict[str, Any]:
        """
        Search for CUIs by term or code
        
        Path: /search/{version}
        """
        endpoint = f"/search/{self.version}"
        params = {
            'string': term,
            'partialSearch': 'true' if partial_search else 'false',
            'searchType': search_type,
            'pageSize': page_size,
            'pageNumber': page_number
        }
        return self._make_request(endpoint, params)
    
    def search_with_scores(
        self, 
        term: str, 
        page_size: int = 25,
        search_type: str = "words",
        print_results: bool = False
    ) -> List[Dict[str, Any]]:
        """Search UMLS with computed relevance scores."""
        raw_response = self.search(
            term=term,
            page_size=page_size,
            search_type=search_type
        )
        
        results = raw_response.get('result', {}).get('results', [])
        scored_results = []
        
        for rank, result in enumerate(results, 1):
            name = result.get('name', '')
            cui = result.get('ui', '')
            root_source = result.get('rootSource', '')
            
            similarity = compute_similarity_score(term, name)
            position_score = 1.0 / (1 + 0.1 * (rank - 1))
            combined_score = (0.7 * similarity) + (0.3 * position_score)
            
            scored_results.append({
                'rank': rank,
                'cui': cui,
                'name': name,
                'root_source': root_source,
                'similarity_score': similarity,
                'position_score': round(position_score, 4),
                'combined_score': round(combined_score, 4),
                'uri': result.get('uri', '')
            })
        
        scored_results.sort(key=lambda x: x['combined_score'], reverse=True)
        return scored_results
    
    # ========== CONTENT ENDPOINTS ==========
    
    def get_cui_info(self, cui: str) -> Dict[str, Any]:
        """
        Retrieve information about a known CUI
        
        Path: /content/{version}/CUI/{CUI}
        """
        endpoint = f"/content/{self.version}/CUI/{cui}"
        return self._make_request(endpoint)
    
    def get_cui_atoms(self, cui: str, page_size: int = 25, page_number: int = 1) -> Dict[str, Any]:
        """
        Retrieve atoms and information about atoms for a known CUI
        
        Path: /content/{version}/CUI/{CUI}/atoms
        """
        endpoint = f"/content/{self.version}/CUI/{cui}/atoms"
        params = {
            'pageSize': page_size,
            'pageNumber': page_number
        }
        return self._make_request(endpoint, params)
    
    def get_cui_definitions(self, cui: str, page_size: int = 25, page_number: int = 1) -> Dict[str, Any]:
        """
        Retrieve definitions for a known CUI
        
        Path: /content/{version}/CUI/{CUI}/definitions
        """
        endpoint = f"/content/{self.version}/CUI/{cui}/definitions"
        params = {
            'pageSize': page_size,
            'pageNumber': page_number
        }
        return self._make_request(endpoint, params)
    
    def get_cui_relations(self, cui: str, page_size: int = 25, page_number: int = 1) -> Dict[str, Any]:
        """
        Retrieve NLM-asserted relationships for a known CUI
        
        Path: /content/{version}/CUI/{CUI}/relations
        """
        endpoint = f"/content/{self.version}/CUI/{cui}/relations"
        params = {
            'pageSize': page_size,
            'pageNumber': page_number
        }
        return self._make_request(endpoint, params)
    
    def get_concept_details(self, cui: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a concept including semantic types."""
        try:
            info = self.get_cui_info(cui)
            semantic_types = []
            if 'result' in info:
                result = info['result']
                if 'semanticTypes' in result:
                    for st in result['semanticTypes']:
                        tui = None
                        uri = st.get('uri', '')
                        if '/TUI/' in uri:
                            tui = uri.split('/TUI/')[-1]
                        semantic_types.append({
                            'tui': tui,
                            'name': st.get('name'),
                            'uri': uri
                        })
            return {
                'cui': cui,
                'info': info,
                'semantic_types': semantic_types
            }
        except Exception as e:
            logger.error(f"Error getting details for {cui}: {e}")
            return None
    
    def get_mesh_for_cui(self, cui: str) -> Optional[str]:
        """Get the MeSH (MSH) term for a given CUI."""
        try:
            atoms_response = self.get_cui_atoms(cui, page_size=50)
            
            if 'result' not in atoms_response:
                return None
            
            atoms = atoms_response.get('result', [])
            if isinstance(atoms, dict):
                atoms = atoms.get('results', [])
            
            mesh_terms = []
            for atom in atoms:
                root_source = atom.get('rootSource', '')
                if root_source == 'MSH':
                    term_type = atom.get('termType', '')
                    name = atom.get('name', '')
                    
                    mesh_terms.append({
                        'name': name,
                        'term_type': term_type,
                        'is_preferred': term_type in ['MH', 'NM', 'HT']
                    })
            
            if not mesh_terms:
                return None
            
            preferred = [m for m in mesh_terms if m['is_preferred']]
            if preferred:
                return preferred[0]['name']
            return mesh_terms[0]['name']
            
        except Exception as e:
            logger.warning(f"Error getting MeSH for {cui}: {e}")
            return None
    
    def _has_allowed_semantic_type(self, semantic_types: List[Dict]) -> bool:
        """Check if any semantic type TUI is in the allowed list."""
        for st in semantic_types:
            tui = st.get('tui')
            if tui and tui in ALLOWED_SEMANTIC_TYPES:
                return True
        return False
    
    def _filter_to_allowed_types(self, semantic_types: List[Dict]) -> List[Dict]:
        """Filter semantic types to only allowed ones."""
        return [st for st in semantic_types if st.get('tui') in ALLOWED_SEMANTIC_TYPES]
    
    def search_best_match(
        self, 
        term: str, 
        threshold: float = 0.6,
        filter_semantic_types: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get the best matching CUI for a term, filtered by allowed semantic types.
        
        Args:
            term: Search term
            threshold: Minimum score threshold (default: 0.6)
            filter_semantic_types: Only return if has allowed semantic type (default: True)
            
        Returns:
            Best matching result dict with semantic_types field, or None if no valid match
        """
        results = self.search_with_scores(term, page_size=25, print_results=False)
        
        if not results:
            return None
        
        for candidate in results:
            if candidate['combined_score'] < threshold:
                continue
            
            cui = candidate.get('cui')
            if not cui:
                continue
            
            details = self.get_concept_details(cui)
            if not details:
                continue
            
            semantic_types = details.get('semantic_types', [])
            
            if filter_semantic_types and not self._has_allowed_semantic_type(semantic_types):
                continue
            
            candidate['semantic_types'] = semantic_types
            candidate['semantic_type_names'] = [st['name'] for st in semantic_types if st.get('name')]
            candidate['semantic_type_tuis'] = [st['tui'] for st in semantic_types if st.get('tui')]
            
            allowed_types = self._filter_to_allowed_types(semantic_types)
            candidate['allowed_semantic_types'] = allowed_types
            candidate['allowed_type_names'] = [st['name'] for st in allowed_types if st.get('name')]
            candidate['allowed_type_tuis'] = [st['tui'] for st in allowed_types if st.get('tui')]
            
            mesh_term = self.get_mesh_for_cui(cui)
            candidate['mesh_term'] = mesh_term
            
            return candidate
        
        return None
    
    def get_source_info(self, source: str, source_id: str) -> Dict[str, Any]:
        """
        Retrieve information about a known source-asserted identifier
        
        Path: /content/{version}/source/{source}/{id}
        """
        endpoint = f"/content/{self.version}/source/{source}/{source_id}"
        return self._make_request(endpoint)
    
    def get_source_atoms(self, source: str, source_id: str, 
                        page_size: int = 25, page_number: int = 1) -> Dict[str, Any]:
        """
        Retrieve information about atoms for a known source-asserted identifier
        
        Path: /content/{version}/source/{source}/{id}/atoms
        """
        endpoint = f"/content/{self.version}/source/{source}/{source_id}/atoms"
        params = {
            'pageSize': page_size,
            'pageNumber': page_number
        }
        return self._make_request(endpoint, params)
    
    def get_source_parents(self, source: str, source_id: str, 
                          page_size: int = 25, page_number: int = 1) -> Dict[str, Any]:
        """
        Retrieve immediate parents of a source-asserted identifier
        
        Path: /content/{version}/source/{source}/{id}/parents
        """
        endpoint = f"/content/{self.version}/source/{source}/{source_id}/parents"
        params = {
            'pageSize': page_size,
            'pageNumber': page_number
        }
        return self._make_request(endpoint, params)
    
    def get_source_children(self, source: str, source_id: str, 
                           page_size: int = 25, page_number: int = 1) -> Dict[str, Any]:
        """
        Retrieve immediate children of a source-asserted identifier
        
        Path: /content/{version}/source/{source}/{id}/children
        """
        endpoint = f"/content/{self.version}/source/{source}/{source_id}/children"
        params = {
            'pageSize': page_size,
            'pageNumber': page_number
        }
        return self._make_request(endpoint, params)
    
    def get_source_ancestors(self, source: str, source_id: str, 
                            page_size: int = 25, page_number: int = 1) -> Dict[str, Any]:
        """
        Retrieve all ancestors of a source-asserted identifier
        
        Path: /content/{version}/source/{source}/{id}/ancestors
        """
        endpoint = f"/content/{self.version}/source/{source}/{source_id}/ancestors"
        params = {
            'pageSize': page_size,
            'pageNumber': page_number
        }
        return self._make_request(endpoint, params)
    
    def get_source_descendants(self, source: str, source_id: str, 
                              page_size: int = 25, page_number: int = 1) -> Dict[str, Any]:
        """
        Retrieve all descendants of a source-asserted identifier
        
        Path: /content/{version}/source/{source}/{id}/descendants
        """
        endpoint = f"/content/{self.version}/source/{source}/{source_id}/descendants"
        params = {
            'pageSize': page_size,
            'pageNumber': page_number
        }
        return self._make_request(endpoint, params)
    
    def get_source_relations(self, source: str, source_id: str, 
                            page_size: int = 25, page_number: int = 1) -> Dict[str, Any]:
        """
        Retrieve all relationships of a source-asserted identifier
        
        Path: /content/{version}/source/{source}/{id}/relations
        """
        endpoint = f"/content/{self.version}/source/{source}/{source_id}/relations"
        params = {
            'pageSize': page_size,
            'pageNumber': page_number
        }
        return self._make_request(endpoint, params)
    
    def get_source_attributes(self, source: str, source_id: str, 
                             page_size: int = 25, page_number: int = 1) -> Dict[str, Any]:
        """
        Retrieve information about source-asserted attributes
        
        Path: /content/{version}/source/{source}/{id}/attributes
        """
        endpoint = f"/content/{self.version}/source/{source}/{source_id}/attributes"
        params = {
            'pageSize': page_size,
            'pageNumber': page_number
        }
        return self._make_request(endpoint, params)
    
    # ========== SEMANTIC NETWORK ENDPOINTS ==========
    
    def get_all_semantic_types(self, page_size: int = 25, page_number: int = 1) -> Dict[str, Any]:
        """
        Retrieve all Semantic Types
        
        Path: /semantic-network/{version}/TUI
        """
        endpoint = f"/semantic-network/{self.version}/TUI"
        params = {
            'pageSize': page_size,
            'pageNumber': page_number
        }
        return self._make_request(endpoint, params)
    
    def get_semantic_type_info(self, tui: str) -> Dict[str, Any]:
        """
        Retrieve information for a known Semantic Type identifier (TUI)
        
        Path: /semantic-network/{version}/TUI/{id}
        """
        endpoint = f"/semantic-network/{self.version}/TUI/{tui}"
        return self._make_request(endpoint)
    
    def get_all_semantic_relations(self, page_size: int = 25, page_number: int = 1) -> Dict[str, Any]:
        """
        Retrieve all Semantic Relations
        
        Path: /semantic-network/{version}/REL
        """
        endpoint = f"/semantic-network/{self.version}/REL"
        params = {
            'pageSize': page_size,
            'pageNumber': page_number
        }
        return self._make_request(endpoint, params)
    
    # ========== CROSSWALK ENDPOINTS ==========
    
    def get_crosswalk(self, source: str, source_id: str, 
                     page_size: int = 25, page_number: int = 1) -> Dict[str, Any]:
        """
        Retrieve all source-asserted identifiers that share a UMLS CUI with a particular code
        
        Path: /crosswalk/{version}/source/{source}/{id}
        """
        endpoint = f"/crosswalk/{self.version}/source/{source}/{source_id}"
        params = {
            'pageSize': page_size,
            'pageNumber': page_number
        }
        return self._make_request(endpoint, params)
    
    # ========== HELPER METHODS ==========
    
    def get_all_pages(self, func, *args, **kwargs):
        """Helper to retrieve all pages of results"""
        all_results = []
        page_number = 1
        page_size = kwargs.get('page_size', 25)
        
        while True:
            kwargs['page_number'] = page_number
            result = func(*args, **kwargs)
            
            if 'result' in result:
                results = result['result'].get('results', [])
                if not results:
                    break
                all_results.extend(results)
                
                # Check if there are more pages
                if len(results) < page_size:
                    break
                page_number += 1
            else:
                break
        
        return all_results


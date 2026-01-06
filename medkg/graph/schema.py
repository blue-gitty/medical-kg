"""
Graph Schema and In-Memory Graph Store for Medical Knowledge Graph
Practical Entity Discovery Approach: Start with 3 seed entities, use UMLS for validation
"""
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
import json


# ========== GLOBAL CONSTRAINTS ==========
MAX_DEPTH = 2
MAX_NODES = 30
MIN_PUBMED_CITATIONS = 2


class ConstraintViolationError(Exception):
    """Raised when a global constraint is violated"""
    pass


# ========== SEED ENTITIES ==========
# Hardcoded, human-curated seed entities for the knowledge graph
SEED_ENTITIES = {
    'intracranial_aneurysm_rupture': {
        'label': 'Intracranial Aneurysm Rupture',
        'entity_type': 'Disease',
        'synonyms': ['Brain Aneurysm Rupture', 'Cerebral Aneurysm Rupture', 'Intracranial Aneurysm']
    },
    'inflammation': {
        'label': 'Inflammation',
        'entity_type': 'Biological Process',
        'synonyms': ['Inflammatory Response', 'Inflammatory Process']
    },
    'hemodynamics': {
        'label': 'Hemodynamics',
        'entity_type': 'Biomechanical',
        'synonyms': ['Blood Flow Dynamics', 'Hemodynamic Forces', 'Vascular Hemodynamics']
    }
}


# ========== NODE SCHEMA ==========
@dataclass
class Node:
    """
    Node schema for the knowledge graph
    
    Attributes:
        node_id: Unique identifier (human-readable, e.g., 'intracranial_aneurysm_rupture')
        label: Human-readable name
        entity_type: Type of entity (Disease, Biological Process, Biomechanical, etc.)
        synonyms: List of alternative names
        ontology_ref: UMLS CUI (validated via UMLS, not discovered)
        is_seed: Whether this is one of the 3 seed entities
    """
    node_id: str
    label: str
    entity_type: str
    synonyms: List[str] = field(default_factory=list)
    ontology_ref: Optional[str] = None  # UMLS CUI for validation
    is_seed: bool = False
    
    def __post_init__(self):
        """Validate node data"""
        if not self.node_id:
            raise ValueError("node_id cannot be empty")
        if not self.label:
            raise ValueError("label cannot be empty")
        if not self.entity_type:
            raise ValueError("entity_type cannot be empty")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary"""
        return {
            'node_id': self.node_id,
            'label': self.label,
            'entity_type': self.entity_type,
            'synonyms': self.synonyms,
            'ontology_ref': self.ontology_ref,
            'is_seed': self.is_seed
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Node':
        """Create node from dictionary"""
        return cls(
            node_id=data['node_id'],
            label=data['label'],
            entity_type=data['entity_type'],
            synonyms=data.get('synonyms', []),
            ontology_ref=data.get('ontology_ref'),
            is_seed=data.get('is_seed', False)
        )


# ========== EDGE SCHEMA ==========
@dataclass
class Evidence:
    """
    Evidence for an edge relationship
    
    Attributes:
        pubmed_id: PubMed article ID
        sentence: Relevant sentence from the article
    """
    pubmed_id: str
    sentence: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert evidence to dictionary"""
        return {
            'pubmed_id': self.pubmed_id,
            'sentence': self.sentence
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Evidence':
        """Create evidence from dictionary"""
        return cls(
            pubmed_id=data['pubmed_id'],
            sentence=data['sentence']
        )


@dataclass
class Edge:
    """
    Edge schema for the knowledge graph
    
    Attributes:
        source_node_id: Source node identifier
        target_node_id: Target node identifier
        relationship_type: Type of relationship (INFLUENCES, MECHANISTIC_LINK, etc.)
        evidence: List of evidence objects (PubMed IDs + sentences)
        confidence: Confidence score (0.0 to 1.0)
    """
    source_node_id: str
    target_node_id: str
    relationship_type: str
    evidence: List[Evidence] = field(default_factory=list)
    confidence: float = 0.0
    
    def __post_init__(self):
        """Validate edge data"""
        if not self.source_node_id:
            raise ValueError("source_node_id cannot be empty")
        if not self.target_node_id:
            raise ValueError("target_node_id cannot be empty")
        if not self.relationship_type:
            raise ValueError("relationship_type cannot be empty")
        if self.source_node_id == self.target_node_id:
            raise ValueError("source and target nodes cannot be the same")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
        
        # Validate minimum PubMed citations constraint
        if len(self.evidence) < MIN_PUBMED_CITATIONS:
            raise ConstraintViolationError(
                f"Edge must have at least {MIN_PUBMED_CITATIONS} PubMed citations. "
                f"Found {len(self.evidence)}"
            )
    
    def get_pubmed_ids(self) -> Set[str]:
        """Get unique PubMed IDs from evidence"""
        return {e.pubmed_id for e in self.evidence}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert edge to dictionary"""
        return {
            'source_node_id': self.source_node_id,
            'target_node_id': self.target_node_id,
            'relationship_type': self.relationship_type,
            'evidence': [e.to_dict() for e in self.evidence],
            'confidence': self.confidence
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Edge':
        """Create edge from dictionary"""
        evidence = [Evidence.from_dict(e) for e in data.get('evidence', [])]
        return cls(
            source_node_id=data['source_node_id'],
            target_node_id=data['target_node_id'],
            relationship_type=data['relationship_type'],
            evidence=evidence,
            confidence=data.get('confidence', 0.0)
        )


# ========== IN-MEMORY GRAPH STORE ==========
class GraphStore:
    """
    In-memory graph store using dictionaries
    Starts with 3 seed entities and expands through relationships
    
    Structure:
        - nodes: Dict[node_id -> Node]
        - edges: Dict[edge_id -> Edge]
        - node_edges: Dict[node_id -> List[edge_id]] (for fast lookup)
    """
    
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, Edge] = {}
        self.node_edges: Dict[str, List[str]] = {}  # node_id -> list of edge_ids
        self._edge_counter = 0
        
        # Initialize with seed entities
        self._initialize_seed_entities()
    
    def _initialize_seed_entities(self) -> None:
        """Initialize graph with the 3 seed entities"""
        for node_id, entity_data in SEED_ENTITIES.items():
            node = Node(
                node_id=node_id,
                label=entity_data['label'],
                entity_type=entity_data['entity_type'],
                synonyms=entity_data.get('synonyms', []),
                is_seed=True
            )
            self.nodes[node_id] = node
            self.node_edges[node_id] = []
    
    def validate_with_umls(self, node_id: str, umls_cui: str) -> None:
        """
        Validate a node with UMLS CUI (UMLS is used for validation, not discovery)
        
        Args:
            node_id: Node identifier to validate
            umls_cui: UMLS CUI to associate with the node
        """
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} does not exist")
        
        self.nodes[node_id].ontology_ref = umls_cui
    
    def _generate_edge_id(self, source_id: str, target_id: str, rel_type: str) -> str:
        """Generate unique edge ID"""
        self._edge_counter += 1
        return f"E_{self._edge_counter}_{source_id}_{target_id}_{rel_type}"
    
    def _validate_constraints(self):
        """Validate global constraints"""
        # Check max_nodes constraint
        if len(self.nodes) > MAX_NODES:
            raise ConstraintViolationError(
                f"Graph exceeds maximum nodes constraint: {len(self.nodes)} > {MAX_NODES}"
            )
        
        # Check max_depth constraint (calculate maximum path depth from seed entities)
        max_depth = self._calculate_max_depth()
        if max_depth > MAX_DEPTH:
            raise ConstraintViolationError(
                f"Graph exceeds maximum depth constraint: {max_depth} > {MAX_DEPTH}"
            )
    
    def _calculate_max_depth(self) -> int:
        """Calculate maximum depth of the graph using BFS from seed entities"""
        if not self.nodes:
            return 0
        
        # Start BFS from all seed entities
        seed_nodes = [node_id for node_id, node in self.nodes.items() if node.is_seed]
        
        if not seed_nodes:
            # If no seeds found, start from any node
            seed_nodes = [list(self.nodes.keys())[0]]
        
        max_depth = 0
        for seed in seed_nodes:
            depth = self._bfs_depth(seed)
            max_depth = max(max_depth, depth)
        
        return max_depth
    
    def _bfs_depth(self, start_node_id: str) -> int:
        """Calculate depth using BFS from a starting node"""
        if start_node_id not in self.nodes:
            return 0
        
        visited = set()
        queue = [(start_node_id, 0)]
        max_depth = 0
        
        while queue:
            node_id, depth = queue.pop(0)
            if node_id in visited:
                continue
            
            visited.add(node_id)
            max_depth = max(max_depth, depth)
            
            # Get outgoing edges
            edge_ids = self.node_edges.get(node_id, [])
            for edge_id in edge_ids:
                edge = self.edges.get(edge_id)
                if edge and edge.source_node_id == node_id:
                    if edge.target_node_id not in visited:
                        queue.append((edge.target_node_id, depth + 1))
        
        return max_depth
    
    def add_node(self, node: Node) -> None:
        """
        Add a node to the graph (new nodes come from relationships, not UMLS discovery)
        
        Args:
            node: Node to add
        """
        # Check if adding this node would violate max_nodes constraint
        if len(self.nodes) >= MAX_NODES and node.node_id not in self.nodes:
            raise ConstraintViolationError(
                f"Cannot add node: would exceed maximum nodes constraint ({MAX_NODES})"
            )
        
        self.nodes[node.node_id] = node
        if node.node_id not in self.node_edges:
            self.node_edges[node.node_id] = []
    
    def add_edge(self, edge: Edge) -> str:
        """
        Add an edge to the graph
        
        Returns:
            edge_id: The generated edge ID
        """
        # Validate that both nodes exist
        if edge.source_node_id not in self.nodes:
            raise ValueError(f"Source node {edge.source_node_id} does not exist")
        if edge.target_node_id not in self.nodes:
            raise ValueError(f"Target node {edge.target_node_id} does not exist")
        
        # Generate edge ID
        edge_id = self._generate_edge_id(
            edge.source_node_id,
            edge.target_node_id,
            edge.relationship_type
        )
        
        # Add edge
        self.edges[edge_id] = edge
        
        # Update node_edges index
        if edge.source_node_id not in self.node_edges:
            self.node_edges[edge.source_node_id] = []
        self.node_edges[edge.source_node_id].append(edge_id)
        
        # Also track incoming edges for target node
        if edge.target_node_id not in self.node_edges:
            self.node_edges[edge.target_node_id] = []
        self.node_edges[edge.target_node_id].append(edge_id)
        
        # Validate constraints after adding
        try:
            self._validate_constraints()
        except ConstraintViolationError as e:
            # Rollback: remove the edge
            del self.edges[edge_id]
            if edge_id in self.node_edges[edge.source_node_id]:
                self.node_edges[edge.source_node_id].remove(edge_id)
            if edge_id in self.node_edges[edge.target_node_id]:
                self.node_edges[edge.target_node_id].remove(edge_id)
            raise
        
        return edge_id
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID"""
        return self.nodes.get(node_id)
    
    def get_seed_nodes(self) -> List[Node]:
        """Get all seed nodes"""
        return [node for node in self.nodes.values() if node.is_seed]
    
    def get_edge(self, edge_id: str) -> Optional[Edge]:
        """Get an edge by ID"""
        return self.edges.get(edge_id)
    
    def get_node_edges(self, node_id: str, direction: str = 'outgoing') -> List[Edge]:
        """
        Get edges for a node
        
        Args:
            node_id: Node identifier
            direction: 'outgoing', 'incoming', or 'both'
        
        Returns:
            List of edges
        """
        edge_ids = self.node_edges.get(node_id, [])
        edges = []
        
        for edge_id in edge_ids:
            edge = self.edges.get(edge_id)
            if edge:
                if direction == 'outgoing' and edge.source_node_id == node_id:
                    edges.append(edge)
                elif direction == 'incoming' and edge.target_node_id == node_id:
                    edges.append(edge)
                elif direction == 'both':
                    edges.append(edge)
        
        return edges
    
    def get_neighbors(self, node_id: str, direction: str = 'outgoing') -> List[Node]:
        """
        Get neighbor nodes
        
        Args:
            node_id: Node identifier
            direction: 'outgoing', 'incoming', or 'both'
        
        Returns:
            List of neighbor nodes
        """
        edges = self.get_node_edges(node_id, direction)
        neighbor_ids = set()
        
        for edge in edges:
            if direction == 'outgoing':
                neighbor_ids.add(edge.target_node_id)
            elif direction == 'incoming':
                neighbor_ids.add(edge.source_node_id)
            else:  # both
                if edge.source_node_id == node_id:
                    neighbor_ids.add(edge.target_node_id)
                else:
                    neighbor_ids.add(edge.source_node_id)
        
        return [self.nodes[nid] for nid in neighbor_ids if nid in self.nodes]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics"""
        seed_count = sum(1 for node in self.nodes.values() if node.is_seed)
        return {
            'num_nodes': len(self.nodes),
            'num_seed_nodes': seed_count,
            'num_edges': len(self.edges),
            'max_depth': self._calculate_max_depth(),
            'max_nodes_constraint': MAX_NODES,
            'max_depth_constraint': MAX_DEPTH,
            'min_pubmed_citations_constraint': MIN_PUBMED_CITATIONS,
            'entity_types': {
                node.entity_type: sum(1 for n in self.nodes.values() if n.entity_type == node.entity_type)
                for node in self.nodes.values()
            },
            'relationship_types': {
                edge.relationship_type: sum(1 for e in self.edges.values() if e.relationship_type == edge.relationship_type)
                for edge in self.edges.values()
            }
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert graph to dictionary"""
        return {
            'seed_entities': SEED_ENTITIES,
            'nodes': {nid: node.to_dict() for nid, node in self.nodes.items()},
            'edges': {eid: edge.to_dict() for eid, edge in self.edges.items()},
            'statistics': self.get_statistics()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """Load graph from dictionary"""
        # Clear existing data
        self.nodes.clear()
        self.edges.clear()
        self.node_edges.clear()
        self._edge_counter = 0
        
        # Reinitialize seed entities
        self._initialize_seed_entities()
        
        # Load nodes (skip seeds as they're already initialized)
        for nid, node_data in data.get('nodes', {}).items():
            if not node_data.get('is_seed', False):
                node = Node.from_dict(node_data)
                self.add_node(node)
            else:
                # Update seed node with any additional data (like ontology_ref)
                if nid in self.nodes:
                    if 'ontology_ref' in node_data:
                        self.nodes[nid].ontology_ref = node_data['ontology_ref']
                    if 'synonyms' in node_data:
                        self.nodes[nid].synonyms = node_data['synonyms']
        
        # Load edges
        for eid, edge_data in data.get('edges', {}).items():
            edge = Edge.from_dict(edge_data)
            # Reconstruct edge_id mapping
            self.edges[eid] = edge
            if edge.source_node_id not in self.node_edges:
                self.node_edges[edge.source_node_id] = []
            if edge.target_node_id not in self.node_edges:
                self.node_edges[edge.target_node_id] = []
            self.node_edges[edge.source_node_id].append(eid)
            self.node_edges[edge.target_node_id].append(eid)
    
    def save_to_file(self, filepath: str) -> None:
        """Save graph to JSON file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    def load_from_file(self, filepath: str) -> None:
        """Load graph from JSON file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.from_dict(data)

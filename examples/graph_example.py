"""
Example usage of the Graph Schema and Store with Seed Entities
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from medkg.graph import (
    Node, Edge, Evidence, GraphStore, SEED_ENTITIES,
    MAX_DEPTH, MAX_NODES, MIN_PUBMED_CITATIONS,
    ConstraintViolationError
)


def example_usage():
    """Demonstrate graph schema usage with seed entities"""
    print("="*80)
    print("GRAPH SCHEMA EXAMPLE - SEED ENTITY APPROACH")
    print("="*80)
    print(f"Global Constraints:")
    print(f"  - MAX_DEPTH: {MAX_DEPTH}")
    print(f"  - MAX_NODES: {MAX_NODES}")
    print(f"  - MIN_PUBMED_CITATIONS: {MIN_PUBMED_CITATIONS}")
    print("\nSeed Entities (hardcoded, human-curated):")
    for node_id, entity in SEED_ENTITIES.items():
        print(f"  - {entity['label']} ({entity['entity_type']})")
    print("="*80)
    
    # Create graph store (automatically initializes with 3 seed entities)
    print("\n[1] Initializing graph store...")
    graph = GraphStore()
    print(f"  Graph initialized with {len(graph.nodes)} seed nodes")
    
    # Display seed nodes
    print("\n[2] Seed nodes in graph:")
    for node in graph.get_seed_nodes():
        print(f"  - {node.label} (ID: {node.node_id}, Type: {node.entity_type})")
        if node.ontology_ref:
            print(f"    UMLS CUI: {node.ontology_ref}")
    
    # Validate seed entities with UMLS (simulated - in real usage, use UMLS API)
    print("\n[3] Validating seed entities with UMLS (simulated)...")
    # In practice, you would use UMLS API to find CUIs for these entities
    graph.validate_with_umls('intracranial_aneurysm_rupture', 'C0000001')
    graph.validate_with_umls('inflammation', 'C0000002')
    graph.validate_with_umls('hemodynamics', 'C0000003')
    print("  Validated all seed entities with UMLS CUIs")
    
    # Create edges between seed entities with evidence
    print("\n[4] Creating edges between seed entities...")
    
    # Edge 1: Intracranial Aneurysm Rupture -> Inflammation
    evidence1 = [
        Evidence(pubmed_id="12345678", sentence="Intracranial aneurysms are associated with inflammatory processes."),
        Evidence(pubmed_id="23456789", sentence="Inflammation plays a key role in aneurysm formation and rupture.")
    ]
    
    edge1 = Edge(
        source_node_id="intracranial_aneurysm_rupture",
        target_node_id="inflammation",
        relationship_type="INFLUENCES",
        evidence=evidence1,
        confidence=0.85
    )
    
    edge_id1 = graph.add_edge(edge1)
    print(f"  Added edge: {edge1.relationship_type} ({edge1.source_node_id} -> {edge1.target_node_id})")
    
    # Edge 2: Hemodynamics -> Intracranial Aneurysm Rupture
    evidence2 = [
        Evidence(pubmed_id="34567890", sentence="Low wall shear stress is a risk factor for aneurysm rupture."),
        Evidence(pubmed_id="45678901", sentence="Hemodynamic forces influence aneurysm development.")
    ]
    
    edge2 = Edge(
        source_node_id="hemodynamics",
        target_node_id="intracranial_aneurysm_rupture",
        relationship_type="MECHANISTIC_LINK",
        evidence=evidence2,
        confidence=0.90
    )
    
    edge_id2 = graph.add_edge(edge2)
    print(f"  Added edge: {edge2.relationship_type} ({edge2.source_node_id} -> {edge2.target_node_id})")
    
    # Edge 3: Hemodynamics -> Inflammation
    evidence3 = [
        Evidence(pubmed_id="56789012", sentence="Hemodynamic stress triggers inflammatory responses."),
        Evidence(pubmed_id="67890123", sentence="Blood flow patterns influence vascular inflammation.")
    ]
    
    edge3 = Edge(
        source_node_id="hemodynamics",
        target_node_id="inflammation",
        relationship_type="INFLUENCES",
        evidence=evidence3,
        confidence=0.80
    )
    
    edge_id3 = graph.add_edge(edge3)
    print(f"  Added edge: {edge3.relationship_type} ({edge3.source_node_id} -> {edge3.target_node_id})")
    
    # Display graph statistics
    print("\n[5] Graph Statistics:")
    stats = graph.get_statistics()
    for key, value in stats.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")
    
    # Test constraint violations
    print("\n[6] Testing constraint violations...")
    
    # Test: Try to add edge with insufficient evidence
    print("  Testing MIN_PUBMED_CITATIONS constraint...")
    try:
        insufficient_evidence = [
            Evidence(pubmed_id="11111111", sentence="Only one citation.")
        ]
        bad_edge = Edge(
            source_node_id="intracranial_aneurysm_rupture",
            target_node_id="hemodynamics",
            relationship_type="INFLUENCES",
            evidence=insufficient_evidence,
            confidence=0.5
        )
        graph.add_edge(bad_edge)
        print("    ERROR: Should have raised ConstraintViolationError!")
    except ConstraintViolationError as e:
        print(f"    ✓ Correctly rejected: {e}")
    
    # Save graph to file
    print("\n[7] Saving graph to file...")
    # Save to data directory
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(data_dir, exist_ok=True)
    output_file = os.path.join(data_dir, 'example_graph.json')
    graph.save_to_file(output_file)
    print(f"  Saved to {output_file}")
    
    # Load graph from file
    print("\n[8] Loading graph from file...")
    new_graph = GraphStore()
    new_graph.load_from_file(output_file)
    print(f"  Loaded {len(new_graph.nodes)} nodes and {len(new_graph.edges)} edges")
    print(f"  Seed nodes: {len(new_graph.get_seed_nodes())}")
    
    print("\n" + "="*80)
    print("EXAMPLE COMPLETE")
    print("="*80)
    print("\nKey Points:")
    print("  - Graph starts with 3 hardcoded seed entities")
    print("  - UMLS is used for validation (finding CUIs), not entity discovery")
    print("  - New entities come from relationships/evidence, not UMLS search")
    print("  - All constraints are enforced (max_depth, max_nodes, min_pubmed_citations)")


if __name__ == "__main__":
    example_usage()

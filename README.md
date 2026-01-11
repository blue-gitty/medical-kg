# MEDKG - Medical Knowledge Graph

A knowledge graph system for medical research, focusing on biological pathways linking intracranial aneurysm rupture risk to inflammation and hemodynamics.

## Project Structure

```
MEDKG/
├── medkg/                      # Main package (everything lives here)
│   ├── __init__.py
│   │
│   ├── api/                    # API clients
│   │   ├── __init__.py
│   │   ├── umls_client.py      # UMLS API client
│   │   └── pubmed_client.py    # PubMed API client
│   │
│   ├── graph/                  # Graph schema and store
│   │   ├── __init__.py
│   │   └── schema.py           # Node, Edge, GraphStore classes
│   │
│   ├── search/                 # Query Builder/N-gram logic
│   │   ├── __init__.py
│   │   └── builder.py          # PubMed query builder (UMLS/MeSH)
│   │
│   └── server.py               # MCP Server definition
│
├── scripts/                    # Analysis scripts
│   ├── northstar_analysis.py
│   └── print_summary.py
│
├── examples/                   # Example code
│   └── graph_example.py
│
├── data/                       # Data files (JSON results)
│   └── *.json
│
├── .env                        # Environment variables (create this)
├── requirements.txt
├── pyproject.toml              # Package configuration (optional)
├── main.py                     # Entry point to run the server
└── README.md
```

## Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Create `.env` file:**
```env
UMLS_API_KEY=your_umls_api_key_here
PUBMED_EMAIL=your_email@example.com
# Optional: For future PostgreSQL integration
# DATABASE_URL=postgresql://user:password@localhost:5432/medkg
```

3. **Get API keys:**
   - **UMLS API Key**: Register at https://uts.nlm.nih.gov/
   - **PubMed API**: No key required, but email recommended

## Usage

### Basic Graph Operations

```python
from medkg.graph import GraphStore, Node, Edge, Evidence

# Initialize graph (starts with 3 seed entities)
graph = GraphStore()

# Validate seed entities with UMLS
from medkg.api.umls_client import UMLSAPIClient
umls = UMLSAPIClient()
# Find CUI for a seed entity
# Then validate:
graph.validate_with_umls('intracranial_aneurysm_rupture', 'C0000001')

# Add an edge with evidence
evidence = [
    Evidence(pubmed_id="12345678", sentence="..."),
    Evidence(pubmed_id="23456789", sentence="...")
]
edge = Edge(
    source_node_id="intracranial_aneurysm_rupture",
    target_node_id="inflammation",
    relationship_type="INFLUENCES",
    evidence=evidence,
    confidence=0.85
)
graph.add_edge(edge)
```

### PubMed Search

```python
from medkg.api.pubmed_client import PubMedAPIClient

pubmed = PubMedAPIClient()

# Basic search
results = pubmed.search("intracranial aneurysm AND inflammation", max_results=20)

# Search with date filtering
results = pubmed.search(
    "intracranial aneurysm",
    start_date="2020/01/01",
    end_date="2023/12/31",
    max_results=20
)

# Smart query builder (UMLS/MeSH)
results = pubmed.search(
    "What links aneurysm rupture to inflammation?",
    use_smart_query=True,
    max_results=20,
    return_query=True
)
```

## Global Constraints

- **MAX_DEPTH**: 2 (maximum graph depth)
- **MAX_NODES**: 30 (maximum number of nodes)
- **MIN_PUBMED_CITATIONS**: 2 (minimum PubMed citations per edge)

## Seed Entities

The graph starts with 3 hardcoded seed entities:
1. **Intracranial Aneurysm Rupture** (Disease)
2. **Inflammation** (Biological Process)
3. **Hemodynamics** (Biomechanical)

## Architecture

- **Entity Discovery**: Starts with 3 seed entities, expands through relationships
- **UMLS**: Used for validation only (finding CUIs for entities), not discovery
- **PubMed**: Used for evidence collection and relationship discovery
- **Graph Store**: In-memory (dict-based), ready for PostgreSQL integration

## License

MIT


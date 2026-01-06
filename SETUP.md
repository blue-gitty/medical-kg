# MEDKG Setup Guide

## Quick Start

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Create `.env` file in project root:**
```env
UMLS_API_KEY=your_umls_api_key_here
PUBMED_EMAIL=your_email@example.com
```

3. **Test the setup:**
```python
# Test imports
from medkg.graph import GraphStore
from api.umls_client import UMLSAPIClient
from api.pubmed_client import PubMedAPIClient

# Initialize graph
graph = GraphStore()
print(f"Graph initialized with {len(graph.nodes)} seed nodes")
```

## Project Organization

- **`medkg/`** - Main package with graph schema
- **`api/`** - API clients (UMLS, PubMed)
- **`mcp/`** - MCP server for standardized interface
- **`scripts/`** - Analysis scripts
- **`examples/`** - Example code
- **`data/`** - JSON data files

## Key Features

✅ **3 Seed Entities** - Hardcoded starting points
✅ **UMLS Validation** - Use UMLS to validate entities, not discover
✅ **PubMed Integration** - Search and fetch articles for evidence
✅ **Graph Constraints** - MAX_DEPTH=2, MAX_NODES=30, MIN_PUBMED_CITATIONS=2
✅ **MCP Server Ready** - Structure for Model Context Protocol

## Next Steps

1. Implement PubMed search integration
2. Build MCP server endpoints
3. Add PostgreSQL persistence (when ready)
4. Expand graph through relationships and evidence


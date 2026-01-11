# MCP Inspector Setup Guide

This guide explains how to test your MEDKG MCP server using the MCP Inspector.

## Prerequisites

1. **Install Node.js** (if you haven't already)
   - Download from: https://nodejs.org/
   - Verify installation: `node --version`

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up `.env` file**
   Create a `.env` file in the project root with:
   ```
   UMLS_API_KEY=your_umls_api_key_here
   PUBMED_EMAIL=your_email@example.com
   ```

## Running the Inspector

The MCP Inspector is a web-based tool that lets you test your tools interactively.

**IMPORTANT: Make sure to activate your conda environment first!**

```bash
conda activate iaxai_env
```

### Option 1: Use the server script (Recommended)

Run the inspector with the server script:

```bash
npx @modelcontextprotocol/inspector python server_mcp.py
```

**Note:** You must use `server_mcp.py`, not `main.py` or `medkg/server.py`. The `server_mcp.py` file is the correct MCP server implementation.

This will:
1. Start the MCP Inspector web UI (usually at `localhost:5173`)
2. Connect to your MEDKG server via stdin/stdout
3. Allow you to test all tools interactively

### Option 2: Use main.py (Alternative)

**Note:** `main.py` is incomplete and will not work with the MCP Inspector. Always use `server_mcp.py` instead.

## Testing Your Tools

Once the inspector opens:

1. **View Tools**: You'll see a list of your tools on the left:
   - `search_pubmed` - Search PubMed for research papers
   - `search_umls` - Search UMLS for concept standardization
   - `get_umls_concept` - Get detailed UMLS concept information
   - `get_graph_summary` - Get knowledge graph summary

2. **Test a Tool**:
   - Click on a tool (e.g., `search_umls`)
   - Enter arguments in the JSON format:
     ```json
     {
       "term": "intracranial aneurysm",
       "max_results": 5
     }
     ```
   - Click "Run"
   - View the JSON output immediately

3. **Example Tests**:

   **Test UMLS Search**:
   ```json
   {
     "term": "inflammation",
     "max_results": 5,
     "filter_semantic_types": false
   }
   ```

   **Test PubMed Search**:
   ```json
   {
     "query": "intracranial aneurysm AND inflammation",
     "max_results": 10
   }
   ```

   **Test UMLS Concept Lookup**:
   ```json
   {
     "cui": "C0000001"
   }
   ```

## Troubleshooting

### Error: "MCP SDK not installed"
- Run: `pip install mcp`
- Make sure you're using Python 3.8+

### Error: "UMLS_API_KEY not set"
- Create a `.env` file with your UMLS API key
- Get your API key from: https://uts.nlm.nih.gov/

### Inspector won't start
- Make sure Node.js is installed: `node --version`
- Try clearing npm cache: `npm cache clean --force`
- Make sure you're in the project root directory

### Tools not appearing
- Check the console/terminal for error messages
- Verify `server_mcp.py` is executable (Unix/Mac): `chmod +x server_mcp.py`
- Make sure all Python dependencies are installed

## Next Steps

After testing with the Inspector:
1. Verify all tools work correctly
2. Test with various inputs to ensure robustness
3. Once verified, you can integrate the server with Claude Desktop or other MCP clients


# Business ChatBot - MCP System with RAG

Complete business chatbot system with MCP server, RAG (Retrieval-Augmented Generation) tool and Ollama integration.

## 🚀 Quick Start

```bash
#rename requiments.txt to .env

# Install dependencies
pip install -r requirements.txt

# Start MCP server 
python mcp_server.py

# Start MCP client 
python mcp_client.py

# Start Ollama bot 
python ollama_bot.py
```

## 🔄 Dynamic File Loading

The RAG system now automatically discovers and loads all text files from the `data/` directory:

- **Automatic Discovery**: Scans for `.txt`, `.md`, `.rst`, `.text` files
- **Smart Categorization**: Automatically detects file types based on names
- **Auto-Rebuild**: Rebuilds ChromaDB on every server restart
- **No Configuration**: Just add files to the `data/` directory

## 🛠️ Available Tools

### 1. `rag_search` - Main RAG Tool
```python
# Local search only
result = rag_search(
    query="Today's menu",
    top_k=3
)

```

### 2. `search` - Web Search
```python
result = search(
    q="Italian restaurants Milan",
    count=5,
    country="it"
)
```

### 3. `echo` - Test Tool
```python
result = echo(message="Test message")
```

## 📚 Documentation

- [RAG_README.md](RAG_README.md) - Detailed RAG tool documentation

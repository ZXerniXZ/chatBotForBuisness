
# Business ChatBot - MCP System with RAG

Complete business chatbot system with MCP server, RAG (Retrieval-Augmented Generation) tool and Ollama integration.

## 🚀 Quick Start

```bash
#rename requiments.txt to .env

# create venv
python3 -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start MCP server 
python mcp_server.py

# Start MCP client 
python mcp_client.py

# Start Ollama bot 
python ollama_bot.py
```
#todo create RAG_README.md with detailed rag tool documentation#
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

### 3. `current_time` - Time and Date Tool
```python
# Get current time in local timezone (human format)
result = current_time()

# Get current time in specific timezone
result = current_time(timezone="Europe/Rome")

# Get time in different formats
result = current_time(timezone="UTC", format="iso")
result = current_time(format="date_only")
result = current_time(format="time_only")
result = current_time(format="timestamp")

# Available formats: 'human', 'iso', 'timestamp', 'date_only', 'time_only'
# Available timezones: 'UTC', 'Europe/Rome', 'America/New_York', etc.
```

### 4. `echo` - Test Tool
```python
result = echo(message="Test message")
```

## 📚 Documentation

- [RAG_README.md](RAG_README.md) - Detailed RAG tool documentation

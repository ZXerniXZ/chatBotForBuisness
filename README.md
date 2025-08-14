######################################\n
#TO-DO rebuild all readme from scrach#\n
######################################\n


# Business ChatBot - MCP System with RAG

Complete business chatbot system with MCP server, RAG (Retrieval-Augmented Generation) tool and Ollama integration.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Test dynamic file discovery
python test_dynamic_rag.py

# Start MCP server with RAG tool
python mcp_server.py

# Start MCP client (in another terminal)
python mcp_client.py

# Start Ollama bot (in another terminal)
python ollama_bot.py
```

## 🔄 Dynamic File Loading

The RAG system now automatically discovers and loads all text files from the `data/` directory:

- **Automatic Discovery**: Scans for `.txt`, `.md`, `.rst`, `.text` files
- **Smart Categorization**: Automatically detects file types based on names
- **Auto-Rebuild**: Rebuilds ChromaDB on every server restart
- **No Configuration**: Just add files to the `data/` directory

**To add new content:**
1. Add text files to the `data/` directory
2. Restart the MCP server
3. The RAG database will automatically rebuild with new content

## 🏗️ Architecture

### MCP Server (`mcp_server.py`)
- **RAG Tool**: Semantic search on restaurant data
- **Search Tool**: Web search with Brave API
- **Resources**: Access to structured data files
- **Port**: 8001 (configurable)

### MCP Client (`mcp_client.py`)
- HTTP interface for MCP tools
- Port: 8000 (configurable)

### RAG Tool (`rag_search`)
- **ChromaDB**: Vector database for semantic search
- **Sentence Transformers**: Embedding for semantic understanding
- **Web Integration**: Fallback with Brave Search API
- **Automatic Data**: Loading from `data/` folder

## 🔧 Configuration

### Environment Variables
```bash
# Custom data directory
export RESTAURANT_DATA_DIR="/path/to/data"

# Brave API Key (for web search)
export BRAVE_API_KEY="your_api_key"

# MCP Server
export MCP_SERVER_HOST="127.0.0.1"
export MCP_SERVER_PORT="8001"
```

### Supported Data Files
The system automatically discovers and loads all text files from the `data/` directory:

**Supported Formats:**
- `.txt` - Plain text files
- `.md` - Markdown files  
- `.rst` - ReStructuredText files
- `.text` - Text files

**File Type Detection:**
The system automatically categorizes files based on their names:
- `menu_*.txt` → Menu information
- `location*.txt` → Location data
- `contact*.txt` → Contact information
- `hours*.txt` → Opening hours
- `special*.txt` → Special offers
- `policy*.txt` → Policies and terms

**Examples:**
- `data/menu_today.txt` → Today's menu
- `data/location.txt` → Restaurant location
- `data/special_offers.md` → Special offers
- `data/contact_info.txt` → Contact details

## 🛠️ Available Tools

### 1. `rag_search` - Main RAG Tool
```python
# Local search only
result = rag_search(
    query="Today's menu",
    top_k=3
)

# Hybrid search (local + web)
result = rag_search(
    query="Italian menu",
    top_k=2,
    include_web_search=True,
    web_results_count=2
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

## 📊 MCP Resources

- `restaurant://info` → General information
- `restaurant://location` → Restaurant location
- `restaurant://menu/{date}` → Menu for specific date

## 🧪 Tests and Examples

### RAG Test
```bash
python test_rag.py
```

### Usage Examples
```bash
python example_rag_usage.py
```

### Configuration
```bash
python rag_config.py
```

## 📈 System Benefits

### 🎯 Accuracy
- Semantic search vs keyword matching
- Relevance score for ranking
- Metadata for context

### 🔄 Flexibility
- Local-only or hybrid search
- Configurable parameters
- Automatic fallback

### 📈 Scalability
- Persistent database
- Automatic data loading
- Optimized performance

## 🔍 RAG Query Examples

| Query | Type | Expected Result |
|-------|------|------------------|
| "Today's menu" | Local | Menu from `menu_today.txt` file |
| "Opening hours" | Local | Hours from `info.txt` |
| "Where is it located?" | Local | Address from `info.txt` and `location.txt` |
| "Vegetarian options" | Local | Notes from menu |
| "Italian recipes" | Hybrid | Local menu + web recipes |

## 🐛 Troubleshooting

### ChromaDB Error
```bash
# Check installation
pip install chromadb --upgrade

# Recreate database
rm -rf data/chroma_db/
python test_rag.py
```

### Sentence Transformers Error
```bash
# Download models
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### Brave API Error
```bash
# Check API key
echo $BRAVE_API_KEY

# Test connection
curl -H "X-Subscription-Token: $BRAVE_API_KEY" "https://api.search.brave.com/res/v1/web/search?q=test"
```

### MCP Server not responding
```bash
# Check processes
ps aux | grep mcp_server

# Restart server
pkill -f mcp_server.py
python mcp_server.py
```

## 📚 Documentation

- [RAG_README.md](RAG_README.md) - Detailed RAG tool documentation
- [rag_config.py](rag_config.py) - Configuration and parameters
- [test_rag.py](test_rag.py) - Tests and validation
- [example_rag_usage.py](example_rag_usage.py) - Usage examples

## 🔮 Future Developments

- [ ] Multi-language support
- [ ] Intelligent caching
- [ ] Automatic data updates
- [ ] Performance metrics
- [ ] Web interface for management
- [ ] Integration with more data sources
- [ ] Complete REST API 

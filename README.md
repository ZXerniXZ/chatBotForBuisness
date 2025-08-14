# ChatBot per Business - Sistema MCP con RAG

Sistema completo di chatbot per business con server MCP, tool RAG (Retrieval-Augmented Generation) e integrazione Ollama.

## 🚀 Avvio rapido

```bash
# Installazione dipendenze
pip install -r requirements.txt

# Avvio server MCP con tool RAG
python mcp_server.py

# Avvio client MCP (in un altro terminale)
python mcp_client.py

# Test del tool RAG
python test_rag.py
```

## 🏗️ Architettura

### Server MCP (`mcp_server.py`)
- **Tool RAG**: Ricerca semantica sui dati del ristorante
- **Tool Search**: Ricerca web con Brave API
- **Risorse**: Accesso ai file di dati strutturati
- **Porta**: 8001 (configurabile)

### Client MCP (`mcp_client.py`)
- Interfaccia HTTP per i tool MCP
- Porta: 8000 (configurabile)

### Tool RAG (`rag_search`)
- **ChromaDB**: Database vettoriale per ricerca semantica
- **Sentence Transformers**: Embedding per comprensione semantica
- **Integrazione Web**: Fallback con Brave Search API
- **Dati Automatici**: Caricamento da cartella `data/`

## 🔧 Configurazione

### Variabili d'Ambiente
```bash
# Directory dati personalizzata
export RESTAURANT_DATA_DIR="/path/to/data"

# Brave API Key (per ricerca web)
export BRAVE_API_KEY="your_api_key"

# Server MCP
export MCP_SERVER_HOST="127.0.0.1"
export MCP_SERVER_PORT="8001"
```

### File di Dati Supportati
- `data/info.txt` → Informazioni ristorante
- `data/menu_today.txt` → Menu del giorno  
- `data/location.txt` → Posizione e contatti

## 🛠️ Tool Disponibili

### 1. `rag_search` - Tool RAG Principale
```python
# Ricerca solo locale
result = rag_search(
    query="Menu di oggi",
    top_k=3
)

# Ricerca ibrida (locale + web)
result = rag_search(
    query="Menu italiano",
    top_k=2,
    include_web_search=True,
    web_results_count=2
)
```

### 2. `search` - Ricerca Web
```python
result = search(
    q="ristoranti italiani Milano",
    count=5,
    country="it"
)
```

### 3. `echo` - Tool di Test
```python
result = echo(message="Test message")
```

## 📊 Risorse MCP

- `restaurant://info` → Informazioni generali
- `restaurant://location` → Posizione ristorante
- `restaurant://menu/{date}` → Menu per data specifica

## 🧪 Test e Esempi

### Test RAG
```bash
python test_rag.py
```

### Esempi di Utilizzo
```bash
python example_rag_usage.py
```

### Configurazione
```bash
python rag_config.py
```

## 📈 Vantaggi del Sistema

### 🎯 Precisione
- Ricerca semantica vs keyword matching
- Score di rilevanza per ordinamento
- Metadati per contesto

### 🔄 Flessibilità
- Ricerca solo locale o ibrida
- Parametri configurabili
- Fallback automatico

### 📈 Scalabilità
- Database persistente
- Caricamento automatico dati
- Performance ottimizzate

## 🔍 Esempi di Query RAG

| Query | Tipo | Risultato Atteso |
|-------|------|------------------|
| "Menu di oggi" | Locale | Menu dal file `menu_today.txt` |
| "Orari apertura" | Locale | Orari da `info.txt` |
| "Dove si trova?" | Locale | Indirizzo da `info.txt` e `location.txt` |
| "Opzioni vegetariane" | Locale | Note dal menu |
| "Ricette italiane" | Ibrida | Menu locale + ricette web |

## 🐛 Troubleshooting

### Errore ChromaDB
```bash
# Verifica installazione
pip install chromadb --upgrade

# Ricrea database
rm -rf data/chroma_db/
python test_rag.py
```

### Errore Sentence Transformers
```bash
# Download modelli
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### Errore Brave API
```bash
# Verifica API key
echo $BRAVE_API_KEY

# Test connessione
curl -H "X-Subscription-Token: $BRAVE_API_KEY" "https://api.search.brave.com/res/v1/web/search?q=test"
```

### Server MCP non risponde
```bash
# Verifica processi
ps aux | grep mcp_server

# Riavvia server
pkill -f mcp_server.py
python mcp_server.py
```

## 📚 Documentazione

- [RAG_README.md](RAG_README.md) - Documentazione dettagliata del tool RAG
- [rag_config.py](rag_config.py) - Configurazione e parametri
- [test_rag.py](test_rag.py) - Test e validazione
- [example_rag_usage.py](example_rag_usage.py) - Esempi di utilizzo

## 🔮 Sviluppi Futuri

- [ ] Supporto per più lingue
- [ ] Cache intelligente
- [ ] Aggiornamento automatico dati
- [ ] Metriche di performance
- [ ] Interfaccia web per gestione
- [ ] Integrazione con più fonti dati
- [ ] API REST completa 
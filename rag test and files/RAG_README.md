# Tool RAG per Server MCP

## Panoramica

Il tool `rag_search` implementa un sistema di **Retrieval-Augmented Generation (RAG)** per il server MCP del ristorante. Combina ricerca semantica sui dati locali con opzionale ricerca web per fornire risposte complete e accurate.

## Caratteristiche

### 🔍 Ricerca Semantica Locale
- **ChromaDB**: Database vettoriale per ricerca semantica
- **Sentence Transformers**: Embedding per comprensione semantica
- **Dati Automatici**: Caricamento automatico da file `data/`

### 🌐 Ricerca Web Integrata
- **Brave Search API**: Ricerca web opzionale
- **Fallback Intelligente**: Quando i dati locali non sono sufficienti
- **Risultati Combinati**: Integrazione locale + web

### 📊 Risultati Strutturati
- **Score di Rilevanza**: Ordinamento per pertinenza
- **Metadati**: Fonte, tipo, contenuto
- **Formato JSON**: Facile da processare

## Installazione

### 1. Dipendenze
```bash
pip install -r requirements.txt
```

### 2. Variabili d'Ambiente (Opzionali)
```bash
# Directory dati personalizzata
export RESTAURANT_DATA_DIR="/path/to/data"

# Brave API Key (per ricerca web)
export BRAVE_API_KEY="your_api_key"
```

## Utilizzo

### Tool MCP: `rag_search`

#### Parametri
- `query` / `question` / `q`: Domanda di ricerca (obbligatorio)
- `top_k`: Numero risultati locali (default: 3)
- `include_web_search`: Abilita ricerca web (default: false)
- `web_results_count`: Numero risultati web (default: 2)

#### Esempi di Utilizzo

**Ricerca Solo Locale:**
```python
result = rag_search(
    query="Quali sono gli orari del ristorante?",
    top_k=2
)
```

**Ricerca Completa (Locale + Web):**
```python
result = rag_search(
    query="Menu di oggi",
    top_k=3,
    include_web_search=True,
    web_results_count=2
)
```

#### Struttura Risultato
```json
{
  "query": "string",
  "local_results": [
    {
      "content": "string",
      "source": "filename.txt",
      "type": "restaurant_info|menu|location",
      "relevance_score": 0.95
    }
  ],
  "local_count": 3,
  "web_results": [
    {
      "title": "string",
      "url": "string",
      "description": "string",
      "source": "string"
    }
  ],
  "web_count": 2
}
```

## Test

Esegui i test per verificare il funzionamento:

```bash
python test_rag.py
```

I test verificano:
- ✅ Inizializzazione database
- ✅ Ricerca semantica
- ✅ Tool completo
- ✅ Gestione errori

## Architettura

### Database ChromaDB
- **Percorso**: `data/chroma_db/`
- **Collection**: `restaurant_knowledge`
- **Embedding**: Sentence Transformers (automatico)

### File di Dati Supportati
- `info.txt` → Informazioni ristorante
- `menu_today.txt` → Menu del giorno
- `location.txt` → Posizione e contatti

### Flusso di Ricerca
1. **Query Processing**: Normalizzazione input
2. **Embedding**: Conversione in vettori
3. **Similarity Search**: Ricerca in ChromaDB
4. **Web Search** (opzionale): Brave API
5. **Result Aggregation**: Combinazione risultati

## Vantaggi

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

## Troubleshooting

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

## Sviluppi Futuri

- [ ] Supporto per più lingue
- [ ] Cache intelligente
- [ ] Aggiornamento automatico dati
- [ ] Metriche di performance
- [ ] Interfaccia web per gestione 
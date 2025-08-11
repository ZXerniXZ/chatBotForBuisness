# Ollama Bot - Basic Chat Interface

Bot semplice per interagire con modelli Ollama locali, pronto per implementazione MCP client.

## 🚀 Avvio rapido

```bash
# Metodo automatico
./run_bot.sh

# Metodo manuale
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 ollama_bot.py
```

## 📋 Prerequisiti

1. **Ollama** installato e in esecuzione
2. **Modello Llama3** scaricato: `ollama pull llama3:8b`

## ⚙️ Configurazione

Variabili d'ambiente:
- `OLLAMA_MODEL`: Modello da usare (default: `llama3:8b`)
- `OLLAMA_URL`: URL server Ollama (default: `http://localhost:11434`)

## 💬 Comandi

- `quit`, `exit`, `q`: Uscire
- `reset`: Reset cronologia
- `stats`: Statistiche sessione

## 🔄 Per MCP Client

Il codice è strutturato per facilitare l'implementazione MCP:
- Classe `OllamaBot` modulare
- Gestione stato già implementata
- Metodi indipendenti e riutilizzabili

## 🐛 Troubleshooting

```bash
# Verificare Ollama
ollama serve
curl http://localhost:11434/api/tags

# Scaricare modello
ollama pull llama3:8b
``` 
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configurazione per il tool RAG del server MCP.
Contiene impostazioni e parametri per personalizzare il comportamento del RAG.
"""

import os
from pathlib import Path
from typing import Dict, Any, List

# Configurazione database ChromaDB
CHROMA_CONFIG = {
    "collection_name": "restaurant_knowledge",
    "embedding_model": "all-MiniLM-L6-v2",  # Modello di embedding predefinito
    "distance_metric": "cosine",  # Metrica di similarità
    "persist_directory": "data/chroma_db"
}

# Configurazione ricerca
SEARCH_CONFIG = {
    "default_top_k": 3,  # Numero di risultati locali predefinito
    "max_top_k": 10,     # Numero massimo di risultati locali
    "min_relevance_score": 0.1,  # Score minimo di rilevanza
    "default_web_results": 2,    # Numero di risultati web predefinito
    "max_web_results": 5         # Numero massimo di risultati web
}

# Configurazione file di dati
DATA_CONFIG = {
    "supported_files": [
        "info.txt",
        "menu_today.txt", 
        "location.txt"
    ],
    "file_types": {
        "info.txt": "restaurant_info",
        "menu_today.txt": "menu",
        "location.txt": "location"
    },
    "data_dir": os.environ.get("RESTAURANT_DATA_DIR", "data")
}

# Configurazione ricerca web
WEB_SEARCH_CONFIG = {
    "default_country": "it",
    "default_language": "it",
    "timeout": 15,
    "max_retries": 3
}

# Configurazione logging
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "rag.log"
}

def get_data_directory() -> Path:
    """Restituisce la directory dei dati."""
    return Path(DATA_CONFIG["data_dir"]).resolve()

def get_chroma_path() -> Path:
    """Restituisce il percorso del database ChromaDB."""
    data_dir = get_data_directory()
    return data_dir / CHROMA_CONFIG["persist_directory"]

def validate_config() -> List[str]:
    """Valida la configurazione e restituisce eventuali errori."""
    errors = []
    
    # Verifica directory dati
    data_dir = get_data_directory()
    if not data_dir.exists():
        errors.append(f"Directory dati non trovata: {data_dir}")
    
    # Verifica file supportati
    for filename in DATA_CONFIG["supported_files"]:
        file_path = data_dir / filename
        if not file_path.exists():
            errors.append(f"File dati mancante: {file_path}")
    
    # Verifica configurazione ricerca
    if SEARCH_CONFIG["default_top_k"] > SEARCH_CONFIG["max_top_k"]:
        errors.append("default_top_k non può essere maggiore di max_top_k")
    
    return errors

def get_tool_description() -> str:
    """Restituisce la descrizione del tool per MCP."""
    return """
    Tool RAG (Retrieval-Augmented Generation) per ricerca semantica sui dati del ristorante.
    
    Caratteristiche:
    - Ricerca semantica sui dati locali usando ChromaDB
    - Integrazione opzionale con ricerca web (Brave API)
    - Score di rilevanza per ordinamento risultati
    - Supporto per metadati e fonti
    
    Parametri:
    - query/question/q: Domanda di ricerca (obbligatorio)
    - top_k: Numero risultati locali (default: 3, max: 10)
    - include_web_search: Abilita ricerca web (default: false)
    - web_results_count: Numero risultati web (default: 2, max: 5)
    
    Esempi:
    - Ricerca menu: query="Menu di oggi"
    - Ricerca orari: query="Orari apertura"
    - Ricerca completa: query="Menu italiano" + include_web_search=true
    """

def get_example_queries() -> List[Dict[str, Any]]:
    """Restituisce esempi di query per il tool."""
    return [
        {
            "query": "Quali sono gli orari del ristorante?",
            "description": "Ricerca informazioni sugli orari",
            "top_k": 2,
            "include_web_search": False
        },
        {
            "query": "Cosa c'è nel menu di oggi?",
            "description": "Ricerca menu del giorno",
            "top_k": 3,
            "include_web_search": False
        },
        {
            "query": "Dove si trova il ristorante?",
            "description": "Ricerca informazioni sulla posizione",
            "top_k": 1,
            "include_web_search": False
        },
        {
            "query": "Ci sono opzioni vegetariane?",
            "description": "Ricerca opzioni vegetariane nel menu",
            "top_k": 2,
            "include_web_search": False
        },
        {
            "query": "Menu italiano e specialità",
            "description": "Ricerca ibrida con informazioni web",
            "top_k": 2,
            "include_web_search": True,
            "web_results_count": 3
        }
    ]

# Configurazione per test
TEST_CONFIG = {
    "test_queries": [
        "Quali sono gli orari del ristorante?",
        "Cosa c'è nel menu di oggi?",
        "Dove si trova il ristorante?",
        "Quali sono i contatti?",
        "Ci sono opzioni vegetariane?"
    ],
    "expected_sources": {
        "orari": ["info.txt"],
        "menu": ["menu_today.txt"],
        "posizione": ["info.txt", "location.txt"],
        "contatti": ["info.txt"],
        "vegetariano": ["menu_today.txt"]
    }
} 
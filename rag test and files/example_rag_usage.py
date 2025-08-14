#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Esempio di utilizzo del tool RAG per il server MCP.
Dimostra come utilizzare il tool rag_search per diverse tipologie di query.
"""

import requests
import json
from typing import Dict, Any

def call_rag_tool(query: str, top_k: int = 3, include_web_search: bool = False, web_results_count: int = 2) -> Dict[str, Any]:
    """Chiama il tool RAG tramite HTTP API."""
    url = "http://127.0.0.1:8001/mcp/tools/rag_search/call"
    payload = {
        "query": query,
        "top_k": top_k,
        "include_web_search": include_web_search,
        "web_results_count": web_results_count
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Errore nella chiamata API: {e}")
        return {}

def print_rag_results(result: Dict[str, Any]):
    """Stampa i risultati del RAG in formato leggibile."""
    if not result:
        print("❌ Nessun risultato ottenuto")
        return
    
    print(f"\n🔍 Query: '{result.get('query', 'N/A')}'")
    print(f"📊 Risultati locali: {result.get('local_count', 0)}")
    print(f"🌐 Risultati web: {result.get('web_count', 0)}")
    
    # Risultati locali
    local_results = result.get('local_results', [])
    if local_results:
        print("\n📚 Risultati Locali:")
        for i, local in enumerate(local_results, 1):
            print(f"   {i}. Score: {local.get('relevance_score', 0):.3f}")
            print(f"      Fonte: {local.get('source', 'N/A')}")
            print(f"      Tipo: {local.get('type', 'N/A')}")
            print(f"      Contenuto: {local.get('content', 'N/A')[:100]}...")
            print()
    
    # Risultati web
    web_results = result.get('web_results', [])
    if web_results:
        print("🌐 Risultati Web:")
        for i, web in enumerate(web_results, 1):
            print(f"   {i}. {web.get('title', 'N/A')}")
            print(f"      URL: {web.get('url', 'N/A')}")
            print(f"      Fonte: {web.get('source', 'N/A')}")
            print(f"      Descrizione: {web.get('description', 'N/A')[:80]}...")
            print()

def main():
    """Esempi di utilizzo del tool RAG."""
    print("🚀 Esempi di utilizzo del tool RAG")
    print("=" * 50)
    
    # Esempio 1: Ricerca solo locale
    print("\n1️⃣ Ricerca Solo Locale - Menu del giorno")
    result1 = call_rag_tool(
        query="Cosa c'è nel menu di oggi?",
        top_k=2,
        include_web_search=False
    )
    print_rag_results(result1)
    
    # Esempio 2: Ricerca locale con più risultati
    print("\n2️⃣ Ricerca Locale Estesa - Informazioni ristorante")
    result2 = call_rag_tool(
        query="Quali sono gli orari e i contatti del ristorante?",
        top_k=3,
        include_web_search=False
    )
    print_rag_results(result2)
    
    # Esempio 3: Ricerca ibrida (locale + web)
    print("\n3️⃣ Ricerca Ibrida - Menu e informazioni aggiuntive")
    result3 = call_rag_tool(
        query="Menu italiano e specialità",
        top_k=2,
        include_web_search=True,
        web_results_count=2
    )
    print_rag_results(result3)
    
    # Esempio 4: Ricerca specifica
    print("\n4️⃣ Ricerca Specifica - Opzioni vegetariane")
    result4 = call_rag_tool(
        query="Ci sono opzioni vegetariane nel menu?",
        top_k=1,
        include_web_search=False
    )
    print_rag_results(result4)
    
    # Esempio 5: Ricerca con fallback web
    print("\n5️⃣ Ricerca con Fallback Web - Informazioni non presenti localmente")
    result5 = call_rag_tool(
        query="Ricette tradizionali italiane",
        top_k=1,
        include_web_search=True,
        web_results_count=3
    )
    print_rag_results(result5)

if __name__ == "__main__":
    main() 
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from mcp.server.fastmcp import FastMCP
import uvicorn
import os
import requests
from typing import Any, List, Dict
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import json

# Carica variabili da .env se presente
load_dotenv()

# Minimal FastMCP server
mcp = FastMCP(name="demo-basic-http")

# --- Helpers per lettura file di dati ---
from pathlib import Path

def _get_data_dir() -> Path:
    env_dir = os.environ.get("RESTAURANT_DATA_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return (Path(__file__).parent / "data").resolve()


def _read_text(filename: str) -> str:
    data_dir = _get_data_dir()
    file_path = data_dir / filename
    if not file_path.exists():
        raise ValueError(
            f"File dati mancante: '{file_path}'. Crea il file o imposta RESTAURANT_DATA_DIR."
        )
    try:
        return file_path.read_text(encoding="utf-8").strip()
    except Exception as e:
        raise ValueError(f"Impossibile leggere '{file_path}': {e}") from e


# --- Helpers per RAG con ChromaDB ---
def _get_chroma_client():
    """Inizializza e restituisce il client ChromaDB."""
    data_dir = _get_data_dir()
    chroma_path = data_dir / "chroma_db"
    return chromadb.PersistentClient(
        path=str(chroma_path),
        settings=Settings(anonymized_telemetry=False)
    )


def _initialize_rag_database():
    """Inizializza il database RAG con i dati del ristorante."""
    try:
        client = _get_chroma_client()
        collection_name = "restaurant_knowledge"
        
        # Verifica se la collection esiste già
        try:
            collection = client.get_collection(collection_name)
            return collection
        except:
            # Crea nuova collection
            collection = client.create_collection(
                name=collection_name,
                metadata={"description": "Conoscenza del ristorante per RAG"}
            )
            
            # Carica e segmenta i dati
            documents = []
            metadatas = []
            ids = []
            
            # Info del ristorante
            try:
                info_content = _read_text("info.txt")
                documents.append(info_content)
                metadatas.append({"source": "info.txt", "type": "restaurant_info"})
                ids.append("info_001")
            except:
                pass
            
            # Menu di oggi
            try:
                menu_content = _read_text("menu_today.txt")
                documents.append(menu_content)
                metadatas.append({"source": "menu_today.txt", "type": "menu"})
                ids.append("menu_today_001")
            except:
                pass
            
            # Location
            try:
                location_content = _read_text("location.txt")
                documents.append(location_content)
                metadatas.append({"source": "location.txt", "type": "location"})
                ids.append("location_001")
            except:
                pass
            
            # Aggiungi documenti se ce ne sono
            if documents:
                collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
            
            return collection
            
    except Exception as e:
        print(f"Errore nell'inizializzazione RAG: {e}")
        return None


def _rag_search(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Esegue ricerca RAG sui dati del ristorante."""
    try:
        collection = _initialize_rag_database()
        if not collection:
            return []
        
        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        
        formatted_results = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                formatted_results.append({
                    "content": doc,
                    "source": results['metadatas'][0][i].get('source', 'unknown'),
                    "type": results['metadatas'][0][i].get('type', 'unknown'),
                    "relevance_score": 1.0 - (results['distances'][0][i] if results['distances'] and results['distances'][0] else 0.0)
                })
        
        return formatted_results
        
    except Exception as e:
        print(f"Errore nella ricerca RAG: {e}")
        return []


@mcp.tool()
def echo(message: str | None = None, payload: str | None = None) -> str:
    """Ritorna il messaggio così com'è (eco).

    Accetta sia 'message' che 'payload' come alias per compatibilità.
    """
    value = message if message is not None else payload
    if value is None:
        raise ValueError("Campo mancante: specificare 'message' o 'payload'.")
    return value

@mcp.tool()
def search(
    q: str | None = None,
    query: str | None = None,
    text: str | None = None,
    message: str | None = None,
    count: int | str | None = 3,
    country: str | None = "it",
    search_lang: str | None = "it",
    safesearch: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Esegue una ricerca Web usando Brave Search API.

    Parametri:
    - q/query/text/message: testo della query (obbligatorio, alias equivalenti)
    - count: numero risultati (default 3)
    - country: paese, es. "it", "us" (default "it")
    - search_lang: lingua dei risultati, es. "it", "en" (default "it")
    - safesearch: livello filtro contenuti (es. "off", "moderate", "strict")
    - api_key: chiave Brave (se assente, usa env BRAVE_API_KEY)

    Restituisce una struttura compatta con i campi rilevanti per la LLM.
    """
    key = api_key or os.environ.get("BRAVE_API_KEY")
    if not key:
        raise ValueError(
            "Brave API key mancante: passare 'api_key' oppure impostare env 'BRAVE_API_KEY'."
        )

    # Normalizza query e count
    q_value = q or query or text or message
    if not q_value:
        raise ValueError("Parametro mancante: fornire 'q' o uno degli alias 'query'/'text'/'message'.")

    if isinstance(count, str):
        try:
            count = int(count)
        except ValueError:
            raise ValueError("'count' deve essere un intero o una stringa numerica.")

    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "X-Subscription-Token": key,
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    }
    params: dict[str, Any] = {"q": q_value}
    if count is not None:
        params["count"] = count
    if country:
        params["country"] = country
    if search_lang:
        params["search_lang"] = search_lang
    if safesearch:
        params["safesearch"] = safesearch

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # Post-processing: estrai solo dati essenziali
        def strip_html(text: str | None) -> str:
            if not text:
                return ""
            # Rimuove tag HTML basilari come <strong>
            import re as _re
            return _re.sub(r"<[^>]+>", "", text)

        web_results = (data.get("web") or {}).get("results") or []
        limited = web_results[: max(0, count or 0)] if count is not None else web_results

        compact: list[dict[str, Any]] = []
        for item in limited:
            title = item.get("title")
            url_item = item.get("url")
            desc = strip_html(item.get("description"))
            meta = item.get("meta_url") or {}
            profile = item.get("profile") or {}
            source = (
                profile.get("long_name")
                or profile.get("name")
                or meta.get("hostname")
            )
            if title and url_item:
                compact.append(
                    {
                        "title": title,
                        "url": url_item,
                        "description": desc,
                        "source": source,
                    }
                )

        # Fallback su video se non ci sono risultati web
        if not compact:
            videos = (data.get("videos") or {}).get("results") or []
            v_limited = videos[: max(0, count or 0)] if count is not None else videos
            for v in v_limited:
                title = v.get("title")
                url_item = v.get("url")
                desc = strip_html(v.get("description"))
                meta = v.get("meta_url") or {}
                source = meta.get("hostname")
                if title and url_item:
                    compact.append(
                        {
                            "title": title,
                            "url": url_item,
                            "description": desc,
                            "source": source,
                        }
                    )

        return {
            "query": q_value,
            "country": country,
            "search_lang": search_lang,
            "count": count,
            "results": compact,
        }
    except requests.HTTPError as http_err:
        raise ValueError(
            f"Brave API HTTP error {resp.status_code}: {resp.text[:500]}"
        ) from http_err
    except Exception as e:
        raise ValueError(f"Errore chiamando Brave API: {e}") from e


@mcp.tool()
def rag_search(
    query: str | None = None,
    question: str | None = None,
    q: str | None = None,
    top_k: int | None = 3,
    include_web_search: bool | None = False,
    web_results_count: int | None = 2
) -> dict[str, Any]:
    """Esegue una ricerca RAG (Retrieval-Augmented Generation) sui dati del ristorante.
    
    Questo tool combina ricerca semantica sui dati locali del ristorante con 
    opzionale ricerca web per informazioni aggiuntive.
    
    Parametri:
    - query/question/q: domanda o query di ricerca (obbligatorio, alias equivalenti)
    - top_k: numero di risultati locali da recuperare (default 3)
    - include_web_search: se includere anche ricerca web (default False)
    - web_results_count: numero di risultati web se abilitato (default 2)
    
    Restituisce risultati strutturati con contenuto locale e opzionalmente web.
    """
    # Normalizza query
    query_value = query or question or q
    if not query_value:
        raise ValueError("Parametro mancante: fornire 'query', 'question' o 'q'.")
    
    # Normalizza parametri
    if isinstance(top_k, str):
        try:
            top_k = int(top_k)
        except ValueError:
            raise ValueError("'top_k' deve essere un intero o una stringa numerica.")
    
    if isinstance(web_results_count, str):
        try:
            web_results_count = int(web_results_count)
        except ValueError:
            raise ValueError("'web_results_count' deve essere un intero o una stringa numerica.")
    
    # Esegui ricerca RAG locale
    local_results = _rag_search(query_value, top_k or 3)
    
    # Prepara risultato base
    result = {
        "query": query_value,
        "local_results": local_results,
        "local_count": len(local_results),
        "web_results": [],
        "web_count": 0
    }
    
    # Aggiungi ricerca web se richiesto
    if include_web_search:
        try:
            web_results = search(
                q=query_value,
                count=web_results_count or 2,
                country="it",
                search_lang="it"
            )
            result["web_results"] = web_results.get("results", [])
            result["web_count"] = len(result["web_results"])
        except Exception as e:
            result["web_error"] = str(e)
    
    return result


# --- Risorse MCP per il ristorante (da file in 'data/') ---
@mcp.resource("restaurant://info")
def restaurant_info() -> dict[str, Any]:
    """Informazioni generali sul ristorante lette da 'data/info.txt'."""
    content = _read_text("info.txt")
    return {"text": content}


@mcp.resource("restaurant://location")
def restaurant_location() -> dict[str, Any]:
    """Dove si trova il ristorante, letto da 'data/location.txt'."""
    content = _read_text("location.txt")
    return {"text": content}


@mcp.resource("restaurant://menu/{date}")
def restaurant_menu(date: str) -> dict[str, Any]:
    """Menù per la data richiesta, letto da file nella cartella 'data'.

    Regole file:
    - Oggi: 'menu_today.txt'
    - Data specifica (YYYY-MM-DD): 'menu_YYYY-MM-DD.txt'
    """
    import re as _re

    date_norm = (date or "").strip().lower()
    if date_norm in {"oggi", "today", ""}:
        filename = "menu_today.txt"
        label = "today"
    elif _re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_norm):
        filename = f"menu_{date_norm}.txt"
        label = date_norm
    else:
        raise ValueError(
            "Formato data non valido. Usa 'oggi'/'today' oppure 'YYYY-MM-DD'."
        )

    content = _read_text(filename)
    return {"date": label, "text": content}

if __name__ == "__main__":
    # Serve l'app Streamable HTTP su /mcp
    app = mcp.streamable_http_app()
    host = os.environ.get("MCP_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_SERVER_PORT", "8001"))
    uvicorn.run(app, host=host, port=port, reload=False) 
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

# --- Helpers for reading data files ---
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
            f"Missing data file: '{file_path}'. Create the file or set RESTAURANT_DATA_DIR."
        )
    try:
        return file_path.read_text(encoding="utf-8").strip()
    except Exception as e:
        raise ValueError(f"Cannot read '{file_path}': {e}") from e


# --- Helpers for RAG with ChromaDB ---
def _get_chroma_client():
    """Initializes and returns the ChromaDB client."""
    data_dir = _get_data_dir()
    chroma_path = data_dir / "chroma_db"
    return chromadb.PersistentClient(
        path=str(chroma_path),
        settings=Settings(anonymized_telemetry=False)
    )


# Global cache for collection and file hashes
_collection_cache = None
_file_hashes = {}

def _get_file_hash(file_path: Path) -> str:
    """Get a hash of file content and modification time."""
    try:
        stat = file_path.stat()
        content = file_path.read_text(encoding='utf-8')
        import hashlib
        hash_content = hashlib.md5(f"{content}{stat.st_mtime}".encode()).hexdigest()
        return hash_content
    except Exception:
        return ""

def _check_files_changed() -> bool:
    """Check if any files have changed since last cache."""
    global _file_hashes
    
    data_dir = _get_data_dir()
    text_extensions = {'.txt', '.md', '.rst', '.text'}
    current_hashes = {}
    
    # Get current file hashes
    for file_path in data_dir.rglob('*'):
        if file_path.is_file() and file_path.suffix.lower() in text_extensions:
            relative_path = str(file_path.relative_to(data_dir))
            current_hashes[relative_path] = _get_file_hash(file_path)
    
    # Check if files changed
    if _file_hashes != current_hashes:
        _file_hashes = current_hashes
        return True
    
    return False

def _initialize_rag_database():
    """Initializes the RAG database with restaurant data by scanning for text files."""
    global _collection_cache
    
    try:
        client = _get_chroma_client()
        collection_name = "restaurant_knowledge"
        
        # Check if files have changed
        files_changed = _check_files_changed()
        
        # If collection exists and files haven't changed, return cached collection
        if not files_changed and _collection_cache is not None:
            try:
                # Verify collection still exists
                collection = client.get_collection(collection_name)
                print(f"Using cached RAG database (no files changed)")
                return collection
            except:
                # Collection was deleted, need to rebuild
                pass
        
        # Files changed or collection doesn't exist, rebuild
        print(f"Files changed or collection missing, rebuilding RAG database...")
        
        # Delete existing collection if it exists
        try:
            client.delete_collection(collection_name)
            print(f"Deleted existing collection: {collection_name}")
        except:
            pass  # Collection didn't exist
        
        # Create new collection
        collection = client.create_collection(
            name=collection_name,
            metadata={"description": "Restaurant knowledge for RAG"}
        )
        
        # Scan data directory for text files
        data_dir = _get_data_dir()
        text_extensions = {'.txt', '.md', '.rst', '.text'}
        
        documents = []
        metadatas = []
        ids = []
        
        print(f"Scanning directory: {data_dir}")
        
        # Find all text files in the data directory
        for file_path in data_dir.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in text_extensions:
                try:
                    # Read file content
                    content = file_path.read_text(encoding='utf-8').strip()
                    if not content:  # Skip empty files
                        continue
                    
                    # Determine file type based on name or path
                    file_type = _determine_file_type(file_path)
                    
                    # Create relative path for source
                    relative_path = file_path.relative_to(data_dir)
                    
                    documents.append(content)
                    metadatas.append({
                        "source": str(relative_path),
                        "type": file_type,
                        "filename": file_path.name,
                        "full_path": str(file_path)
                    })
                    ids.append(f"{relative_path}_{len(documents)}")
                    
                    print(f"Loaded: {relative_path} (type: {file_type})")
                    
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
                    continue
        
        # Add documents if any exist
        if documents:
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Added {len(documents)} documents to RAG database")
        else:
            print("No text files found to add to RAG database")
        
        # Cache the collection
        _collection_cache = collection
        
        return collection
        
    except Exception as e:
        print(f"Error in RAG initialization: {e}")
        return None


def _determine_file_type(file_path: Path) -> str:
    """Determines the type of a file based on its name and content."""
    filename = file_path.name.lower()
    
    # Menu files
    if 'menu' in filename:
        if 'today' in filename:
            return 'menu_today'
        elif any(date_pattern in filename for date_pattern in ['2024', '2025', '2023']):
            return 'menu_dated'
        else:
            return 'menu'
    
    # Location files
    if any(loc_word in filename for loc_word in ['location', 'address', 'where', 'map']):
        return 'location'
    
    # Contact files
    if any(contact_word in filename for contact_word in ['contact', 'phone', 'email', 'info']):
        return 'contact'
    
    # Hours files
    if any(hour_word in filename for hour_word in ['hours', 'schedule', 'time', 'open']):
        return 'hours'
    
    # Special files
    if 'special' in filename or 'promo' in filename:
        return 'special'
    
    if 'policy' in filename or 'terms' in filename:
        return 'policy'
    
    # Default type based on extension
    if file_path.suffix == '.md':
        return 'markdown'
    elif file_path.suffix == '.rst':
        return 'restructured'
    else:
        return 'general'


def _refresh_rag_database():
    """Manually refresh the RAG database by clearing cache."""
    global _collection_cache, _file_hashes
    _collection_cache = None
    _file_hashes = {}
    print("RAG database cache cleared, will rebuild on next request")

def _rag_search(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Performs RAG search on restaurant data."""
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
        print(f"Error in RAG search: {e}")
        return []


@mcp.tool()
def echo(message: str | None = None, payload: str | None = None) -> str:
    """Returns the message as-is (echo).

    Accepts both 'message' and 'payload' as aliases for compatibility.
    """
    value = message if message is not None else payload
    if value is None:
        raise ValueError("Missing field: specify 'message' or 'payload'.")
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
    """Performs a Web search using Brave Search API.

    Parameters:
    - q/query/text/message: query text (required, equivalent aliases)
    - count: number of results (default 3)
    - country: country, e.g. "it", "us" (default "it")
    - search_lang: language of results, e.g. "it", "en" (default "it")
    - safesearch: content filter level (e.g. "off", "moderate", "strict")
    - api_key: Brave key (if missing, uses env BRAVE_API_KEY)

    Returns a compact structure with fields relevant for the LLM.
    """
    key = api_key or os.environ.get("BRAVE_API_KEY")
    if not key:
        raise ValueError(
            "Missing Brave API key: pass 'api_key' or set env 'BRAVE_API_KEY'."
        )

    # Normalize query and count
    q_value = q or query or text or message
    if not q_value:
        raise ValueError("Missing parameter: provide 'q' or one of the aliases 'query'/'text'/'message'.")

    if isinstance(count, str):
        try:
            count = int(count)
        except ValueError:
            raise ValueError("'count' must be an integer or numeric string.")

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

        # Post-processing: extract only essential data
        def strip_html(text: str | None) -> str:
            if not text:
                return ""
            # Removes basic HTML tags like <strong>
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

        # Fallback to videos if no web results
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
        raise ValueError(f"Error calling Brave API: {e}") from e


@mcp.tool()
def rag_search(
    query: str | None = None,
    question: str | None = None,
    q: str | None = None,
    top_k: int | None = 3
) -> dict[str, Any]:
    """Performs a RAG (Retrieval-Augmented Generation) search on restaurant data.
    
    This tool performs semantic search on local restaurant data using ChromaDB.
    
    Parameters:
    - query/question/q: search query or question (required, equivalent aliases)
    - top_k: number of local results to retrieve (default 3)
    
    Returns structured results with local content.
    """
    # Normalize query
    query_value = query or question or q
    if not query_value:
        raise ValueError("Missing parameter: provide 'query', 'question' or 'q'.")
    
    # Normalize parameters
    if isinstance(top_k, str):
        try:
            top_k = int(top_k)
        except ValueError:
            raise ValueError("'top_k' must be an integer or numeric string.")
    
    # Perform local RAG search
    local_results = _rag_search(query_value, top_k or 3)
    
    # Prepare result
    result = {
        "query": query_value,
        "local_results": local_results,
        "local_count": len(local_results)
    }
    
    return result


# --- MCP Resources for restaurant (from files in 'data/') ---
#@mcp.resource("restaurant://info")
def restaurant_info() -> dict[str, Any]:
    """General restaurant information read from 'data/info.txt'."""
    content = _read_text("info.txt")
    return {"text": content}


#@mcp.resource("restaurant://location")
def restaurant_location() -> dict[str, Any]:
    """Where the restaurant is located, read from 'data/location.txt'."""
    content = _read_text("location.txt")
    return {"text": content}


#@mcp.resource("restaurant://menu/{date}")
def restaurant_menu(date: str) -> dict[str, Any]:
    """Menu for the requested date, read from files in the 'data' folder.

    File rules:
    - Today: 'menu_today.txt'
    - Specific date (YYYY-MM-DD): 'menu_YYYY-MM-DD.txt'
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
            "Invalid date format. Use 'oggi'/'today' or 'YYYY-MM-DD'."
        )

    content = _read_text(filename)
    return {"date": label, "text": content}

if __name__ == "__main__":
    # Serve the Streamable HTTP app on /mcp
    app = mcp.streamable_http_app()
    host = os.environ.get("MCP_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_SERVER_PORT", "8001"))
    uvicorn.run(app, host=host, port=port, reload=False) 
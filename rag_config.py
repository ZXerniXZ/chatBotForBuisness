#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuration for the RAG tool of the MCP server.
Contains settings and parameters to customize RAG behavior.
"""

import os
from pathlib import Path
from typing import Dict, Any, List

# ChromaDB database configuration
CHROMA_CONFIG = {
    "collection_name": "restaurant_knowledge",
    "embedding_model": "all-MiniLM-L6-v2",  # Default embedding model
    "distance_metric": "cosine",  # Similarity metric
    "persist_directory": "data/chroma_db"
}

# Search configuration
SEARCH_CONFIG = {
    "default_top_k": 3,  # Default number of local results
    "max_top_k": 10,     # Maximum number of local results
    "min_relevance_score": 0.1,  # Minimum relevance score
}

# Data files configuration
DATA_CONFIG = {
    # Supported text file extensions
    "supported_extensions": ['.txt', '.md', '.rst', '.text'],
    # File type detection patterns
    "type_patterns": {
        "menu": ["menu", "food", "dish", "course"],
        "location": ["location", "address", "where", "map"],
        "contact": ["contact", "phone", "email", "info"],
        "hours": ["hours", "schedule", "time", "open"],
        "special": ["special", "promo", "offer"],
        "policy": ["policy", "terms", "rules"]
    },
    "data_dir": os.environ.get("RESTAURANT_DATA_DIR", "data"),
    # Auto-rebuild database on startup
    "auto_rebuild": True
}

# Web search configuration
WEB_SEARCH_CONFIG = {
    "default_country": "it",
    "default_language": "it",
    "timeout": 15,
    "max_retries": 3
}

# Logging configuration
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "rag.log"
}

def get_data_directory() -> Path:
    """Returns the data directory."""
    return Path(DATA_CONFIG["data_dir"]).resolve()

def get_chroma_path() -> Path:
    """Returns the ChromaDB database path."""
    data_dir = get_data_directory()
    return data_dir / CHROMA_CONFIG["persist_directory"]

def validate_config() -> List[str]:
    """Validates the configuration and returns any errors."""
    errors = []
    
    # Check data directory
    data_dir = get_data_directory()
    if not data_dir.exists():
        errors.append(f"Data directory not found: {data_dir}")
        return errors
    
    # Check if any text files exist
    text_files = []
    for ext in DATA_CONFIG["supported_extensions"]:
        text_files.extend(data_dir.rglob(f"*{ext}"))
    
    if not text_files:
        errors.append(f"No text files found in {data_dir}. Supported extensions: {DATA_CONFIG['supported_extensions']}")
    
    # Check search configuration
    if SEARCH_CONFIG["default_top_k"] > SEARCH_CONFIG["max_top_k"]:
        errors.append("default_top_k cannot be greater than max_top_k")
    
    return errors

def get_tool_description() -> str:
    """Returns the tool description for MCP."""
    return """
    RAG (Retrieval-Augmented Generation) tool for semantic search on restaurant data.
    
    Features:
    - Dynamic file discovery: Automatically loads all text files from data directory
    - Supported formats: .txt, .md, .rst, .text files
    - Semantic search on local data using ChromaDB
    - Relevance score for result ranking
    - Support for metadata and sources
    - Auto-rebuilds database on server restart
    
    Parameters:
    - query/question/q: Search query (required)
    - top_k: Number of local results (default: 3, max: 10)
    
    Examples:
    - Search menu: query="Today's menu"
    - Search hours: query="Opening hours"
    - Search info: query="Where is the restaurant located"
    - Search any content: query="vegetarian options"
    """

def get_example_queries() -> List[Dict[str, Any]]:
    """Returns example queries for the tool."""
    return [
        {
            "query": "What are the restaurant hours?",
            "description": "Search for opening hours information",
            "top_k": 2
        },
        {
            "query": "What's on today's menu?",
            "description": "Search for today's menu",
            "top_k": 3
        },
        {
            "query": "Where is the restaurant located?",
            "description": "Search for location information",
            "top_k": 1
        },
        {
            "query": "Are there vegetarian options?",
            "description": "Search for vegetarian options in the menu",
            "top_k": 2
        },
        {
            "query": "What are the restaurant contact details?",
            "description": "Search for contact information",
            "top_k": 1
        }
    ]

# Test configuration
TEST_CONFIG = {
    "test_queries": [
        "What are the restaurant hours?",
        "What's on today's menu?",
        "Where is the restaurant located?",
        "What are the contact details?",
        "Are there vegetarian options?"
    ],
    "expected_sources": {
        "hours": ["info.txt"],
        "menu": ["menu_today.txt"],
        "location": ["info.txt", "location.txt"],
        "contacts": ["info.txt"],
        "vegetarian": ["menu_today.txt"]
    }
} 
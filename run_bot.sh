#!/bin/bash

# Ollama Bot Launcher Script
# This script sets up and runs the basic Ollama bot

echo "🤖 Ollama Bot Launcher"
echo "======================"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed or not in PATH"
    exit 1
fi

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "📥 Installing requirements..."
pip install -r requirements.txt

# Check if Ollama is running
echo "🔍 Checking Ollama connection..."
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "❌ Ollama is not running or not accessible at http://localhost:11434"
    echo "💡 Please start Ollama first:"
    echo "   ollama serve"
    echo ""
    echo "   Or install Ollama if not installed:"
    echo "   curl -fsSL https://ollama.ai/install.sh | sh"
    exit 1
fi

echo "✅ Ollama is running!"

# Set default model if not set
if [ -z "$OLLAMA_MODEL" ]; then
    export OLLAMA_MODEL="llama3:latest"
    echo "🎯 Using default model: $OLLAMA_MODEL"
fi

# Run the bot
echo "🚀 Starting Ollama Bot..."
echo "=========================="
python3 ollama_bot.py 
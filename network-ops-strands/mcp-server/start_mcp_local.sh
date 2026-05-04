#!/bin/bash
# Start MCP server locally for development

set -e

echo "🚀 Starting External Context MCP Server (Local)"
echo ""

# Check if we're in the right directory
if [ ! -f "external_context_mcp.py" ]; then
    echo "❌ Error: Please run this script from the mcp-server directory"
    exit 1
fi

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "✓ Dependencies installed"
echo ""
echo "🔧 Starting MCP server on stdio..."
echo "   Press Ctrl+C to stop"
echo ""

# Run the MCP server
python external_context_mcp.py

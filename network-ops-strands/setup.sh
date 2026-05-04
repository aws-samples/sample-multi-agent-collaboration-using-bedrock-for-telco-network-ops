#!/bin/bash
# Setup script for Network Operations Strands Platform

set -e

echo "🚀 Setting up Network Operations Strands Platform..."
echo ""

# Check if we're in the right directory
if [ ! -f "setup.sh" ]; then
    echo "❌ Error: Please run this script from the network-ops-strands directory"
    exit 1
fi

# Backend setup
echo "📦 Setting up backend..."
if [ ! -d "backend/venv" ]; then
    echo "  Creating Python virtual environment..."
    python3 -m venv backend/venv
fi

echo "  Installing Python dependencies..."
backend/venv/bin/pip install --quiet --upgrade pip
backend/venv/bin/pip install --quiet -r backend/requirements.txt

echo "  ✓ Backend setup complete"
echo ""

# Frontend setup
echo "📦 Setting up frontend..."
if [ ! -d "frontend/node_modules" ]; then
    echo "  Installing Node.js dependencies..."
    cd frontend
    npm install --silent
    cd ..
    echo "  ✓ Frontend setup complete"
else
    echo "  ✓ Frontend dependencies already installed"
fi
echo ""

# Generate data if not exists
if [ ! -f "data/sites.csv" ]; then
    echo "📊 Generating synthetic data..."
    backend/venv/bin/python scripts/generate_data.py --sites 20 --profile qts --output data
    echo "  ✓ Data generation complete"
else
    echo "✓ Data already exists"
fi
echo ""

# Create .env files if they don't exist
if [ ! -f "backend/.env" ]; then
    echo "📝 Creating backend .env file..."
    cp backend/.env.example backend/.env
    echo "  ✓ Created backend/.env (please update with your values)"
fi

if [ ! -f "frontend/.env" ]; then
    echo "📝 Creating frontend .env file..."
    cp frontend/.env.example frontend/.env
    echo "  ✓ Created frontend/.env (please update with your values)"
fi
echo ""

echo "✅ Setup complete!"
echo ""
echo "📚 Next steps:"
echo "  1. Test the agents:"
echo "     backend/venv/bin/python backend/agents/maintenance_agent.py"
echo "     backend/venv/bin/python backend/agents/alarm_agent.py"
echo "     backend/venv/bin/python backend/agents/kpi_agent.py"
echo ""
echo "  2. Start frontend development server:"
echo "     cd frontend && npm run dev"
echo ""
echo "  3. See PROGRESS.md for implementation status"
echo "  4. See README.md for full documentation"
echo ""

#!/bin/bash
# Start frontend (and optionally backend) for local development
#
# Modes:
#   ./start-local.sh              → Local backend + frontend (default)
#   ./start-local.sh --agentcore  → Frontend only, hitting AgentCore directly
#
# The MCP server (external context: power outages, weather, 811 dig requests)
# is automatically spawned by the supervisor agent via stdio transport in local mode.

set -e

# Defaults
USE_AGENTCORE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --agentcore)
      USE_AGENTCORE=true
      shift
      ;;
    --help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --agentcore   Skip local backend; frontend hits AgentCore directly"
      echo "  --help        Show this help"
      echo ""
      echo "Examples:"
      echo "  $0                # Local backend + frontend"
      echo "  $0 --agentcore    # Frontend only → AgentCore supervisor"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

echo "🚀 Starting Network Operations Platform (Local Development)"
if [ "$USE_AGENTCORE" = true ]; then
  echo "   Mode:     AgentCore (frontend only → deployed agent)"
else
  echo "   Mode:     Local (backend + frontend)"
fi
echo "   Frontend: React + TypeScript"
echo ""

# Set AWS region
export AWS_REGION=${AWS_REGION:-us-east-1}
echo "📍 AWS Region: $AWS_REGION"

# Load backend .env if it exists (picks up MEMORY_ID, etc.)
if [ -f "backend/.env" ]; then
    set -a
    source backend/.env
    set +a
    echo "📄 Loaded backend/.env"
    if [ -n "$MEMORY_ID" ]; then
        echo "   🧠 MEMORY_ID: ${MEMORY_ID:0:20}..."
    fi
fi
echo ""

# Check if we're in the right directory
if [ ! -f "start-local.sh" ]; then
    echo "❌ Error: Please run this script from the network-ops-strands directory"
    exit 1
fi

# Check for AWS credentials
echo "🔍 Checking AWS credentials..."
if ! aws sts get-caller-identity &>/dev/null; then
    echo "❌ Error: No valid AWS credentials found"
    echo "   Configure with: aws configure"
    exit 1
fi

AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
AWS_USER=$(aws sts get-caller-identity --query Arn --output text 2>/dev/null | cut -d'/' -f2)
echo "✓ AWS credentials found"
echo "   Account: $AWS_ACCOUNT"
echo "   User: $AWS_USER"
echo ""

# --- AgentCore mode: frontend only ---
if [ "$USE_AGENTCORE" = true ]; then
    # Get agent ARN from backend/.env or environment
    if [ -z "$AGENTCORE_ARN" ]; then
        # Try to read from the .env file written by deploy.sh
        AGENTCORE_ARN=$(grep '^AGENTCORE_ARN=' backend/.env 2>/dev/null | cut -d= -f2 || echo "")
    fi

    if [ -z "$AGENTCORE_ARN" ]; then
        echo "❌ Error: AGENTCORE_ARN not found"
        echo "   Set it in backend/.env or export it:"
        echo "   export AGENTCORE_ARN=arn:aws:bedrock-agentcore:us-east-1:...:runtime/..."
        exit 1
    fi

    echo "🤖 AgentCore agent: $AGENTCORE_ARN"
    echo ""

    # Write frontend .env.local for AgentCore mode
    cat > frontend/.env.local << EOF
VITE_AGENTCORE_ARN=$AGENTCORE_ARN
VITE_REGION=$AWS_REGION
EOF
    echo "✓ frontend/.env.local written with AgentCore ARN"
    echo ""

    # Check frontend deps
    if [ ! -d "frontend/node_modules" ]; then
        echo "⚠️  Frontend node_modules not found. Running npm install..."
        cd frontend && npm install && cd ..
    fi

    echo "🎨 Starting frontend (AgentCore mode)..."
    echo "   Frontend URL: http://localhost:3000"
    echo "   Agent: $AGENTCORE_ARN"
    echo ""
    echo "📝 Press Ctrl+C to stop"
    echo ""

    cd frontend
    npm run dev
    exit 0
fi

# --- Local mode: backend + frontend ---

# Check if setup has been run
if [ ! -d "backend/venv" ]; then
    echo "⚠️  Backend venv not found. Running setup..."
    ./setup.sh
fi

if [ ! -d "frontend/node_modules" ]; then
    echo "⚠️  Frontend node_modules not found. Running setup..."
    ./setup.sh
fi

# Remove AgentCore .env.local if it exists (so frontend uses local backend)
rm -f frontend/.env.local

# Activate virtual environment and check dependencies
echo "📦 Checking backend dependencies..."
cd backend
source venv/bin/activate

if ! python3 -c "import strands" 2>/dev/null; then
    echo "📥 Installing Strands dependencies..."
    pip install -q -r requirements.txt
fi

if ! python3 -c "import awscrt" 2>/dev/null; then
    echo "📥 Installing botocore[crt]..."
    pip install -q 'botocore[crt]'
fi

cd ..
echo "✓ Backend dependencies ready"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Stopping all servers..."
    kill $BACKEND_PID 2>/dev/null || true
    echo "✓ Servers stopped"
    exit 0
}
trap cleanup INT TERM

# Start backend
echo "🔧 Starting backend API server with Strands agents..."
echo "   - Supervisor Agent (Claude 4.5 Sonnet)"
echo "   - Maintenance Agent (Nova 2 Lite)"
echo "   - Alarm Agent (Nova 2 Lite)"
echo "   - KPI Agent (Nova 2 Lite)"
echo "   - MCP: External Context (power, weather, 811) via stdio"
echo ""
backend/venv/bin/python backend/api_server.py &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"
echo "   Backend URL: http://localhost:8000"
echo "   API Docs:    http://localhost:8000/docs"
echo ""

sleep 3

# Start frontend
echo "🎨 Starting frontend development server..."
echo "   Frontend URL: http://localhost:3000"
echo ""
echo "📝 Press Ctrl+C to stop all servers"
echo ""
echo "💡 Try these queries in the chat:"
echo "   - Check maintenance for site_atlanta_001"
echo "   - Show all critical alarms"
echo "   - Analyze performance for site_dallas_003"
echo "   - Why is site_richmond_008 down? (triggers MCP external context)"
echo ""

cd frontend
npm run dev

cleanup

#!/bin/bash
##############################################################################
# Deploy External Context MCP Server to AgentCore Gateway
#
# This deploys the MCP server that provides external context tools:
# - check_power_outages: Utility power outage data
# - check_811_dig_requests: Excavation activity near sites
# - check_weather_events: Severe weather events
# - get_external_context_summary: Combined root cause analysis
#
# Called by: deploy.sh (Step 5.5)
# Can also be run standalone.
#
# Usage:
#   ./scripts/deploy_mcp_server.sh
#   ./scripts/deploy_mcp_server.sh --region us-east-1 --stack-name netops
##############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
STACK_NAME=${STACK_NAME:-netops}
REGION=${AWS_REGION:-us-east-1}
MCP_NAME="external_context"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --region)
      REGION="$2"
      shift 2
      ;;
    --stack-name)
      STACK_NAME="$2"
      shift 2
      ;;
    --mcp-name)
      MCP_NAME="$2"
      shift 2
      ;;
    --help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --region REGION         AWS region (default: us-east-1)"
      echo "  --stack-name NAME       Stack name (default: netops)"
      echo "  --mcp-name NAME         MCP server name (default: external-context)"
      echo "  --help                  Show this help"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

echo -e "${BLUE}🌐 Deploying External Context MCP Server to AgentCore Gateway${NC}"
echo "   Region:    $REGION"
echo "   MCP Name:  $MCP_NAME"
echo ""

# Check if we're in the right directory
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ ! -d "$SCRIPT_DIR/mcp-server" ]; then
    echo -e "${RED}❌ Error: mcp-server directory not found at $SCRIPT_DIR${NC}"
    exit 1
fi

# Change to the project root
cd "$SCRIPT_DIR"

# Activate backend venv if available (agentcore CLI is installed there)
if [ -d "backend/venv/bin" ]; then
    source backend/venv/bin/activate
fi

# Check for AgentCore CLI
if ! command -v agentcore &> /dev/null; then
    echo -e "${YELLOW}📥 Installing AgentCore CLI...${NC}"
    pip install bedrock-agentcore-starter-toolkit
fi

# Navigate to MCP server directory
cd mcp-server

# Configure AgentCore deployment
echo -e "${YELLOW}⚙️  Configuring AgentCore...${NC}"
agentcore configure \
    --entrypoint external_context_mcp.py \
    --non-interactive \
    --name "$MCP_NAME" \
    --region "$REGION" \
    --requirements-file requirements.txt \
    --runtime PYTHON_3_11 \
    --protocol MCP

echo -e "${GREEN}✓ Configuration complete${NC}"
echo ""

# Set environment variable for runtime mode
export AGENTCORE_RUNTIME=true

# Deploy using AgentCore CLI
echo -e "${YELLOW}🚀 Deploying to AgentCore...${NC}"
agentcore launch --agent "$MCP_NAME" --auto-update-on-conflict --force-rebuild-deps --env MCP_TRANSPORT=http

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ MCP Server deployed successfully${NC}"
    echo ""

    # Show status
    echo -e "${BLUE}📋 MCP Server Status:${NC}"
    agentcore status --agent "$MCP_NAME" 2>/dev/null || true
    echo ""

    # Run validation
    echo -e "${YELLOW}🧪 Validating MCP server...${NC}"
    echo ""

    # Check server status
    echo -e "${BLUE}  Checking server status...${NC}"
    STATUS=$(agentcore status --agent "$MCP_NAME" 2>/dev/null || echo "")
    if echo "$STATUS" | grep -qi "Ready\|READY\|running"; then
      echo -e "${GREEN}  ✓ MCP server is running and ready${NC}"
    else
      echo -e "${YELLOW}  ⚠️  MCP server status unclear (may still be initializing)${NC}"
    fi

    # Check protocol is MCP
    PROTOCOL=$(agentcore status --agent "$MCP_NAME" --verbose 2>/dev/null | grep -i "serverProtocol" || echo "")
    if echo "$PROTOCOL" | grep -qi "MCP"; then
      echo -e "${GREEN}  ✓ Server protocol: MCP${NC}"
    else
      echo -e "${YELLOW}  ⚠️  Server protocol not confirmed as MCP${NC}"
    fi

    echo ""
    echo -e "${GREEN}✓ MCP server validation complete${NC}"
    echo -e "${BLUE}  Tools available: check_power_outages, check_811_dig_requests,${NC}"
    echo -e "${BLUE}                   check_weather_events, get_external_context_summary${NC}"
else
    echo -e "${RED}✗ MCP Server deployment failed${NC}"
    exit 1
fi

cd ..

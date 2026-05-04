#!/bin/bash
##############################################################################
# Deploy AgentCore Memory for the Network Operations Platform
#
# Creates an LTM memory resource with semantic extraction and writes
# the MEMORY_ID to backend/.env so start-local.sh picks it up.
#
# Called by: deploy.sh (can also be run standalone)
#
# Usage:
#   ./scripts/deploy_memory.sh
#   ./scripts/deploy_memory.sh --region us-west-2
##############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

REGION=${AWS_REGION:-us-east-1}
NAME_PREFIX="netops"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --region)
      REGION="$2"
      shift 2
      ;;
    --name-prefix)
      NAME_PREFIX="$2"
      shift 2
      ;;
    --help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --region REGION           AWS region (default: us-east-1)"
      echo "  --name-prefix PREFIX      Memory name prefix (default: netops)"
      echo "  --help                    Show this help"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

echo -e "${BLUE}🧠 Deploying AgentCore Memory${NC}"
echo "   Region: $REGION"
echo "   Prefix: $NAME_PREFIX"
echo ""

# Check if we're in the right directory
if [ ! -d "scripts" ]; then
    echo -e "${RED}❌ Error: Run from the network-ops-strands directory${NC}"
    exit 1
fi

# Determine which python to use
if [ -d "backend/venv" ]; then
    PYTHON="backend/venv/bin/python"
else
    PYTHON="python3"
fi

# Check dependencies
if ! $PYTHON -c "from bedrock_agentcore_starter_toolkit.operations.memory.manager import MemoryManager" 2>/dev/null; then
    echo -e "${YELLOW}📥 Installing bedrock-agentcore-starter-toolkit...${NC}"
    $PYTHON -m pip install -q bedrock-agentcore-starter-toolkit
fi

# Run the setup script and capture the memory ID
echo -e "${YELLOW}⚙️  Creating memory resource...${NC}"
MEMORY_ID=$($PYTHON -c "
import sys
sys.path.insert(0, 'scripts')
from bedrock_agentcore_starter_toolkit.operations.memory.manager import MemoryManager
from bedrock_agentcore_starter_toolkit.operations.memory.models.strategies import SemanticStrategy

manager = MemoryManager(region_name='$REGION')
ltm = manager.get_or_create_memory(
    name='${NAME_PREFIX}_ltm',
    description='Network Operations long-term memory with semantic extraction',
    strategies=[
        SemanticStrategy(
            name='operatorPreferences',
            namespaces=['/strategies/{memoryStrategyId}/actors/{actorId}/'],
        ),
    ],
)
print(ltm.get('id'))
")

if [ -z "$MEMORY_ID" ]; then
    echo -e "${RED}❌ Failed to create memory resource${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Memory resource created: ${MEMORY_ID}${NC}"
echo ""

# Write to backend/.env
ENV_FILE="backend/.env"
if [ -f "$ENV_FILE" ]; then
    # Update existing MEMORY_ID or append
    if grep -q "^MEMORY_ID=" "$ENV_FILE"; then
        sed -i.bak "s/^MEMORY_ID=.*/MEMORY_ID=$MEMORY_ID/" "$ENV_FILE"
        rm -f "${ENV_FILE}.bak"
        echo -e "${GREEN}✓ Updated MEMORY_ID in $ENV_FILE${NC}"
    else
        echo "MEMORY_ID=$MEMORY_ID" >> "$ENV_FILE"
        echo -e "${GREEN}✓ Added MEMORY_ID to $ENV_FILE${NC}"
    fi
else
    echo "MEMORY_ID=$MEMORY_ID" > "$ENV_FILE"
    echo -e "${GREEN}✓ Created $ENV_FILE with MEMORY_ID${NC}"
fi

echo ""
echo -e "${BLUE}📋 Memory ID: ${GREEN}$MEMORY_ID${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  The MEMORY_ID has been written to backend/.env"
echo "  start-local.sh will pick it up automatically."
echo ""
echo "  Or export manually:"
echo "    export MEMORY_ID=$MEMORY_ID"

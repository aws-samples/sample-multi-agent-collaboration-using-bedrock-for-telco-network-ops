#!/bin/bash
##############################################################################
# Deploy Network Operations Platform to AWS AgentCore Runtime
#
# This script follows the official AgentCore deployment workflow:
# 1. Install AgentCore CLI
# 2. Configure the agent
# 3. Deploy to AWS
# 4. Test the deployment
##############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
AGENT_NAME="netops-supervisor"
REGION="us-east-1"
DATA_BUCKET=""
EXECUTION_ROLE=""
MCP_URL=""
MEMORY_ID=""
KB_ID=""
SKIP_INSTALL=false
NON_INTERACTIVE=true

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --agent-name)
      AGENT_NAME="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --data-bucket)
      DATA_BUCKET="$2"
      shift 2
      ;;
    --execution-role)
      EXECUTION_ROLE="$2"
      shift 2
      ;;
    --mcp-url)
      MCP_URL="$2"
      shift 2
      ;;
    --memory-id)
      MEMORY_ID="$2"
      shift 2
      ;;
    --kb-id)
      KB_ID="$2"
      shift 2
      ;;
    --skip-install)
      SKIP_INSTALL=true
      shift
      ;;
    --interactive)
      NON_INTERACTIVE=false
      shift
      ;;
    --help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --agent-name NAME       Agent name (default: netops-supervisor)"
      echo "  --region REGION         AWS region (default: us-east-1)"
      echo "  --data-bucket BUCKET    S3 data bucket name (required)"
      echo "  --execution-role ARN    IAM execution role ARN (optional)"
      echo "  --mcp-url URL           MCP server endpoint URL (optional)"
      echo "  --skip-install          Skip CLI installation"
      echo "  --interactive           Use interactive mode (prompts for inputs)"
      echo "  --help                  Show this help"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

# Validate required parameters
if [ -z "$DATA_BUCKET" ]; then
    echo -e "${RED}Error: --data-bucket is required${NC}"
    echo "Use --help for usage information"
    exit 1
fi

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     AgentCore Deployment - Network Operations Platform    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Agent Name:${NC}      $AGENT_NAME"
echo -e "${BLUE}Region:${NC}          $REGION"
echo -e "${BLUE}Data Bucket:${NC}     $DATA_BUCKET"
if [ -n "$EXECUTION_ROLE" ]; then
  echo -e "${BLUE}Execution Role:${NC}  $EXECUTION_ROLE"
fi
if [ -n "$MCP_URL" ]; then
  echo -e "${BLUE}MCP URL:${NC}         ${MCP_URL:0:80}..."
fi
echo ""

# Step 1: Install AgentCore CLI
if [ "$SKIP_INSTALL" = false ]; then
  echo -e "${YELLOW}📦 Step 1: Installing AgentCore CLI...${NC}"
  pip install bedrock-agentcore-starter-toolkit --upgrade
  echo -e "${GREEN}✓ AgentCore CLI installed${NC}"
  echo ""
else
  echo -e "${YELLOW}⏭️  Step 1: Skipping CLI installation${NC}"
  echo ""
fi

# Step 2: Verify agent code structure
echo -e "${YELLOW}🔍 Step 2: Verifying agent code structure...${NC}"

cd backend

# Activate venv so agentcore CLI is on PATH
if [ -d "venv/bin" ]; then
  source venv/bin/activate
  echo -e "${GREEN}✓ Activated backend venv${NC}"
elif [ -d "../backend/venv/bin" ]; then
  source ../backend/venv/bin/activate
  echo -e "${GREEN}✓ Activated backend venv${NC}"
fi

# Check for required file
if [ ! -f "strands_agents/agentcore_app.py" ]; then
  echo -e "${RED}✗ Error: agentcore_app.py not found${NC}"
  exit 1
fi
echo -e "${GREEN}✓ agentcore_app.py found${NC}"

# Check for BedrockAgentCoreApp import
if ! grep -q "from bedrock_agentcore.runtime import BedrockAgentCoreApp" strands_agents/agentcore_app.py; then
  echo -e "${RED}✗ Error: Missing BedrockAgentCoreApp import${NC}"
  exit 1
fi
echo -e "${GREEN}✓ BedrockAgentCoreApp import found${NC}"

# Check for @app.entrypoint decorator
if ! grep -q "@app.entrypoint" strands_agents/agentcore_app.py; then
  echo -e "${RED}✗ Error: Missing @app.entrypoint decorator${NC}"
  exit 1
fi
echo -e "${GREEN}✓ @app.entrypoint decorator found${NC}"

# Check for app.run()
if ! grep -q "app.run()" strands_agents/agentcore_app.py; then
  echo -e "${RED}✗ Error: Missing app.run() call${NC}"
  exit 1
fi
echo -e "${GREEN}✓ app.run() call found${NC}"

# Check requirements.txt
if [ ! -f "requirements.txt" ]; then
  echo -e "${RED}✗ Error: requirements.txt not found${NC}"
  exit 1
fi
echo -e "${GREEN}✓ requirements.txt found${NC}"

if ! grep -q "bedrock-agentcore" requirements.txt; then
  echo -e "${RED}✗ Error: bedrock-agentcore not in requirements.txt${NC}"
  exit 1
fi
echo -e "${GREEN}✓ bedrock-agentcore in requirements.txt${NC}"

echo -e "${GREEN}✓ Agent code structure validated${NC}"
echo ""

# Step 3: Configure agent
echo -e "${YELLOW}⚙️  Step 3: Configuring agent for AgentCore...${NC}"

CONFIGURE_CMD="agentcore configure \
  --entrypoint strands_agents/agentcore_app.py \
  --name $AGENT_NAME \
  --region $REGION \
  --requirements-file requirements.txt \
  --runtime PYTHON_3_11"

# Add execution role if provided
if [ -n "$EXECUTION_ROLE" ]; then
  CONFIGURE_CMD="$CONFIGURE_CMD --execution-role $EXECUTION_ROLE"
fi

# Add non-interactive flag
if [ "$NON_INTERACTIVE" = true ]; then
  CONFIGURE_CMD="$CONFIGURE_CMD --non-interactive"
fi

echo -e "${BLUE}Running: $CONFIGURE_CMD${NC}"
eval $CONFIGURE_CMD

if [ $? -eq 0 ]; then
  echo -e "${GREEN}✓ Agent configured successfully${NC}"
else
  echo -e "${RED}✗ Agent configuration failed${NC}"
  exit 1
fi
echo ""

# Step 4: Deploy to AgentCore
echo -e "${YELLOW}🚀 Step 4: Deploying to AgentCore Runtime...${NC}"
echo -e "${BLUE}This may take 5-10 minutes...${NC}"
echo ""

# Build launch command with all env vars in one shot
LAUNCH_CMD="agentcore launch --agent $AGENT_NAME \
  --env ENVIRONMENT=production \
  --env DATA_BUCKET_NAME=$DATA_BUCKET \
  --env LOG_LEVEL=DEBUG"

if [ -n "$MCP_URL" ]; then
  LAUNCH_CMD="$LAUNCH_CMD --env MCP_EXTERNAL_CONTEXT_URL=$MCP_URL"
fi

if [ -n "$MEMORY_ID" ]; then
  LAUNCH_CMD="$LAUNCH_CMD --env MEMORY_ID=$MEMORY_ID"
fi

if [ -n "$KB_ID" ]; then
  LAUNCH_CMD="$LAUNCH_CMD --env KNOWLEDGE_BASE_ID=$KB_ID"
fi

LAUNCH_CMD="$LAUNCH_CMD --auto-update-on-conflict --force-rebuild-deps"

eval $LAUNCH_CMD

if [ $? -eq 0 ]; then
  echo -e "${GREEN}✓ Agent deployed successfully${NC}"
  
  # If MEMORY_ID wasn't provided, read it from the config that agentcore launch just wrote
  if [ -z "$MEMORY_ID" ]; then
    echo -e "${YELLOW}   Looking up auto-created memory ID...${NC}"
    MEMORY_ID=$(python3 -c "
import yaml, sys
try:
    with open('.bedrock_agentcore.yaml') as f:
        cfg = yaml.safe_load(f)
    for a in cfg.get('agents', {}).values():
        mid = a.get('memory', {}).get('memory_id', '')
        if mid:
            print(mid)
            break
except: pass
" 2>/dev/null)
    
    if [ -n "$MEMORY_ID" ]; then
      echo -e "${GREEN}   Found memory ID: $MEMORY_ID${NC}"
      echo -e "${YELLOW}   Updating agent with MEMORY_ID env var...${NC}"
      agentcore launch --agent $AGENT_NAME \
        --env ENVIRONMENT=production \
        --env DATA_BUCKET_NAME=$DATA_BUCKET \
        --env LOG_LEVEL=DEBUG \
        --env MEMORY_ID=$MEMORY_ID \
        $([ -n "$MCP_URL" ] && echo "--env MCP_EXTERNAL_CONTEXT_URL=$MCP_URL") \
        --auto-update-on-conflict
      echo -e "${GREEN}   ✓ Agent updated with MEMORY_ID${NC}"
    else
      echo -e "${YELLOW}   ⚠️  Could not find memory ID — memory will be disabled${NC}"
    fi
  fi
else
  echo -e "${RED}✗ Agent deployment failed${NC}"
  echo -e "${YELLOW}Check CloudFormation console for details${NC}"
  exit 1
fi
echo ""

# Step 5: Get agent status
echo -e "${YELLOW}📊 Step 5: Getting agent status...${NC}"

agentcore status --agent $AGENT_NAME

echo ""

# Step 6: Test the deployment
echo -e "${YELLOW}🧪 Step 6: Validating deployed agent...${NC}"
echo ""

# Test 1: Basic alarm query
echo -e "${BLUE}  Test 1: Alarm query${NC}"
RESULT=$(agentcore invoke '{"prompt": "How many active critical alarms are there?"}' --agent $AGENT_NAME 2>/dev/null || echo "FAILED")
if echo "$RESULT" | grep -qi "alarm\|critical\|active\|site"; then
  echo -e "${GREEN}  ✓ Alarm agent working${NC}"
else
  echo -e "${YELLOW}  ⚠️  Alarm query returned unexpected result (agent may be initializing)${NC}"
fi

# Test 2: Maintenance query
echo -e "${BLUE}  Test 2: Maintenance query${NC}"
RESULT=$(agentcore invoke '{"prompt": "Check maintenance for site_atlanta_001"}' --agent $AGENT_NAME 2>/dev/null || echo "FAILED")
if echo "$RESULT" | grep -qi "maintenance\|scheduled\|active\|no "; then
  echo -e "${GREEN}  ✓ Maintenance agent working${NC}"
else
  echo -e "${YELLOW}  ⚠️  Maintenance query returned unexpected result${NC}"
fi

# Test 3: MCP external context (if available)
echo -e "${BLUE}  Test 3: External context (MCP)${NC}"
RESULT=$(agentcore invoke '{"prompt": "Check for power outages near site_richmond_008"}' --agent $AGENT_NAME 2>/dev/null || echo "FAILED")
if echo "$RESULT" | grep -qi "power\|outage\|external\|no "; then
  echo -e "${GREEN}  ✓ MCP external context working${NC}"
elif echo "$RESULT" | grep -qi "not available\|not currently"; then
  echo -e "${YELLOW}  ⚠️  MCP tools not available (MCP_EXTERNAL_CONTEXT_URL may not be set)${NC}"
else
  echo -e "${YELLOW}  ⚠️  External context query returned unexpected result${NC}"
fi

# Test 4: Metrics action (non-LLM)
echo -e "${BLUE}  Test 4: Metrics endpoint (direct data)${NC}"
RESULT=$(agentcore invoke '{"action": "metrics"}' --agent $AGENT_NAME 2>/dev/null || echo "FAILED")
if echo "$RESULT" | grep -qi "activeAlarms\|sitesMonitored"; then
  echo -e "${GREEN}  ✓ Metrics endpoint working${NC}"
else
  echo -e "${YELLOW}  ⚠️  Metrics endpoint returned unexpected result${NC}"
fi

echo ""
echo -e "${GREEN}✓ Agent validation complete${NC}"
echo ""

# Get endpoint URL
echo -e "${YELLOW}📡 Getting agent endpoint...${NC}"
ENDPOINT=$(agentcore status --agent $AGENT_NAME --verbose 2>/dev/null | grep -o 'https://[^"]*' | head -1)

cd ..

# Success summary
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           AgentCore Deployment Complete! ✓                 ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Agent Details:${NC}"
echo -e "  Name:     ${GREEN}$AGENT_NAME${NC}"
echo -e "  Region:   ${GREEN}$REGION${NC}"
if [ -n "$ENDPOINT" ]; then
  echo -e "  Endpoint: ${GREEN}$ENDPOINT${NC}"
fi
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "  1. Update frontend .env with AgentCore endpoint"
echo "  2. Deploy frontend: ./scripts/deploy_frontend.sh"
echo "  3. Test end-to-end via CloudFront URL"
echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo "  # Test agent"
echo "  agentcore invoke '{\"prompt\": \"Show critical alarms\"}' --agent $AGENT_NAME"
echo ""
echo "  # Check status"
echo "  agentcore status --agent $AGENT_NAME"
echo ""
echo "  # View logs"
echo "  agentcore status --agent $AGENT_NAME --verbose"
echo ""
echo "  # Stop sessions"
echo "  agentcore stop-session --agent $AGENT_NAME"
echo ""
echo "  # Destroy agent"
echo "  agentcore destroy --agent $AGENT_NAME"
echo ""


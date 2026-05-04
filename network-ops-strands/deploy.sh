#!/bin/bash

##############################################################################
# Network Operations Platform - Unified Deployment Script
#
# This script deploys the entire platform using AWS SAM:
# - S3 buckets (frontend, data, config)
# - Cognito (authentication)
# - IAM roles
# - Lambda@Edge (JWT authorization)
# - CloudFront (CDN)
# - AgentCore agents
# - Frontend application
#
# Usage:
#   ./deploy.sh                    # Deploy with defaults
#   ./deploy.sh --guided           # Interactive deployment
#   ./deploy.sh --stack-name prod  # Deploy to prod
##############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
STACK_NAME="netops"
REGION="us-east-1"
GUIDED=false
SKIP_INFRA=false
SKIP_DATA=false
SKIP_MEMORY=false
SKIP_AGENTS=false
SKIP_MCP=false
SKIP_KB=false
SKIP_FRONTEND=false
CREATE_DEMO_USER=false
DEMO_USERNAME="netopsuser@example.com"
DEMO_PASSWORD="NetworkOps2026!"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --stack-name)
      STACK_NAME="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --guided)
      GUIDED=true
      shift
      ;;
    --skip-infra)
      SKIP_INFRA=true
      shift
      ;;
    --skip-data)
      SKIP_DATA=true
      shift
      ;;
    --skip-memory)
      SKIP_MEMORY=true
      shift
      ;;
    --skip-agents)
      SKIP_AGENTS=true
      shift
      ;;
    --skip-mcp)
      SKIP_MCP=true
      shift
      ;;
    --skip-kb)
      SKIP_KB=true
      shift
      ;;
    --skip-frontend)
      SKIP_FRONTEND=true
      shift
      ;;
    --create-demo-user)
      CREATE_DEMO_USER=true
      shift
      ;;
    --demo-username)
      DEMO_USERNAME="$2"
      shift 2
      ;;
    --demo-password)
      DEMO_PASSWORD="$2"
      shift 2
      ;;
    --help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --stack-name NAME       Stack name (default: netops)"
      echo "  --region REGION         AWS region (default: us-east-1)"
      echo "  --guided                Interactive deployment"
      echo "  --skip-infra            Skip SAM build & deploy (Steps 1-3)"
      echo "  --skip-data             Skip data upload (Step 4)"
      echo "  --skip-memory           Skip AgentCore Memory setup (Step 4.5)"
      echo "  --skip-agents           Skip AgentCore agent deployment (Step 5)"
      echo "  --skip-mcp              Skip MCP server deployment (Step 5.5)"
      echo "  --skip-kb               Skip Knowledge Base deployment (Step 4.6)"
      echo "  --skip-frontend         Skip frontend deployment (Step 6)"
      echo "  --create-demo-user      Create demo users in Cognito (Step 3.5)"
      echo "  --demo-username EMAIL   Demo user email (default: netopsuser@example.com)"
      echo "  --demo-password PASS    Demo user password (default: NetworkOps2026!)"
      echo "  --help                  Show this help"
      echo ""
      echo "Examples:"
      echo "  $0                                    # Full deploy"
      echo "  $0 --create-demo-user                 # Full deploy + demo users"
      echo "  $0 --skip-infra --skip-data           # Re-deploy agents + frontend only"
      echo "  $0 --skip-infra --skip-data --skip-agents --skip-mcp  # Frontend only"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Network Operations Platform - Unified Deployment      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Steps 1-3: SAM validate, build, deploy
if [ "$SKIP_INFRA" = false ]; then
  echo -e "${BLUE}📋 Step 1: Validating SAM template...${NC}"
  sam validate --lint
  echo -e "${GREEN}✓ Template validated${NC}"
  echo ""

  echo -e "${BLUE}🔨 Step 2: Building SAM application...${NC}"
  sam build
  echo -e "${GREEN}✓ Build complete${NC}"
  echo ""

  echo -e "${BLUE}☁️  Step 3: Deploying infrastructure...${NC}"
  if [ "$GUIDED" = true ]; then
    sam deploy --guided --stack-name "$STACK_NAME" --region "$REGION"
  else
    sam deploy --stack-name "$STACK_NAME" --region "$REGION"
  fi
  echo -e "${GREEN}✓ Infrastructure deployed${NC}"
  echo ""
else
  echo -e "${YELLOW}⏭️  Steps 1-3: Skipping infrastructure (SAM build & deploy)${NC}"
  echo ""
fi

# Always fetch stack outputs (needed by later steps)
echo -e "${BLUE}📤 Getting stack outputs...${NC}"
OUTPUTS=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs' \
  --output json)

DATA_BUCKET=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="DataBucketName") | .OutputValue')
FRONTEND_BUCKET=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="FrontendBucketName") | .OutputValue')
DISTRIBUTION_ID=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="CloudFrontDistributionId") | .OutputValue')
AGENTCORE_ROLE=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="AgentCoreExecutionRoleArn") | .OutputValue')
APP_URL=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="ApplicationURL") | .OutputValue')
USER_POOL_ID=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="UserPoolId") | .OutputValue')
API_ENDPOINT=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="ApiEndpoint") | .OutputValue')

echo -e "${GREEN}✓ Outputs retrieved${NC}"
echo ""

# Step 3.5: Create demo users (if requested)
if [ "$CREATE_DEMO_USER" = true ]; then
  echo -e "${BLUE}👤 Step 3.5: Creating demo users in Cognito...${NC}"
  
  if [ -z "$USER_POOL_ID" ] || [ "$USER_POOL_ID" = "null" ]; then
    echo -e "${RED}❌ Error: Could not find Cognito User Pool ID${NC}"
    echo -e "${YELLOW}   Skipping demo user creation${NC}"
  else
    # Create primary demo user
    echo -e "${YELLOW}   Creating user 1: $DEMO_USERNAME${NC}"
    
    aws cognito-idp admin-create-user \
      --user-pool-id "$USER_POOL_ID" \
      --username "$DEMO_USERNAME" \
      --user-attributes \
        Name=email,Value="$DEMO_USERNAME" \
        Name=email_verified,Value=true \
        Name=name,Value="Network Ops Operator 1" \
      --message-action SUPPRESS \
      --region "$REGION" \
      --output text \
      --no-cli-pager > /dev/null 2>&1 || true
    
    aws cognito-idp admin-set-user-password \
      --user-pool-id "$USER_POOL_ID" \
      --username "$DEMO_USERNAME" \
      --password "$DEMO_PASSWORD" \
      --permanent \
      --region "$REGION" \
      --output text \
      --no-cli-pager > /dev/null 2>&1

    # Create second demo user for memory demo
    DEMO_USER2="operator2@netops.demo"
    DEMO_PASS2="$DEMO_PASSWORD"
    echo -e "${YELLOW}   Creating user 2: $DEMO_USER2${NC}"
    
    aws cognito-idp admin-create-user \
      --user-pool-id "$USER_POOL_ID" \
      --username "$DEMO_USER2" \
      --user-attributes \
        Name=email,Value="$DEMO_USER2" \
        Name=email_verified,Value=true \
        Name=name,Value="Network Ops Operator 2" \
      --message-action SUPPRESS \
      --region "$REGION" \
      --output text \
      --no-cli-pager > /dev/null 2>&1 || true
    
    aws cognito-idp admin-set-user-password \
      --user-pool-id "$USER_POOL_ID" \
      --username "$DEMO_USER2" \
      --password "$DEMO_PASS2" \
      --permanent \
      --region "$REGION" \
      --output text \
      --no-cli-pager > /dev/null 2>&1

    echo -e "${GREEN}✓ Demo users created${NC}"
    echo -e "${BLUE}   User 1: ${GREEN}$DEMO_USERNAME${NC} / ${GREEN}$DEMO_PASSWORD${NC}"
    echo -e "${BLUE}   User 2: ${GREEN}$DEMO_USER2${NC} / ${GREEN}$DEMO_PASS2${NC}"
  fi
  echo ""
fi

# Step 4: Upload data
if [ "$SKIP_DATA" = false ]; then
  echo -e "${BLUE}📦 Step 4: Uploading data to S3...${NC}"
  ./scripts/upload_data.sh --bucket "$DATA_BUCKET"
  echo -e "${GREEN}✓ Data uploaded${NC}"
else
  echo -e "${YELLOW}⏭️  Step 4: Skipping data upload${NC}"
fi
echo ""

# Step 4.5: Deploy AgentCore Memory (LTM with semantic extraction)
# Note: agentcore launch auto-creates STM memory. This step adds LTM.
if [ "$SKIP_MEMORY" = false ]; then
  echo -e "${BLUE}🧠 Step 4.5: Deploying AgentCore Memory (LTM)...${NC}"
  echo -e "${YELLOW}   Note: STM memory is auto-created by agentcore launch${NC}"
  if ./scripts/deploy_memory.sh --region "$REGION"; then
    echo -e "${GREEN}✓ LTM Memory deployed${NC}"
  else
    echo -e "${YELLOW}⚠️  LTM Memory deployment failed (non-critical)${NC}"
    echo -e "${YELLOW}   STM memory will still be created by agentcore launch${NC}"
  fi
else
  echo -e "${YELLOW}⏭️  Step 4.5: Skipping memory deployment${NC}"
fi
echo ""

# Step 4.6: Deploy Knowledge Base (Bedrock KB with S3 Vectors)
if [ "$SKIP_KB" = false ]; then
  echo -e "${BLUE}📚 Step 4.6: Deploying Knowledge Base...${NC}"

  # Upload KB documents to S3
  if [ -d "data/knowledge-base" ]; then
    echo -e "${BLUE}   Uploading KB documents to S3...${NC}"
    aws s3 sync data/knowledge-base/ "s3://${DATA_BUCKET}/knowledge-base/" \
      --delete --region "$REGION" 2>/dev/null
    echo -e "${GREEN}   ✓ KB documents uploaded${NC}"
  else
    echo -e "${YELLOW}   Generating KB content first...${NC}"
    python3 scripts/generate_data.py --output data --profile datacenter 2>/dev/null
    aws s3 sync data/knowledge-base/ "s3://${DATA_BUCKET}/knowledge-base/" \
      --delete --region "$REGION" 2>/dev/null
    echo -e "${GREEN}   ✓ KB content generated and uploaded${NC}"
  fi

  # Check if KB already exists
  KB_NAME="${STACK_NAME}-dev-kb"
  EXISTING_KB=$(aws bedrock-agent list-knowledge-bases --region "$REGION" \
    --query "knowledgeBaseSummaries[?name=='${KB_NAME}'].knowledgeBaseId" \
    --output text 2>/dev/null || echo "")

  if [ -n "$EXISTING_KB" ] && [ "$EXISTING_KB" != "None" ]; then
    KB_ID="$EXISTING_KB"
    echo -e "${GREEN}   ✓ Found existing KB: $KB_ID${NC}"
  else
    echo -e "${BLUE}   Creating Knowledge Base with S3 Vectors...${NC}"

    # Get KB role ARN from infra stack
    KB_ROLE_ARN=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="KnowledgeBaseRoleArn") | .OutputValue' 2>/dev/null || echo "")
    if [ -z "$KB_ROLE_ARN" ] || [ "$KB_ROLE_ARN" = "null" ]; then
      # Fallback: construct from naming convention
      ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
      KB_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${STACK_NAME}-dev-kb-role"
    fi
    echo -e "${BLUE}   KB Role: $KB_ROLE_ARN${NC}"

    # Use Python SDK to create KB (CLI doesn't support S3_VECTORS)
    KB_ID=$(source backend/venv/bin/activate 2>/dev/null && python3 scripts/create_kb.py \
      --name "$KB_NAME" \
      --role-arn "$KB_ROLE_ARN" \
      --region "$REGION" \
      --bucket "$DATA_BUCKET" \
      --prefix "knowledge-base/" 2>&1 | tee /dev/stderr | tail -1)

    if [ -z "$KB_ID" ]; then
      echo -e "${YELLOW}⚠️  KB creation failed: $KB_RESPONSE${NC}"
    else
      echo -e "${GREEN}   ✓ Knowledge Base created: $KB_ID${NC}"

      # Wait for KB to be active
      echo -e "${YELLOW}   ⏳ Waiting for KB to become active...${NC}"
      for i in $(seq 1 30); do
        STATUS=$(aws bedrock-agent get-knowledge-base --knowledge-base-id "$KB_ID" \
          --region "$REGION" --query "knowledgeBase.status" --output text 2>/dev/null)
        if [ "$STATUS" = "ACTIVE" ]; then break; fi
        sleep 5
      done
      echo -e "${GREEN}   ✓ KB is ACTIVE${NC}"

      # Create S3 data source
      DS_RESPONSE=$(aws bedrock-agent create-data-source \
        --knowledge-base-id "$KB_ID" \
        --name "${KB_NAME}-s3-source" \
        --data-source-configuration '{
          "type": "S3",
          "s3Configuration": {
            "bucketArn": "arn:aws:s3:::'"$DATA_BUCKET"'",
            "inclusionPrefixes": ["knowledge-base/"]
          }
        }' \
        --region "$REGION" --output json 2>&1)

      DS_ID=$(echo "$DS_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['dataSource']['dataSourceId'])" 2>/dev/null || echo "")
      echo -e "${GREEN}   ✓ Data source created: $DS_ID${NC}"
    fi
  fi

  # Trigger ingestion if we have KB + data source
  if [ -n "$KB_ID" ] && [ "$KB_ID" != "None" ]; then
    DS_ID=${DS_ID:-$(aws bedrock-agent list-data-sources --knowledge-base-id "$KB_ID" \
      --region "$REGION" --query "dataSourceSummaries[0].dataSourceId" --output text 2>/dev/null)}
    if [ -n "$DS_ID" ] && [ "$DS_ID" != "None" ]; then
      echo -e "${BLUE}   Starting ingestion job...${NC}"
      aws bedrock-agent start-ingestion-job \
        --knowledge-base-id "$KB_ID" --data-source-id "$DS_ID" \
        --region "$REGION" >/dev/null 2>&1
      echo -e "${GREEN}   ✓ Ingestion started (runs in background, 1-3 min)${NC}"
    fi
  fi
else
  echo -e "${YELLOW}⏭️  Step 4.6: Skipping Knowledge Base deployment${NC}"
fi
echo ""

# Step 5: Deploy MCP server first (supervisor needs its URL)
MCP_ENDPOINT=""
if [ "$SKIP_MCP" = false ]; then
  echo -e "${BLUE}🌐 Step 5: Deploying MCP server to AgentCore...${NC}"
  if ./scripts/deploy_mcp_server.sh --region "$REGION" --stack-name "$STACK_NAME"; then
    echo -e "${GREEN}✓ MCP server deployed${NC}"

    # Construct MCP endpoint URL from the agent ARN
    MCP_ARN=$(cd mcp-server && source ../backend/venv/bin/activate 2>/dev/null && agentcore status --agent external_context --verbose 2>/dev/null | grep -A1 '"agent_arn"' | grep 'arn:' | sed 's/.*"\(arn:[^"]*\)".*/\1/' || echo "")
    
    if [ -n "$MCP_ARN" ]; then
      # URL-encode the ARN for the endpoint path
      ENCODED_ARN=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$MCP_ARN', safe=''))")
      MCP_ENDPOINT="https://bedrock-agentcore.${REGION}.amazonaws.com/runtimes/${ENCODED_ARN}/invocations?qualifier=DEFAULT"
      echo -e "${GREEN}✓ MCP endpoint: $MCP_ENDPOINT${NC}"
    else
      echo -e "${YELLOW}⚠️  Could not retrieve MCP agent ARN${NC}"
    fi
  else
    echo -e "${YELLOW}⚠️  MCP server deployment failed (non-critical)${NC}"
    echo -e "${YELLOW}   Supervisor will work without external context tools${NC}"
  fi
  echo ""
else
  echo -e "${YELLOW}⏭️  Step 5: Skipping MCP server deployment${NC}"
  # Still look up the existing MCP endpoint so the supervisor can use it
  MCP_ARN=$(cd mcp-server && source ../backend/venv/bin/activate 2>/dev/null && agentcore status --agent external_context --verbose 2>/dev/null | grep -A1 '"agent_arn"' | grep 'arn:' | sed 's/.*"\(arn:[^"]*\)".*/\1/' || echo "")
  if [ -n "$MCP_ARN" ]; then
    ENCODED_ARN=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$MCP_ARN', safe=''))")
    MCP_ENDPOINT="https://bedrock-agentcore.${REGION}.amazonaws.com/runtimes/${ENCODED_ARN}/invocations?qualifier=DEFAULT"
    echo -e "${GREEN}   Found existing MCP endpoint${NC}"
  fi
  echo ""
fi

# Step 5.5: Deploy supervisor agent to AgentCore (with MCP URL if available)
if [ "$SKIP_AGENTS" = false ]; then
  echo -e "${BLUE}🤖 Step 5.5: Deploying supervisor agent to AgentCore Runtime...${NC}"

  # Build args — include MCP endpoint and Memory ID if available
  EXTRA_ARGS=""
  if [ -n "$MCP_ENDPOINT" ]; then
    EXTRA_ARGS="--mcp-url $MCP_ENDPOINT"
    echo -e "${BLUE}   Including MCP endpoint in deploy${NC}"
  fi

  # Look up supervisor memory ID
  SUP_MEMORY_ID=$(cd backend && source venv/bin/activate 2>/dev/null && agentcore memory list --region "$REGION" 2>/dev/null | grep "${STACK_NAME}_supervisor_mem" | awk '{print $4}' || echo "")
  if [ -n "$SUP_MEMORY_ID" ]; then
    EXTRA_ARGS="$EXTRA_ARGS --memory-id $SUP_MEMORY_ID"
    echo -e "${BLUE}   Including Memory ID: $SUP_MEMORY_ID${NC}"
  fi

  # Look up Knowledge Base ID
  KB_NAME="${STACK_NAME}-dev-kb"
  KB_ID=$(aws bedrock-agent list-knowledge-bases --region "$REGION" \
    --query "knowledgeBaseSummaries[?name=='${KB_NAME}'].knowledgeBaseId" \
    --output text 2>/dev/null || echo "")
  if [ -n "$KB_ID" ] && [ "$KB_ID" != "None" ]; then
    EXTRA_ARGS="$EXTRA_ARGS --kb-id $KB_ID"
    echo -e "${BLUE}   Including Knowledge Base ID: $KB_ID${NC}"
  fi

  ./scripts/deploy_to_agentcore.sh \
    --agent-name "${STACK_NAME}_supervisor" \
    --region "$REGION" \
    --data-bucket "$DATA_BUCKET" \
    --execution-role "$AGENTCORE_ROLE" \
    --skip-install \
    $EXTRA_ARGS
  
  if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Supervisor agent deployed to AgentCore${NC}"

    # Get the AgentCore agent ARN for frontend config
    AGENT_ARN=$(cd backend && source venv/bin/activate 2>/dev/null && agentcore status --agent "${STACK_NAME}_supervisor" --verbose 2>/dev/null | grep -A1 '"agent_arn"' | grep 'arn:' | sed 's/.*"\(arn:[^"]*\)".*/\1/' || echo "")
    
    if [ -z "$AGENT_ARN" ]; then
      AGENT_ARN=$(grep 'agent_arn' backend/.bedrock_agentcore.yaml 2>/dev/null | sed 's/.*: *//' | tr -d '"' | tr -d "'" | head -1 || echo "")
    fi
    
    if [ -n "$AGENT_ARN" ]; then
      echo -e "${GREEN}✓ Supervisor ARN: $AGENT_ARN${NC}"
      echo "$AGENT_ARN" > /tmp/agentcore-endpoint.txt
      
      # Save ARN to backend/.env for start-local.sh --agentcore
      if grep -q "^AGENTCORE_ARN=" backend/.env 2>/dev/null; then
        sed -i.bak "s|^AGENTCORE_ARN=.*|AGENTCORE_ARN=$AGENT_ARN|" backend/.env
        rm -f backend/.env.bak
      else
        echo "AGENTCORE_ARN=$AGENT_ARN" >> backend/.env
      fi
    else
      echo -e "${YELLOW}⚠️  Could not retrieve agent ARN${NC}"
    fi
  else
    echo -e "${YELLOW}⚠️  AgentCore deployment failed${NC}"
    echo -e "${YELLOW}   You can deploy manually later with:${NC}"
    echo -e "${YELLOW}   ./scripts/deploy_to_agentcore.sh --data-bucket $DATA_BUCKET${NC}"
  fi
  echo ""

  # Step 5.6: Update Lambda API with Memory ID
  MEMORY_ID=$(cd backend && source venv/bin/activate 2>/dev/null && agentcore memory list --region "$REGION" 2>/dev/null | grep "${STACK_NAME}_supervisor_mem" | awk '{print $4}' || echo "")
  if [ -n "$MEMORY_ID" ]; then
    echo -e "${BLUE}🧠 Updating Lambda API with Memory ID: $MEMORY_ID${NC}"
    aws lambda update-function-configuration \
      --function-name "${STACK_NAME}-dev-api" \
      --environment "Variables={DATA_BUCKET=$DATA_BUCKET,CONFIG_BUCKET=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="ConfigBucketName") | .OutputValue'),MEMORY_ID=$MEMORY_ID}" \
      --region "$REGION" \
      --output text --no-cli-pager > /dev/null 2>&1
    echo -e "${GREEN}✓ Lambda API updated with Memory ID${NC}"
  else
    echo -e "${YELLOW}⚠️  Could not find supervisor memory ID${NC}"
  fi
else
  echo -e "${YELLOW}⏭️  Step 5.5: Skipping AgentCore agent deployment${NC}"
  echo ""
fi

# Step 6: Deploy frontend
if [ "$SKIP_FRONTEND" = false ]; then
  echo -e "${BLUE}🎨 Step 6: Deploying frontend...${NC}"
  
  # Check if we have an AgentCore endpoint/ARN
  if [ -f "/tmp/agentcore-endpoint.txt" ]; then
    AGENTCORE_ARN=$(cat /tmp/agentcore-endpoint.txt)
    echo -e "${BLUE}   Using AgentCore ARN: $AGENTCORE_ARN${NC}"
    
    # Update frontend .env with AgentCore config
    cat > frontend/.env << EOF
VITE_AGENTCORE_ARN=$AGENTCORE_ARN
VITE_REGION=$REGION
VITE_USER_POOL_ID=$USER_POOL_ID
VITE_USER_POOL_CLIENT_ID=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="UserPoolClientId") | .OutputValue')
VITE_IDENTITY_POOL_ID=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="IdentityPoolId") | .OutputValue')
VITE_API_GW_ENDPOINT=$API_ENDPOINT
EOF
    
    echo -e "${GREEN}✓ Frontend .env updated with AgentCore config${NC}"
  else
    echo -e "${YELLOW}⚠️  No AgentCore ARN found${NC}"
    echo -e "${YELLOW}   Frontend will use default API endpoint (localhost:8000)${NC}"
  fi
  
  # Try to build and deploy frontend
  if ./scripts/deploy_frontend.sh --bucket "$FRONTEND_BUCKET" --distribution "$DISTRIBUTION_ID" --config-bucket "$CONFIG_BUCKET" 2>/dev/null; then
    echo -e "${GREEN}✓ Frontend deployed${NC}"
  else
    echo -e "${YELLOW}⚠️  Frontend build failed (TypeScript errors)${NC}"
    echo -e "${YELLOW}   Deploying placeholder instead...${NC}"
    
    # Upload placeholder
    aws s3 cp frontend-placeholder/index.html "s3://$FRONTEND_BUCKET/index.html" \
      --region "$REGION" \
      --content-type "text/html" \
      --cache-control "no-cache"
    
    # Invalidate CloudFront cache
    aws cloudfront create-invalidation \
      --distribution-id "$DISTRIBUTION_ID" \
      --paths "/*" \
      --output text > /dev/null
    
    echo -e "${GREEN}✓ Placeholder deployed${NC}"
    echo -e "${YELLOW}   To deploy full app: fix TypeScript errors and run ./scripts/deploy_frontend.sh${NC}"
  fi
  echo ""
else
  echo -e "${YELLOW}⏭️  Step 6: Skipping frontend deployment${NC}"
  echo ""
fi

# Success summary
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Deployment Complete! ✓                        ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Application URL:${NC}"
echo -e "  ${GREEN}$APP_URL${NC}"
echo ""

# Show demo user credentials if created
if [ "$CREATE_DEMO_USER" = true ]; then
  echo -e "${BLUE}Demo User Credentials:${NC}"
  echo -e "  User 1: ${GREEN}$DEMO_USERNAME${NC} / ${GREEN}$DEMO_PASSWORD${NC}"
  echo -e "  User 2: ${GREEN}operator2@netops.demo${NC} / ${GREEN}$DEMO_PASSWORD${NC}"
  echo ""
fi

echo -e "${BLUE}Stack Outputs:${NC}"
echo "$OUTPUTS" | jq -r '.[] | "  \(.OutputKey): \(.OutputValue)"'
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo -e "  1. Access the application: ${GREEN}$APP_URL${NC}"
if [ "$CREATE_DEMO_USER" = false ]; then
  echo -e "  2. Create a Cognito user:"
  echo -e "     ${YELLOW}./deploy.sh --create-demo-user${NC}"
  echo -e "     Or manually via AWS Console"
else
  echo -e "  2. Login with demo user credentials above"
fi
echo -e "  3. Test authentication and agent invocation"
echo ""

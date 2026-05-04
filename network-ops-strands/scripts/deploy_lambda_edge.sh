#!/bin/bash

##############################################################################
# Deploy Lambda@Edge JWT Authorizer
#
# This script:
# 1. Packages the Lambda@Edge function with dependencies
# 2. Deploys the CloudFormation stack
# 3. Updates the function code
# 4. Creates a new version for CloudFront association
#
# Usage:
#   ./deploy_lambda_edge.sh --stack-name netops --region us-east-1
##############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
STACK_NAME="netops"
REGION="us-east-1"  # Lambda@Edge must be deployed in us-east-1
ENVIRONMENT="dev"

# Parse command line arguments
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
    --environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --stack-name NAME      CloudFormation stack name (default: netops)"
      echo "  --region REGION        AWS region - MUST be us-east-1 for Lambda@Edge (default: us-east-1)"
      echo "  --environment ENV      Environment (dev/staging/prod, default: dev)"
      echo "  --help                 Show this help message"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

# Validate region (Lambda@Edge must be in us-east-1)
if [ "$REGION" != "us-east-1" ]; then
  echo -e "${RED}❌ Error: Lambda@Edge functions must be deployed in us-east-1${NC}"
  echo -e "${YELLOW}   Current region: $REGION${NC}"
  exit 1
fi

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Lambda@Edge JWT Authorizer Deployment             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Configuration:${NC}"
echo -e "  Stack Name:    ${YELLOW}$STACK_NAME${NC}"
echo -e "  Region:        ${YELLOW}$REGION${NC}"
echo -e "  Environment:   ${YELLOW}$ENVIRONMENT${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LAMBDA_DIR="$PROJECT_ROOT/infrastructure/lambda-edge/jwt-authorizer"
BUILD_DIR="$PROJECT_ROOT/.build/lambda-edge"

# Step 1: Get Cognito configuration
echo -e "${BLUE}📋 Step 1: Getting Cognito configuration...${NC}"

COGNITO_STACK_NAME="${STACK_NAME}-cognito"
USER_POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name "$COGNITO_STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
  --output text 2>/dev/null || echo "")

APP_CLIENT_ID=$(aws cloudformation describe-stacks \
  --stack-name "$COGNITO_STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' \
  --output text 2>/dev/null || echo "")

if [ -z "$USER_POOL_ID" ] || [ -z "$APP_CLIENT_ID" ]; then
  echo -e "${RED}❌ Error: Could not get Cognito configuration${NC}"
  echo -e "${YELLOW}   Make sure the Cognito stack is deployed: $COGNITO_STACK_NAME${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Cognito configuration retrieved${NC}"
echo -e "  User Pool ID:  ${YELLOW}$USER_POOL_ID${NC}"
echo -e "  App Client ID: ${YELLOW}${APP_CLIENT_ID:0:20}...${NC}"
echo ""

# Step 2: Package Lambda function
echo -e "${BLUE}📦 Step 2: Packaging Lambda@Edge function...${NC}"

# Create build directory
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Copy function code
cp "$LAMBDA_DIR/index.js" "$BUILD_DIR/"
cp "$LAMBDA_DIR/package.json" "$BUILD_DIR/"

# Install dependencies
echo -e "${YELLOW}   Installing Node.js dependencies...${NC}"
cd "$BUILD_DIR"
npm install --production --silent

# Create deployment package
echo -e "${YELLOW}   Creating deployment package...${NC}"
zip -q -r function.zip index.js node_modules/

PACKAGE_SIZE=$(du -h function.zip | cut -f1)
echo -e "${GREEN}✓ Package created: ${PACKAGE_SIZE}${NC}"
echo ""

# Step 3: Deploy CloudFormation stack
echo -e "${BLUE}☁️  Step 3: Deploying CloudFormation stack...${NC}"

LAMBDA_EDGE_STACK_NAME="${STACK_NAME}-lambda-edge"
TEMPLATE_FILE="$PROJECT_ROOT/infrastructure/cloudformation/lambda-edge.yaml"

aws cloudformation deploy \
  --template-file "$TEMPLATE_FILE" \
  --stack-name "$LAMBDA_EDGE_STACK_NAME" \
  --region "$REGION" \
  --parameter-overrides \
    ProjectName="$STACK_NAME" \
    Environment="$ENVIRONMENT" \
    CognitoUserPoolId="$USER_POOL_ID" \
    CognitoAppClientId="$APP_CLIENT_ID" \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset

echo -e "${GREEN}✓ CloudFormation stack deployed${NC}"
echo ""

# Step 4: Update function code
echo -e "${BLUE}🔄 Step 4: Updating Lambda function code...${NC}"

FUNCTION_NAME="${STACK_NAME}-${ENVIRONMENT}-jwt-authorizer"

aws lambda update-function-code \
  --function-name "$FUNCTION_NAME" \
  --region "$REGION" \
  --zip-file "fileb://function.zip" \
  --output text > /dev/null

# Wait for function to be updated
echo -e "${YELLOW}   Waiting for function update to complete...${NC}"
aws lambda wait function-updated \
  --function-name "$FUNCTION_NAME" \
  --region "$REGION"

echo -e "${GREEN}✓ Function code updated${NC}"
echo ""

# Step 5: Publish new version
echo -e "${BLUE}📌 Step 5: Publishing new Lambda version...${NC}"

VERSION_OUTPUT=$(aws lambda publish-version \
  --function-name "$FUNCTION_NAME" \
  --region "$REGION" \
  --description "Deployed on $(date -u +"%Y-%m-%d %H:%M:%S UTC")")

VERSION_NUMBER=$(echo "$VERSION_OUTPUT" | jq -r '.Version')
VERSION_ARN=$(echo "$VERSION_OUTPUT" | jq -r '.FunctionArn')

echo -e "${GREEN}✓ Version published: ${VERSION_NUMBER}${NC}"
echo -e "  Version ARN: ${YELLOW}$VERSION_ARN${NC}"
echo ""

# Step 6: Get outputs
echo -e "${BLUE}📤 Step 6: Getting stack outputs...${NC}"

OUTPUTS=$(aws cloudformation describe-stacks \
  --stack-name "$LAMBDA_EDGE_STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs')

echo -e "${GREEN}✓ Stack outputs:${NC}"
echo "$OUTPUTS" | jq -r '.[] | "  \(.OutputKey): \(.OutputValue)"'
echo ""

# Cleanup
cd "$PROJECT_ROOT"
rm -rf "$BUILD_DIR"

# Summary
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Deployment Complete! ✓                        ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo ""
echo -e "1. ${YELLOW}Update CloudFront distribution${NC} to use this Lambda@Edge function:"
echo -e "   ${GREEN}aws cloudformation update-stack \\${NC}"
echo -e "   ${GREEN}  --stack-name ${STACK_NAME}-cloudfront \\${NC}"
echo -e "   ${GREEN}  --use-previous-template \\${NC}"
echo -e "   ${GREEN}  --parameters ParameterKey=JWTAuthorizerVersionArn,ParameterValue=$VERSION_ARN${NC}"
echo ""
echo -e "2. ${YELLOW}Or redeploy CloudFront${NC} with the JWT authorizer:"
echo -e "   ${GREEN}./scripts/deploy_infrastructure.sh --with-jwt-auth${NC}"
echo ""
echo -e "3. ${YELLOW}Test the authorization${NC}:"
echo -e "   - Try accessing protected pages without login → should redirect"
echo -e "   - Login and access protected pages → should work"
echo -e "   - Check CloudWatch Logs for Lambda@Edge execution logs"
echo ""
echo -e "${BLUE}CloudWatch Logs:${NC}"
echo -e "  Lambda@Edge logs are in CloudWatch Logs in the region where the function executed"
echo -e "  Log group: ${YELLOW}/aws/lambda/us-east-1.${FUNCTION_NAME}${NC}"
echo ""

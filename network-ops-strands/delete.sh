#!/bin/bash

##############################################################################
# Network Operations Platform - Unified Deletion Script
#
# This script deletes the entire platform stack including:
# - CloudFront distribution
# - S3 buckets (after emptying)
# - Lambda@Edge functions
# - Cognito resources
# - IAM roles
# - AgentCore agents
#
# Usage:
#   ./delete.sh                    # Delete with confirmation
#   ./delete.sh --force            # Delete without confirmation
#   ./delete.sh --stack-name prod  # Delete prod stack
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
FORCE=false

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
    --force)
      FORCE=true
      shift
      ;;
    --help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --stack-name NAME    Stack name (default: netops)"
      echo "  --region REGION      AWS region (default: us-east-1)"
      echo "  --force              Skip confirmation prompts"
      echo "  --help               Show this help"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║     Network Operations Platform - Stack Deletion          ║${NC}"
echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}⚠️  WARNING: This will delete ALL resources in stack: ${STACK_NAME}${NC}"
echo ""

# Confirmation
if [ "$FORCE" = false ]; then
  read -p "Are you sure you want to delete the stack? (yes/no): " confirm
  if [ "$confirm" != "yes" ]; then
    echo -e "${BLUE}Deletion cancelled${NC}"
    exit 0
  fi
  
  read -p "Type the stack name to confirm: " confirm_name
  if [ "$confirm_name" != "$STACK_NAME" ]; then
    echo -e "${RED}Stack name mismatch. Deletion cancelled${NC}"
    exit 1
  fi
fi

# Get stack outputs before deletion
echo -e "${BLUE}📤 Getting stack outputs...${NC}"
OUTPUTS=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs' \
  --output json 2>/dev/null || echo "[]")

FRONTEND_BUCKET=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="FrontendBucketName") | .OutputValue' 2>/dev/null || echo "")
DATA_BUCKET=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="DataBucketName") | .OutputValue' 2>/dev/null || echo "")
CONFIG_BUCKET=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="ConfigBucketName") | .OutputValue' 2>/dev/null || echo "")
LOGGING_BUCKET=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="LoggingBucketName") | .OutputValue' 2>/dev/null || echo "")

# Step 1: Empty S3 buckets (including CloudFront logging bucket)
echo -e "${BLUE}🗑️  Step 1: Emptying S3 buckets...${NC}"
for bucket in "$FRONTEND_BUCKET" "$DATA_BUCKET" "$CONFIG_BUCKET" "$LOGGING_BUCKET"; do
  if [ -n "$bucket" ] && [ "$bucket" != "null" ]; then
    echo -e "${YELLOW}   Emptying bucket: $bucket${NC}"
    aws s3 rm "s3://$bucket" --recursive --region "$REGION" 2>/dev/null || true
    echo -e "${GREEN}   ✓ Bucket emptied: $bucket${NC}"
  fi
done

# Also try to empty the logging bucket by name pattern (in case output is not available)
LOGGING_BUCKET_PATTERN="${STACK_NAME}-*-cloudfront-logs-*"
echo -e "${YELLOW}   Checking for CloudFront logging buckets matching pattern: $LOGGING_BUCKET_PATTERN${NC}"
aws s3api list-buckets --query "Buckets[?starts_with(Name, '${STACK_NAME}-')].Name" --output text 2>/dev/null | tr '\t' '\n' | grep -i "cloudfront-logs" | while read -r bucket; do
  if [ -n "$bucket" ]; then
    echo -e "${YELLOW}   Emptying CloudFront logging bucket: $bucket${NC}"
    aws s3 rm "s3://$bucket" --recursive --region "$REGION" 2>/dev/null || true
    echo -e "${GREEN}   ✓ Bucket emptied: $bucket${NC}"
  fi
done
echo ""

# Step 2: Delete AgentCore agents
echo -e "${BLUE}🤖 Step 2: Deleting AgentCore agents...${NC}"
./scripts/cleanup_agentcore.sh 2>/dev/null || echo -e "${YELLOW}   No AgentCore agents to delete${NC}"
echo ""

# Step 3: Delete SAM stack
echo -e "${BLUE}☁️  Step 3: Deleting SAM stack...${NC}"
sam delete \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --no-prompts
echo -e "${GREEN}✓ Stack deleted${NC}"
echo ""

# Success
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Deletion Complete! ✓                          ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}All resources have been deleted.${NC}"
echo ""

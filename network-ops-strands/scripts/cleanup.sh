#!/bin/bash
# Cleanup script - Remove all AWS resources for Network Operations Platform

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="dev"
PROJECT_NAME="netops"
REGION="us-east-1"
FORCE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment|-e)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --project|-p)
            PROJECT_NAME="$2"
            shift 2
            ;;
        --region|-r)
            REGION="$2"
            shift 2
            ;;
        --force|-f)
            FORCE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Remove all AWS resources for Network Operations Platform"
            echo ""
            echo "Options:"
            echo "  --environment, -e    Environment (dev|staging|prod) [default: dev]"
            echo "  --project, -p        Project name [default: netops]"
            echo "  --region, -r         AWS region [default: us-east-1]"
            echo "  --force, -f          Skip confirmation prompts"
            echo "  --help, -h           Show this help message"
            echo ""
            echo "WARNING: This will permanently delete all resources!"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

STACK_NAME="${PROJECT_NAME}-${ENVIRONMENT}"

echo -e "${RED}========================================${NC}"
echo -e "${RED}⚠️  CLEANUP WARNING ⚠️${NC}"
echo -e "${RED}========================================${NC}"
echo ""
echo "This will PERMANENTLY DELETE all resources for:"
echo ""
echo "  Environment:  $ENVIRONMENT"
echo "  Project:      $PROJECT_NAME"
echo "  Region:       $REGION"
echo "  Stack Name:   $STACK_NAME"
echo ""
echo -e "${RED}This action CANNOT be undone!${NC}"
echo ""

# Confirm cleanup
if [ "$FORCE" = false ]; then
    read -p "Type 'DELETE' to confirm: " CONFIRM
    if [ "$CONFIRM" != "DELETE" ]; then
        echo "Cleanup cancelled"
        exit 0
    fi
    
    echo ""
    read -p "Are you absolutely sure? (yes/no): " FINAL_CONFIRM
    if [ "$FINAL_CONFIRM" != "yes" ]; then
        echo "Cleanup cancelled"
        exit 0
    fi
fi

echo ""
echo -e "${YELLOW}Starting cleanup...${NC}"

# Function to empty S3 bucket
empty_bucket() {
    local bucket=$1
    echo -e "${YELLOW}Emptying S3 bucket: $bucket${NC}"
    
    if aws s3 ls "s3://$bucket" --region "$REGION" > /dev/null 2>&1; then
        # Delete all objects
        aws s3 rm "s3://$bucket" --recursive --region "$REGION" || true
        
        # Delete all versions (if versioning enabled)
        aws s3api list-object-versions \
            --bucket "$bucket" \
            --region "$REGION" \
            --output json \
            --query 'Versions[].{Key:Key,VersionId:VersionId}' 2>/dev/null | \
        jq -r '.[] | "--key \"\(.Key)\" --version-id \"\(.VersionId)\""' | \
        xargs -I {} aws s3api delete-object --bucket "$bucket" --region "$REGION" {} || true
        
        # Delete all delete markers
        aws s3api list-object-versions \
            --bucket "$bucket" \
            --region "$REGION" \
            --output json \
            --query 'DeleteMarkers[].{Key:Key,VersionId:VersionId}' 2>/dev/null | \
        jq -r '.[] | "--key \"\(.Key)\" --version-id \"\(.VersionId)\""' | \
        xargs -I {} aws s3api delete-object --bucket "$bucket" --region "$REGION" {} || true
        
        echo -e "${GREEN}✓ Bucket emptied: $bucket${NC}"
    else
        echo -e "${YELLOW}⚠ Bucket not found: $bucket${NC}"
    fi
}

# Function to delete CloudFormation stack
delete_stack() {
    local stack=$1
    echo -e "${YELLOW}Deleting CloudFormation stack: $stack${NC}"
    
    if aws cloudformation describe-stacks --stack-name "$stack" --region "$REGION" > /dev/null 2>&1; then
        aws cloudformation delete-stack --stack-name "$stack" --region "$REGION"
        
        echo "Waiting for stack deletion..."
        aws cloudformation wait stack-delete-complete --stack-name "$stack" --region "$REGION" 2>/dev/null || true
        
        echo -e "${GREEN}✓ Stack deleted: $stack${NC}"
    else
        echo -e "${YELLOW}⚠ Stack not found: $stack${NC}"
    fi
}

# Function to delete AgentCore agents
delete_agents() {
    echo -e "${YELLOW}Deleting AgentCore agents...${NC}"
    
    if command -v agentcore &> /dev/null; then
        # List and delete all agents for this project
        AGENTS=$(agentcore agent list --region "$REGION" 2>/dev/null | grep "${PROJECT_NAME}-${ENVIRONMENT}" || true)
        
        if [ -n "$AGENTS" ]; then
            echo "$AGENTS" | while read -r agent; do
                AGENT_NAME=$(echo "$agent" | awk '{print $1}')
                echo "  Deleting agent: $AGENT_NAME"
                agentcore agent delete --name "$AGENT_NAME" --region "$REGION" --force || true
            done
            echo -e "${GREEN}✓ Agents deleted${NC}"
        else
            echo -e "${YELLOW}⚠ No agents found${NC}"
        fi
        
        # Delete AgentCore Memory
        MEMORY_NAME="${PROJECT_NAME}-${ENVIRONMENT}-sessions"
        if agentcore memory list --region "$REGION" 2>/dev/null | grep -q "$MEMORY_NAME"; then
            echo "  Deleting memory: $MEMORY_NAME"
            agentcore memory delete --name "$MEMORY_NAME" --region "$REGION" --force || true
            echo -e "${GREEN}✓ Memory deleted${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ AgentCore CLI not found, skipping agent cleanup${NC}"
    fi
}

# Get bucket names from stacks (if they exist)
echo ""
echo -e "${YELLOW}Getting resource information...${NC}"

FRONTEND_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}-s3" \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
    --output text \
    --region "$REGION" 2>/dev/null || echo "")

DATA_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}-s3" \
    --query "Stacks[0].Outputs[?OutputKey=='DataBucketName'].OutputValue" \
    --output text \
    --region "$REGION" 2>/dev/null || echo "")

CONFIG_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}-s3" \
    --query "Stacks[0].Outputs[?OutputKey=='ConfigBucketName'].OutputValue" \
    --output text \
    --region "$REGION" 2>/dev/null || echo "")

LOGGING_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}-cloudfront" \
    --query "Stacks[0].Outputs[?OutputKey=='LoggingBucketName'].OutputValue" \
    --output text \
    --region "$REGION" 2>/dev/null || echo "")

# Step 1: Delete AgentCore agents
echo ""
echo -e "${YELLOW}Step 1/5: Deleting AgentCore agents${NC}"
delete_agents

# Step 2: Empty S3 buckets
echo ""
echo -e "${YELLOW}Step 2/5: Emptying S3 buckets${NC}"
[ -n "$FRONTEND_BUCKET" ] && empty_bucket "$FRONTEND_BUCKET"
[ -n "$DATA_BUCKET" ] && empty_bucket "$DATA_BUCKET"
[ -n "$CONFIG_BUCKET" ] && empty_bucket "$CONFIG_BUCKET"
[ -n "$LOGGING_BUCKET" ] && empty_bucket "$LOGGING_BUCKET"

# Step 3: Delete CloudFront stack (must be deleted before S3)
echo ""
echo -e "${YELLOW}Step 3/5: Deleting CloudFront stack${NC}"
delete_stack "${STACK_NAME}-cloudfront"

# Step 4: Delete Cognito stack
echo ""
echo -e "${YELLOW}Step 4/5: Deleting Cognito stack${NC}"
delete_stack "${STACK_NAME}-cognito"

# Step 5: Delete remaining stacks
echo ""
echo -e "${YELLOW}Step 5/5: Deleting remaining stacks${NC}"
delete_stack "${STACK_NAME}-iam"
delete_stack "${STACK_NAME}-s3"

# Delete main stack if it exists
if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" > /dev/null 2>&1; then
    delete_stack "$STACK_NAME"
fi

# Clean up local files
echo ""
echo -e "${YELLOW}Cleaning up local files...${NC}"
[ -f "deployment-outputs.json" ] && rm -f deployment-outputs.json && echo "  ✓ Removed deployment-outputs.json"
[ -f "agentcore-deployment.json" ] && rm -f agentcore-deployment.json && echo "  ✓ Removed agentcore-deployment.json"
[ -f "backend/deployment.zip" ] && rm -f backend/deployment.zip && echo "  ✓ Removed backend/deployment.zip"
[ -d "backend/dist" ] && rm -rf backend/dist && echo "  ✓ Removed backend/dist"

# Print summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Cleanup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "All resources for ${STACK_NAME} have been removed."
echo ""
echo -e "${YELLOW}Note:${NC} CloudWatch logs may still exist. To delete them:"
echo "  aws logs delete-log-group --log-group-name /aws/agentcore/${PROJECT_NAME}-${ENVIRONMENT} --region $REGION"
echo ""

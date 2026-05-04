#!/bin/bash
set -e

##############################################################################
# Setup CodePipeline for Network Operations Platform
#
# Creates a CodePipeline + CodeBuild that pulls from GitHub and runs
# the full deployment. Manual trigger only (no auto-deploy on push).
#
# Usage:
#   export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
#   ./setup-pipeline.sh --repo-url https://github.com/org/repo
##############################################################################

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Defaults
REPO_URL=""
BRANCH="main"
REGION="us-east-1"
PROJECT="netops"
STACK_NAME="${PROJECT}-pipeline"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --repo-url)   REPO_URL="$2"; shift 2 ;;
    --branch)     BRANCH="$2"; shift 2 ;;
    --region)     REGION="$2"; shift 2 ;;
    --project)    PROJECT="$2"; STACK_NAME="${PROJECT}-pipeline"; shift 2 ;;
    --token)      GITHUB_TOKEN="$2"; shift 2 ;;
    --help)
      echo "Usage: $0 --repo-url <github-url> [--branch main] [--region us-east-1] [--token ghp_xxx]"
      echo ""
      echo "Options:"
      echo "  --repo-url   GitHub repository URL (required)"
      echo "  --branch     Branch to deploy from (default: main)"
      echo "  --region     AWS region (default: us-east-1)"
      echo "  --project    Project name (default: netops)"
      echo "  --token      GitHub personal access token (or set GITHUB_TOKEN env var)"
      exit 0
      ;;
    *) echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
  esac
done

# Validate
if [ -z "$REPO_URL" ]; then
  echo -e "${RED}Error: --repo-url is required${NC}"
  echo "Usage: $0 --repo-url https://github.com/org/repo"
  exit 1
fi

if [ -z "$GITHUB_TOKEN" ]; then
  echo -e "${RED}Error: GitHub token required${NC}"
  echo "Set GITHUB_TOKEN env var or use --token flag"
  echo "Create one at: https://github.com/settings/tokens"
  echo "Required scopes: repo, admin:repo_hook"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo -e "${BLUE}"
echo "============================================"
echo "  Network Operations Pipeline Setup"
echo "============================================"
echo "  Repo:    $REPO_URL"
echo "  Branch:  $BRANCH"
echo "  Region:  $REGION"
echo "  Project: $PROJECT"
echo "  Stack:   $STACK_NAME"
echo "============================================"
echo -e "${NC}"

# Step 1: Deploy pipeline CloudFormation stack
echo -e "${BLUE}Step 1: Creating pipeline infrastructure...${NC}"
aws cloudformation deploy \
  --template-file "${SCRIPT_DIR}/pipeline-stack.yaml" \
  --stack-name "$STACK_NAME" \
  --parameter-overrides \
    ProjectName="$PROJECT" \
    GitHubRepo="$REPO_URL" \
    GitHubBranch="$BRANCH" \
    GitHubToken="$GITHUB_TOKEN" \
    DeployRegion="$REGION" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION" \
  --no-fail-on-empty-changeset

echo -e "${GREEN}✓ Pipeline infrastructure created${NC}"

# Step 2: Get pipeline info
PIPELINE_NAME=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='PipelineName'].OutputValue" \
  --output text)

PIPELINE_URL=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='PipelineUrl'].OutputValue" \
  --output text)

echo ""
echo -e "${BLUE}Step 2: Triggering first deployment...${NC}"

# Step 3: Trigger the pipeline
aws codepipeline start-pipeline-execution \
  --name "$PIPELINE_NAME" \
  --region "$REGION" > /dev/null

echo -e "${GREEN}✓ Pipeline triggered${NC}"

# Summary
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Pipeline Setup Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "  Pipeline:  $PIPELINE_NAME"
echo "  Console:   $PIPELINE_URL"
echo ""
echo "  The deployment is now running in AWS."
echo "  Monitor progress at the URL above."
echo ""
echo "  Estimated time: 15-20 minutes"
echo ""
echo "  To re-deploy later:"
echo "    aws codepipeline start-pipeline-execution --name $PIPELINE_NAME --region $REGION"
echo ""
echo "  To tear down the pipeline:"
echo "    aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION"
echo ""
echo -e "${GREEN}============================================${NC}"

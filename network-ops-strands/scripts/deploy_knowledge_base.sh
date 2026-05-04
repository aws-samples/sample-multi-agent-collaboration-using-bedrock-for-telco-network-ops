#!/bin/bash
set -e

# Deploy Bedrock Knowledge Base with S3 Vectors for Network Operations Platform
# Uses CloudFormation for KB + data source, then syncs docs and triggers ingestion

REGION="${AWS_REGION:-us-east-1}"
PROJECT="netops"
ENV="dev"
STACK_NAME="${PROJECT}-${ENV}-knowledge-base"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo "  Bedrock Knowledge Base Deployment"
echo "============================================"
echo "  Region: $REGION"
echo "  Stack:  $STACK_NAME"
echo ""

# Get data bucket from the main infra stack
DATA_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "${PROJECT}-${ENV}" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='DataBucketName'].OutputValue" \
  --output text 2>/dev/null || echo "")

if [ -z "$DATA_BUCKET" ] || [ "$DATA_BUCKET" = "None" ]; then
  echo "❌ Could not find data bucket from stack ${PROJECT}-${ENV}"
  echo "   Make sure infra is deployed first."
  exit 1
fi

DATA_BUCKET_ARN="arn:aws:s3:::${DATA_BUCKET}"
echo "  Data Bucket: $DATA_BUCKET"
echo ""

# Step 1: Generate knowledge base content
echo "📚 Step 1: Generating knowledge base content..."
cd "$PROJECT_ROOT"
python3 scripts/generate_data.py --output data --profile datacenter
echo "   ✓ Content generated"

# Step 2: Upload to S3
echo ""
echo "☁️  Step 2: Uploading knowledge base documents to S3..."
aws s3 sync data/knowledge-base/ "s3://${DATA_BUCKET}/knowledge-base/" \
  --delete --region "$REGION"
echo "   ✓ Documents uploaded to s3://${DATA_BUCKET}/knowledge-base/"

# Step 3: Deploy CloudFormation stack
echo ""
echo "🏗️  Step 3: Deploying Knowledge Base CloudFormation stack..."
aws cloudformation deploy \
  --template-file infrastructure/cloudformation/knowledge-base.yaml \
  --stack-name "$STACK_NAME" \
  --parameter-overrides \
    Environment="$ENV" \
    ProjectName="$PROJECT" \
    DataBucketName="$DATA_BUCKET" \
    DataBucketArn="$DATA_BUCKET_ARN" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION" \
  --no-fail-on-empty-changeset

# Get outputs
KB_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='KnowledgeBaseId'].OutputValue" \
  --output text)

DS_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='DataSourceId'].OutputValue" \
  --output text)

echo "   ✓ Stack deployed"
echo "   KB ID: $KB_ID"
echo "   DS ID: $DS_ID"

# Step 4: Start ingestion job
echo ""
echo "🔄 Step 4: Starting ingestion job..."
INGESTION_ID=$(aws bedrock-agent start-ingestion-job \
  --knowledge-base-id "$KB_ID" \
  --data-source-id "$DS_ID" \
  --region "$REGION" \
  --query "ingestionJob.ingestionJobId" --output text 2>&1)
echo "   ✓ Ingestion job started: $INGESTION_ID"
echo "   ⏳ Ingestion runs in background (1-3 minutes)"

# Step 5: Output
echo ""
echo "============================================"
echo "  ✅ Knowledge Base Deployment Complete"
echo "============================================"
echo ""
echo "  Knowledge Base ID: $KB_ID"
echo "  Data Source ID:    $DS_ID"
echo "  S3 Location:       s3://${DATA_BUCKET}/knowledge-base/"
echo ""
echo "  Add to your agent deploy:"
echo "    export KNOWLEDGE_BASE_ID=$KB_ID"
echo ""

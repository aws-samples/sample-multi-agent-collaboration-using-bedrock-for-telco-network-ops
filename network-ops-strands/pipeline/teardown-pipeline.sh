#!/bin/bash
set -e

# Tear down the CodePipeline infrastructure
PROJECT="${1:-netops}"
REGION="${2:-us-east-1}"
STACK_NAME="${PROJECT}-pipeline"

echo "Deleting pipeline stack: $STACK_NAME"

# Empty artifact bucket first
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucket'].OutputValue" \
  --output text 2>/dev/null || echo "")

if [ -n "$BUCKET" ] && [ "$BUCKET" != "None" ]; then
  echo "Emptying artifact bucket: $BUCKET"
  aws s3 rm "s3://$BUCKET" --recursive --region "$REGION" 2>/dev/null || true
fi

aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"
echo "Waiting for stack deletion..."
aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$REGION"
echo "Done. Pipeline infrastructure deleted."

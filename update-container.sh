#!/bin/bash
set -e

# Get parameters
STACK_NAME=${1:-netops}
REGION=${2:-us-east-1}
PROFILE=${3:-default}

echo "Updating container for stack $STACK_NAME in region $REGION using profile $PROFILE"

# Set up ECR repository URI
ECR_REPO="${STACK_NAME}-network-operations-agent-streamlit"
ECR_URI="$(aws ecr describe-repositories --repository-names $ECR_REPO --query 'repositories[0].repositoryUri' --output text --region $REGION --profile $PROFILE)"

if [ -z "$ECR_URI" ]; then
  echo "Error: Could not find ECR repository $ECR_REPO"
  echo "Make sure the repository exists and you have the correct permissions"
  exit 1
fi

echo "Using ECR repository: $ECR_URI"

# Log in to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $REGION --profile $PROFILE | docker login --username AWS --password-stdin $(echo $ECR_URI | cut -d'/' -f1)

# Build the Docker image
echo "Building Docker image with platform linux/amd64..."
docker build --platform linux/amd64 -t $ECR_URI:latest .

# Push the Docker image
echo "Pushing Docker image to ECR..."
docker push $ECR_URI:latest

# Update the ECS service to force a new deployment
echo "Updating ECS service to use the new image..."
aws ecs update-service --cluster ${STACK_NAME}-cluster --service ${STACK_NAME}-service --force-new-deployment --region $REGION --profile $PROFILE

echo "Container update initiated!"
echo "You can monitor the deployment status with:"
echo "aws ecs describe-services --cluster ${STACK_NAME}-cluster --services ${STACK_NAME}-service --region $REGION --profile $PROFILE"
echo ""
echo "To check the logs of the new container once it's running:"
echo "aws logs get-log-events --log-group-name /ecs/${STACK_NAME} --log-stream-name \$(aws logs describe-log-streams --log-group-name /ecs/${STACK_NAME} --order-by LastEventTime --descending --limit 1 --query 'logStreams[0].logStreamName' --output text --region $REGION --profile $PROFILE) --region $REGION --profile $PROFILE"

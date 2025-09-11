#!/bin/bash
set -e

# Get parameters
STACK_NAME=${1:-netops}
REGION=${2:-us-east-1}
PROFILE=${3:-default}

echo "Deploying $STACK_NAME to $REGION using profile $PROFILE"

# Create lambda layer directory
echo "Creating lambda layer..."
mkdir -p lambda_layer/python

# Install minimal dependencies to reduce layer size
echo "Installing minimal dependencies for Lambda layer..."
python3 -m pip install pandas --no-deps -t lambda_layer/python --only-binary=:all: --platform manylinux2014_x86_64 --python-version 3.9 --implementation cp
python3 -m pip install numpy --no-deps -t lambda_layer/python --only-binary=:all: --platform manylinux2014_x86_64 --python-version 3.9 --implementation cp
python3 -m pip install pytz -t lambda_layer/python --only-binary=:all: --platform manylinux2014_x86_64 --python-version 3.9 --implementation cp
python3 -m pip install python-dateutil -t lambda_layer/python --only-binary=:all: --platform manylinux2014_x86_64 --python-version 3.9 --implementation cp
python3 -m pip install six -t lambda_layer/python --only-binary=:all: --platform manylinux2014_x86_64 --python-version 3.9 --implementation cp

# Clean up unnecessary files to reduce size
echo "Cleaning up unnecessary files to reduce layer size..."
find lambda_layer/python -name "*.dist-info" -type d -exec rm -rf {} \; 2>/dev/null || true
find lambda_layer/python -name "*.egg-info" -type d -exec rm -rf {} \; 2>/dev/null || true
find lambda_layer/python -name "__pycache__" -type d -exec rm -rf {} \; 2>/dev/null || true
find lambda_layer/python -name "*.pyc" -type f -delete 2>/dev/null || true
find lambda_layer/python -name "*.pyo" -type f -delete 2>/dev/null || true
find lambda_layer/python -name "*.so" -type f -exec strip {} \; 2>/dev/null || true
find lambda_layer/python -name "tests" -type d -exec rm -rf {} \; 2>/dev/null || true

# Build and push Docker image
echo "Building and pushing Docker image..."
ECR_REPO="${STACK_NAME}-network-operations-agent-streamlit"
ECR_URI="$(aws ecr describe-repositories --repository-names "$ECR_REPO" --query 'repositories[0].repositoryUri' --output text --region "$REGION" --profile "$PROFILE" 2>/dev/null || echo '')"

if [ -z "$ECR_URI" ]; then
  echo "Creating ECR repository..."
  ECR_URI=$(aws ecr create-repository --repository-name "$ECR_REPO" --query 'repository.repositoryUri' --output text --region "$REGION" --profile "$PROFILE")
fi

echo "Logging in to ECR..."
aws ecr get-login-password --region "$REGION" --profile "$PROFILE" | docker login --username AWS --password-stdin "$(echo "$ECR_URI" | cut -d'/' -f1)"

echo "Building Docker image with explicit platform..."
docker build --platform linux/amd64 -t "$ECR_URI:latest" .

echo "Pushing Docker image to ECR..."
docker push "$ECR_URI:latest"

# Deploy SAM template
echo "Cleaning up build artifacts..."
# First attempt with rm -rf
rm -rf .aws-sam/build .aws-sam 2>/dev/null || true
# If that fails, try with find to remove files first, then directories
if [ -d ".aws-sam" ]; then
  echo "Using alternative cleanup method..."
  find .aws-sam -type f -delete
  find .aws-sam -type d -empty -delete
  # Try rm -rf again after removing files
  rm -rf .aws-sam 2>/dev/null || true
  # If it still exists, just continue
  if [ -d ".aws-sam" ]; then
    echo "Warning: Could not completely remove .aws-sam directory, but continuing anyway."
  fi
fi

echo "Deploying SAM template..."
sam build --template template.yaml
sam deploy --stack-name "$STACK_NAME" \
           --region "$REGION" \
           --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
           --resolve-s3 \
           --no-fail-on-empty-changeset \
           --parameter-overrides ContainerImageUri="$ECR_URI:latest" \
           --template-file .aws-sam/build/template.yaml

# Get CloudFront URL
CF_URL=$(aws cloudformation describe-stacks \
           --stack-name $STACK_NAME \
           --query "Stacks[0].Outputs[?OutputKey=='CloudFrontURL'].OutputValue" \
           --output text \
           --region $REGION \
           --profile $PROFILE)

# Get Cognito User Pool ID
USER_POOL_ID=$(aws cloudformation describe-stacks \
           --stack-name $STACK_NAME \
           --query "Stacks[0].Outputs[?OutputKey=='CognitoUserPoolId'].OutputValue" \
           --output text \
           --region $REGION \
           --profile $PROFILE)

# Get Cognito User Pool Name
USER_POOL_NAME=$(aws cloudformation describe-stacks \
           --stack-name $STACK_NAME \
           --query "Stacks[0].Outputs[?OutputKey=='CognitoUserPoolName'].OutputValue" \
           --output text \
           --region $REGION \
           --profile $PROFILE)

# Get Supervisor Agent ID
SUPERVISOR_AGENT_ID=$(aws cloudformation describe-stacks \
           --stack-name $STACK_NAME \
           --query "Stacks[0].Outputs[?OutputKey=='SupervisorAgentId'].OutputValue" \
           --output text \
           --region $REGION \
           --profile $PROFILE)

# Get Supervisor Agent Alias ID
SUPERVISOR_ALIAS_ID=$(aws cloudformation describe-stacks \
           --stack-name $STACK_NAME \
           --query "Stacks[0].Outputs[?OutputKey=='SupervisorAliasId'].OutputValue" \
           --output text \
           --region $REGION \
           --profile $PROFILE)

# Create a test user in Cognito
if [ ! -z "$USER_POOL_ID" ]; then
  echo "Creating test user in Cognito User Pool ($USER_POOL_NAME)..."
  aws cognito-idp admin-create-user \
    --user-pool-id "$USER_POOL_ID" \
    --username netopsuser@example.com \
    --user-attributes Name=email,Value=netopsuser@example.com Name=email_verified,Value=true Name=name,Value="Network Ops User" \
    --temporary-password "Demouser1!" \
    --region "$REGION" \
    --profile "$PROFILE" \
    --output text \
    --no-cli-pager > /dev/null 2>&1

  # Set the password permanently (skip the forced password change)
  echo "Setting permanent password for test user..."
  aws cognito-idp admin-set-user-password \
    --user-pool-id "$USER_POOL_ID" \
    --username netopsuser@example.com \
    --password "Demouser2!" \
    --permanent \
    --region "$REGION" \
    --profile "$PROFILE" \
    --output text \
    --no-cli-pager > /dev/null 2>&1
    
  echo "Test user created successfully:"
  echo "  Username: netopsuser@example.com"
  echo "  Password: Demouser2!"
else
  echo "Warning: Could not find Cognito User Pool ID. Test user was not created."
fi

echo "Deployment complete!"
echo "Streamlit application will be available at: $CF_URL"
echo "Note: It may take a few minutes for the CloudFront distribution to deploy."
echo ""
echo "Supervisor Agent ID: $SUPERVISOR_AGENT_ID"
echo "Supervisor Agent Alias ID: $SUPERVISOR_ALIAS_ID"
echo ""

# Get ALB URL for direct testing
ALB_URL=$(aws cloudformation describe-stacks \
           --stack-name $STACK_NAME \
           --query "Stacks[0].Outputs[?OutputKey=='ALBEndpoint'].OutputValue" \
           --output text \
           --region $REGION \
           --profile $PROFILE)

echo "For troubleshooting, you can also access the ALB directly at: $ALB_URL"
echo "Check CloudWatch logs for any issues: /ecs/${STACK_NAME}"

# Add instructions for monitoring deployment
echo ""
echo "To monitor the deployment:"
echo "1. Check if the ECS service is running:"
echo "   aws ecs describe-services --cluster ${STACK_NAME}-cluster --services ${STACK_NAME}-service --region $REGION --profile $PROFILE"
echo ""
echo "2. Check the target group health:"
echo "   aws elbv2 describe-target-health --target-group-arn \$(aws elbv2 describe-target-groups --names ${STACK_NAME}-tg --query 'TargetGroups[0].TargetGroupArn' --output text --region $REGION --profile $PROFILE) --region $REGION --profile $PROFILE"
echo ""
echo "3. View CloudWatch logs:"
echo "   aws logs get-log-events --log-group-name /ecs/${STACK_NAME} --log-stream-name \$(aws logs describe-log-streams --log-group-name /ecs/${STACK_NAME} --order-by LastEventTime --descending --limit 1 --query 'logStreams[0].logStreamName' --output text --region $REGION --profile $PROFILE) --region $REGION --profile $PROFILE"

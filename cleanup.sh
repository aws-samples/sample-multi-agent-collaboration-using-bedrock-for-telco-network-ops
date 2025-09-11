#!/bin/bash

# Get stack name from command line argument
STACK_NAME=${1:-netops}
REGION=${2:-us-east-1}
PROFILE=${3:-default}

echo "Starting cleanup for stack: $STACK_NAME in region: $REGION"

# Function to handle errors gracefully
handle_error() {
    echo "Warning: $1"
    return 0
}

# Check if stack exists
if ! aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --profile $PROFILE &>/dev/null; then
    echo "Stack $STACK_NAME does not exist in region $REGION. Nothing to clean up."
    exit 0
fi

# Get CloudFront distribution ID
echo "Finding CloudFront distribution associated with the stack..."
CF_DIST_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDistributionId'].OutputValue" --output text --region "$REGION" --profile "$PROFILE")

if [ -n "$CF_DIST_ID" ]; then
    echo "Found CloudFront distribution: $CF_DIST_ID"
    
    # Check for pending CloudFront invalidations
    echo "Checking for pending CloudFront invalidations..."
    INVALIDATIONS=$(aws cloudfront list-invalidations --distribution-id $CF_DIST_ID --query 'InvalidationList.Items[?Status==`InProgress`].Id' --output text --region $REGION --profile $PROFILE)
    
    if [ -n "$INVALIDATIONS" ]; then
        for INV_ID in $INVALIDATIONS; do
            echo "Waiting for invalidation to complete: $INV_ID"
            aws cloudfront wait invalidation-completed --distribution-id $CF_DIST_ID --id $INV_ID --region $REGION --profile $PROFILE
        done
    else
        echo "No pending CloudFront invalidations found"
    fi
    
    # Check for Lambda@Edge function
    LAMBDA_FUNCTION="${STACK_NAME}-cf-auth"
    LAMBDA_EXISTS=$(aws lambda get-function --function-name $LAMBDA_FUNCTION --query 'Configuration.FunctionName' --output text --region $REGION --profile $PROFILE 2>/dev/null || echo "")
    
    if [ -n "$LAMBDA_EXISTS" ]; then
        echo "Found Lambda@Edge function: $LAMBDA_FUNCTION"
        echo "Disassociating Lambda@Edge function from CloudFront..."
        
        # Get the current distribution configuration
        CF_CONFIG=$(aws cloudfront get-distribution-config --id "$CF_DIST_ID" --region "$REGION" --profile "$PROFILE")
        ETAG=$(echo "$CF_CONFIG" | jq -r '.ETag')
        
        # Remove Lambda associations
        CF_CONFIG_JSON=$(echo "$CF_CONFIG" | jq '.DistributionConfig')
        CF_CONFIG_NO_LAMBDA=$(echo "$CF_CONFIG_JSON" | jq '.DefaultCacheBehavior.LambdaFunctionAssociations = {"Quantity": 0, "Items": []}')
        
        # Save the updated config to a file
        echo "$CF_CONFIG_NO_LAMBDA" > cf_config.json
        
        # Update CloudFront distribution
        aws cloudfront update-distribution --id "$CF_DIST_ID" --distribution-config file://cf_config.json --if-match "$ETAG" --region "$REGION" --profile "$PROFILE" --output text --no-cli-pager > /dev/null 2>&1
        
        echo "Waiting for CloudFront distribution to deploy (this may take a while)..."
        aws cloudfront wait distribution-deployed --id "$CF_DIST_ID" --region "$REGION" --profile "$PROFILE" --no-cli-pager
        
        # Clean up temporary file
        rm -f cf_config.json
    else
        echo "No Lambda@Edge function found with name: $LAMBDA_FUNCTION"
    fi
else
    echo "No CloudFront distribution found in the stack"
fi

# Find all S3 buckets associated with the stack
echo "Finding S3 buckets associated with the stack..."
BUCKETS=$(aws cloudformation describe-stack-resources \
    --stack-name $STACK_NAME \
    --query "StackResources[?ResourceType=='AWS::S3::Bucket'].PhysicalResourceId" \
    --output text \
    --region $REGION \
    --profile $PROFILE) || handle_error "Failed to retrieve S3 buckets"

# Empty each bucket
if [ -n "$BUCKETS" ]; then
    echo "Found the following buckets: $BUCKETS"
    for BUCKET in $BUCKETS; do
        echo "Emptying bucket: $BUCKET"
        aws s3 rm s3://$BUCKET --recursive --region $REGION --profile $PROFILE || handle_error "Failed to empty bucket $BUCKET"
    done
else
    echo "No S3 buckets found in the stack"
fi

# Find and remove all images from ECR repositories
echo "Finding ECR repositories associated with the stack..."
ECR_REPOS=$(aws cloudformation describe-stack-resources \
    --stack-name $STACK_NAME \
    --query "StackResources[?ResourceType=='AWS::ECR::Repository'].PhysicalResourceId" \
    --output text \
    --region $REGION \
    --profile $PROFILE) || handle_error "Failed to retrieve ECR repositories"

if [ -n "$ECR_REPOS" ]; then
    echo "Found the following ECR repositories: $ECR_REPOS"
    for REPO in $ECR_REPOS; do
        echo "Removing all images from repository: $REPO"
        # Get image digests
        IMAGE_DIGESTS=$(aws ecr list-images \
            --repository-name $REPO \
            --query 'imageIds[*].imageDigest' \
            --output text \
            --region $REGION \
            --profile $PROFILE) || handle_error "Failed to list images in repository $REPO"
        
        # Delete images if any exist
        if [ -n "$IMAGE_DIGESTS" ]; then
            for DIGEST in $IMAGE_DIGESTS; do
                echo "Deleting image: $DIGEST"
                aws ecr batch-delete-image \
                    --repository-name $REPO \
                    --image-ids imageDigest=$DIGEST \
                    --region $REGION \
                    --profile $PROFILE \
                    --output text || handle_error "Failed to delete image $DIGEST from repository $REPO"
            done
        else
            echo "No images found in repository: $REPO"
        fi
    done
else
    echo "No ECR repositories found in the stack"
fi

# Also check for ECR repositories created outside of CloudFormation
echo "Checking for ECR repository created by the deployment script..."
ECR_REPO="${STACK_NAME}-network-operations-agent-streamlit"
if aws ecr describe-repositories --repository-names $ECR_REPO --region $REGION --profile $PROFILE &>/dev/null; then
    echo "Found ECR repository created outside of CloudFormation: $ECR_REPO"
    
    # Remove all images from the repository
    echo "Removing all images from repository: $ECR_REPO"
    IMAGE_DIGESTS=$(aws ecr list-images \
        --repository-name $ECR_REPO \
        --query 'imageIds[*].imageDigest' \
        --output text \
        --region $REGION \
        --profile $PROFILE) || handle_error "Failed to list images in repository $ECR_REPO"
    
    # Delete images if any exist
    if [ -n "$IMAGE_DIGESTS" ]; then
        for DIGEST in $IMAGE_DIGESTS; do
            echo "Deleting image: $DIGEST"
            aws ecr batch-delete-image \
                --repository-name $ECR_REPO \
                --image-ids imageDigest=$DIGEST \
                --region $REGION \
                --profile $PROFILE \
                --output text || handle_error "Failed to delete image $DIGEST from repository $ECR_REPO"
        done
    else
        echo "No images found in repository: $ECR_REPO"
    fi
    
    # Delete the repository
    echo "Deleting ECR repository: $ECR_REPO"
    aws ecr delete-repository --repository-name $ECR_REPO --force --region $REGION --profile $PROFILE --output text || handle_error "Failed to delete ECR repository $ECR_REPO"
else
    echo "No ECR repository found with name: $ECR_REPO"
fi

echo "Cleaning up resources for stack: $STACK_NAME in region: $REGION using profile: $PROFILE"

# Find and stop ECS tasks to prevent ClusterContainsTasksException
echo "Finding ECS clusters in the stack..."
ECS_CLUSTERS=$(aws cloudformation describe-stack-resources \
    --stack-name $STACK_NAME \
    --query "StackResources[?ResourceType=='AWS::ECS::Cluster'].PhysicalResourceId" \
    --output text \
    --region $REGION \
    --profile $PROFILE) || handle_error "Failed to retrieve ECS clusters"

if [ -n "$ECS_CLUSTERS" ]; then
    echo "Found the following ECS clusters: $ECS_CLUSTERS"
    for CLUSTER in $ECS_CLUSTERS; do
        echo "Processing ECS cluster: $CLUSTER"
        
        # Find and update ECS services to desired count 0
        echo "Finding services in cluster $CLUSTER..."
        SERVICES=$(aws ecs list-services \
            --cluster $CLUSTER \
            --query "serviceArns" \
            --output text \
            --region $REGION \
            --profile $PROFILE) || handle_error "Failed to list services in cluster $CLUSTER"
        
        if [ -n "$SERVICES" ]; then
            echo "Found services: $SERVICES"
            for SERVICE in $SERVICES; do
                echo "Updating service $SERVICE to desired count 0..."
                aws ecs update-service \
                    --cluster "$CLUSTER" \
                    --service "$SERVICE" \
                    --desired-count 0 \
                    --region "$REGION" \
                    --profile "$PROFILE" \
                    --output text \
                    --no-cli-pager > /dev/null 2>&1 \
                    --output text || handle_error "Failed to update service $SERVICE"
            done
            
            # Wait for services to scale down
            echo "Waiting for services to scale down (30 seconds)..."
            sleep 30
        else
            echo "No services found in cluster $CLUSTER"
        fi
        
        # Find and stop any remaining tasks
        echo "Finding tasks in cluster $CLUSTER..."
        TASKS=$(aws ecs list-tasks \
            --cluster $CLUSTER \
            --query "taskArns" \
            --output text \
            --region $REGION \
            --profile $PROFILE) || handle_error "Failed to list tasks in cluster $CLUSTER"
        
        if [ -n "$TASKS" ]; then
            echo "Found tasks: $TASKS"
            for TASK in $TASKS; do
                echo "Stopping task $TASK..."
                aws ecs stop-task \
                    --cluster $CLUSTER \
                    --task $TASK \
                    --region $REGION \
                    --profile $PROFILE \
                    --output text || handle_error "Failed to stop task $TASK"
            done
            
            # Wait for tasks to stop
            echo "Waiting for tasks to stop (30 seconds)..."
            sleep 30
        else
            echo "No tasks found in cluster $CLUSTER"
        fi
    done
else
    echo "No ECS clusters found in the stack"
fi

# Delete Bedrock agents that start with the stack name
echo "Listing and deleting Bedrock agents that start with $STACK_NAME..."
AGENTS=$(aws bedrock-agent list-agents --query "agentSummaries[?starts_with(agentName, '$STACK_NAME')].agentId" --output text --region $REGION --profile $PROFILE)

if [ -n "$AGENTS" ]; then
  for AGENT_ID in $AGENTS; do
    echo "Deleting agent aliases for agent $AGENT_ID..."
    ALIASES=$(aws bedrock-agent list-agent-aliases --agent-id $AGENT_ID --query "agentAliasSummaries[].agentAliasId" --output text --region $REGION --profile $PROFILE)
    
    for ALIAS_ID in $ALIASES; do
      echo "Deleting agent alias $ALIAS_ID..."
      aws bedrock-agent delete-agent-alias --agent-id $AGENT_ID --agent-alias-id $ALIAS_ID --region $REGION --profile $PROFILE --output text
    done
    
    # Wait for aliases to be deleted
    echo "Waiting for aliases to be deleted..."
    sleep 10
    
    echo "Deleting agent $AGENT_ID..."
    aws bedrock-agent delete-agent --agent-id $AGENT_ID --region $REGION --profile $PROFILE --output text
  done
else
  echo "No Bedrock agents found starting with $STACK_NAME"
fi

# Delete the stack
echo "Deleting stack: $STACK_NAME"
aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION --profile $PROFILE --output text || handle_error "Failed to initiate stack deletion"

echo "Waiting for stack deletion to complete..."
aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $REGION --profile $PROFILE || handle_error "Stack deletion did not complete successfully"

echo "Cleanup completed!"
echo "Note: If there were any Bedrock agents created outside of CloudFormation, you may need to delete them manually."

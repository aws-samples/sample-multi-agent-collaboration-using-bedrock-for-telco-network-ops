param(
    [string]$StackName = "netops",
    [string]$Region = "us-east-1",
    [string]$Profile = "default"
)

Write-Host "Starting cleanup for stack: $StackName in region: $Region"

# Function to handle errors gracefully
function Handle-Error {
    param([string]$Message)
    Write-Warning $Message
}

# Check if stack exists
try {
    aws cloudformation describe-stacks --stack-name $StackName --region $Region --profile $Profile --output text | Out-Null
} catch {
    Write-Host "Stack $StackName does not exist in region $Region. Nothing to clean up."
    exit 0
}

# Get CloudFront distribution ID
Write-Host "Finding CloudFront distribution associated with the stack..."
$CF_DIST_ID = aws cloudformation describe-stacks --stack-name $StackName --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDistributionId'].OutputValue" --output text --region $Region --profile $Profile

if ($CF_DIST_ID -and $CF_DIST_ID -ne "None") {
    Write-Host "Found CloudFront distribution: $CF_DIST_ID"
    
    # Check for pending CloudFront invalidations
    Write-Host "Checking for pending CloudFront invalidations..."
    $INVALIDATIONS = aws cloudfront list-invalidations --distribution-id $CF_DIST_ID --query 'InvalidationList.Items[?Status==`InProgress`].Id' --output text --region $Region --profile $Profile
    
    if ($INVALIDATIONS -and $INVALIDATIONS -ne "") {
        $INVALIDATIONS.Split("`t") | ForEach-Object {
            Write-Host "Waiting for invalidation to complete: $_"
            aws cloudfront wait invalidation-completed --distribution-id $CF_DIST_ID --id $_ --region $Region --profile $Profile
        }
    } else {
        Write-Host "No pending CloudFront invalidations found"
    }
    
    # Check for Lambda@Edge function
    $LAMBDA_FUNCTION = "$StackName-cf-auth"
    try {
        $LAMBDA_EXISTS = aws lambda get-function --function-name $LAMBDA_FUNCTION --query 'Configuration.FunctionName' --output text --region $Region --profile $Profile 2>$null
    } catch {
        $LAMBDA_EXISTS = $null
    }
    
    if ($LAMBDA_EXISTS) {
        Write-Host "Found Lambda@Edge function: $LAMBDA_FUNCTION"
        Write-Host "Disassociating Lambda@Edge function from CloudFront..."
        
        # Get the current distribution configuration
        $CF_CONFIG = aws cloudfront get-distribution-config --id $CF_DIST_ID --region $Region --profile $Profile | ConvertFrom-Json
        $ETAG = $CF_CONFIG.ETag
        
        # Remove Lambda associations
        $CF_CONFIG.DistributionConfig.DefaultCacheBehavior.LambdaFunctionAssociations = @{
            Quantity = 0
            Items = @()
        }
        
        # Save the updated config to a file
        $CF_CONFIG.DistributionConfig | ConvertTo-Json -Depth 10 | Out-File -FilePath "cf_config.json" -Encoding UTF8
        
        # Update CloudFront distribution
        aws cloudfront update-distribution --id $CF_DIST_ID --distribution-config file://cf_config.json --if-match $ETAG --region $Region --profile $Profile --output text --no-cli-pager | Out-Null
        
        Write-Host "Waiting for CloudFront distribution to deploy (this may take a while)..."
        aws cloudfront wait distribution-deployed --id $CF_DIST_ID --region $Region --profile $Profile --no-cli-pager
        
        # Clean up temporary file
        Remove-Item -Path "cf_config.json" -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host "No Lambda@Edge function found with name: $LAMBDA_FUNCTION"
    }
} else {
    Write-Host "No CloudFront distribution found in the stack"
}

# Find all S3 buckets associated with the stack
Write-Host "Finding S3 buckets associated with the stack..."
try {
    $BUCKETS = aws cloudformation describe-stack-resources --stack-name $StackName --query "StackResources[?ResourceType=='AWS::S3::Bucket'].PhysicalResourceId" --output text --region $Region --profile $Profile
} catch {
    Handle-Error "Failed to retrieve S3 buckets"
    $BUCKETS = $null
}

# Empty each bucket
if ($BUCKETS -and $BUCKETS -ne "") {
    Write-Host "Found the following buckets: $BUCKETS"
    $BUCKETS.Split("`t") | ForEach-Object {
        Write-Host "Emptying bucket: $_"
        try {
            aws s3 rm "s3://$_" --recursive --region $Region --profile $Profile
        } catch {
            Handle-Error "Failed to empty bucket $_"
        }
    }
} else {
    Write-Host "No S3 buckets found in the stack"
}

# Find and remove all images from ECR repositories
Write-Host "Finding ECR repositories associated with the stack..."
try {
    $ECR_REPOS = aws cloudformation describe-stack-resources --stack-name $StackName --query "StackResources[?ResourceType=='AWS::ECR::Repository'].PhysicalResourceId" --output text --region $Region --profile $Profile
} catch {
    Handle-Error "Failed to retrieve ECR repositories"
    $ECR_REPOS = $null
}

if ($ECR_REPOS -and $ECR_REPOS -ne "") {
    Write-Host "Found the following ECR repositories: $ECR_REPOS"
    $ECR_REPOS.Split("`t") | ForEach-Object {
        $REPO = $_
        Write-Host "Removing all images from repository: $REPO"
        
        try {
            $IMAGE_DIGESTS = aws ecr list-images --repository-name $REPO --query 'imageIds[*].imageDigest' --output text --region $Region --profile $Profile
        } catch {
            Handle-Error "Failed to list images in repository $REPO"
            $IMAGE_DIGESTS = $null
        }
        
        if ($IMAGE_DIGESTS -and $IMAGE_DIGESTS -ne "") {
            $IMAGE_DIGESTS.Split("`t") | ForEach-Object {
                Write-Host "Deleting image: $_"
                try {
                    aws ecr batch-delete-image --repository-name $REPO --image-ids imageDigest=$_ --region $Region --profile $Profile --output text
                } catch {
                    Handle-Error "Failed to delete image $_ from repository $REPO"
                }
            }
        } else {
            Write-Host "No images found in repository: $REPO"
        }
    }
} else {
    Write-Host "No ECR repositories found in the stack"
}

# Also check for ECR repositories created outside of CloudFormation
Write-Host "Checking for ECR repository created by the deployment script..."
$ECR_REPO = "$StackName-network-operations-agent-streamlit"
try {
    aws ecr describe-repositories --repository-names $ECR_REPO --region $Region --profile $Profile --output text | Out-Null
    $ECR_EXISTS = $true
} catch {
    $ECR_EXISTS = $false
}

if ($ECR_EXISTS) {
    Write-Host "Found ECR repository created outside of CloudFormation: $ECR_REPO"
    
    # Remove all images from the repository
    Write-Host "Removing all images from repository: $ECR_REPO"
    try {
        $IMAGE_DIGESTS = aws ecr list-images --repository-name $ECR_REPO --query 'imageIds[*].imageDigest' --output text --region $Region --profile $Profile
    } catch {
        Handle-Error "Failed to list images in repository $ECR_REPO"
        $IMAGE_DIGESTS = $null
    }
    
    if ($IMAGE_DIGESTS -and $IMAGE_DIGESTS -ne "") {
        $IMAGE_DIGESTS.Split("`t") | ForEach-Object {
            Write-Host "Deleting image: $_"
            try {
                aws ecr batch-delete-image --repository-name $ECR_REPO --image-ids imageDigest=$_ --region $Region --profile $Profile --output text
            } catch {
                Handle-Error "Failed to delete image $_ from repository $ECR_REPO"
            }
        }
    } else {
        Write-Host "No images found in repository: $ECR_REPO"
    }
    
    # Delete the repository
    Write-Host "Deleting ECR repository: $ECR_REPO"
    try {
        aws ecr delete-repository --repository-name $ECR_REPO --force --region $Region --profile $Profile --output text
    } catch {
        Handle-Error "Failed to delete ECR repository $ECR_REPO"
    }
} else {
    Write-Host "No ECR repository found with name: $ECR_REPO"
}

Write-Host "Cleaning up resources for stack: $StackName in region: $Region using profile: $Profile"

# Find and stop ECS tasks to prevent ClusterContainsTasksException
Write-Host "Finding ECS clusters in the stack..."
try {
    $ECS_CLUSTERS = aws cloudformation describe-stack-resources --stack-name $StackName --query "StackResources[?ResourceType=='AWS::ECS::Cluster'].PhysicalResourceId" --output text --region $Region --profile $Profile
} catch {
    Handle-Error "Failed to retrieve ECS clusters"
    $ECS_CLUSTERS = $null
}

if ($ECS_CLUSTERS -and $ECS_CLUSTERS -ne "") {
    Write-Host "Found the following ECS clusters: $ECS_CLUSTERS"
    $ECS_CLUSTERS.Split("`t") | ForEach-Object {
        $CLUSTER = $_
        Write-Host "Processing ECS cluster: $CLUSTER"
        
        # Find and update ECS services to desired count 0
        Write-Host "Finding services in cluster $CLUSTER..."
        try {
            $SERVICES = aws ecs list-services --cluster $CLUSTER --query "serviceArns" --output text --region $Region --profile $Profile
        } catch {
            Handle-Error "Failed to list services in cluster $CLUSTER"
            $SERVICES = $null
        }
        
        if ($SERVICES -and $SERVICES -ne "") {
            Write-Host "Found services: $SERVICES"
            $SERVICES.Split("`t") | ForEach-Object {
                Write-Host "Updating service $_ to desired count 0..."
                try {
                    aws ecs update-service --cluster $CLUSTER --service $_ --desired-count 0 --region $Region --profile $Profile --output text --no-cli-pager | Out-Null
                } catch {
                    Handle-Error "Failed to update service $_"
                }
            }
            
            # Wait for services to scale down
            Write-Host "Waiting for services to scale down (30 seconds)..."
            Start-Sleep -Seconds 30
        } else {
            Write-Host "No services found in cluster $CLUSTER"
        }
        
        # Find and stop any remaining tasks
        Write-Host "Finding tasks in cluster $CLUSTER..."
        try {
            $TASKS = aws ecs list-tasks --cluster $CLUSTER --query "taskArns" --output text --region $Region --profile $Profile
        } catch {
            Handle-Error "Failed to list tasks in cluster $CLUSTER"
            $TASKS = $null
        }
        
        if ($TASKS -and $TASKS -ne "") {
            Write-Host "Found tasks: $TASKS"
            $TASKS.Split("`t") | ForEach-Object {
                Write-Host "Stopping task $_..."
                try {
                    aws ecs stop-task --cluster $CLUSTER --task $_ --region $Region --profile $Profile --output text
                } catch {
                    Handle-Error "Failed to stop task $_"
                }
            }
            
            # Wait for tasks to stop
            Write-Host "Waiting for tasks to stop (30 seconds)..."
            Start-Sleep -Seconds 30
        } else {
            Write-Host "No tasks found in cluster $CLUSTER"
        }
    }
} else {
    Write-Host "No ECS clusters found in the stack"
}

# Delete Bedrock agents that start with the stack name
Write-Host "Listing and deleting Bedrock agents that start with $StackName..."
$AGENTS = aws bedrock-agent list-agents --query "agentSummaries[?starts_with(agentName, '$StackName')].agentId" --output text --region $Region --profile $Profile

if ($AGENTS -and $AGENTS -ne "") {
    $AGENTS.Split("`t") | ForEach-Object {
        $AGENT_ID = $_
        Write-Host "Deleting agent aliases for agent $AGENT_ID..."
        $ALIASES = aws bedrock-agent list-agent-aliases --agent-id $AGENT_ID --query "agentAliasSummaries[].agentAliasId" --output text --region $Region --profile $Profile
        
        if ($ALIASES -and $ALIASES -ne "") {
            $ALIASES.Split("`t") | ForEach-Object {
                Write-Host "Deleting agent alias $_..."
                aws bedrock-agent delete-agent-alias --agent-id $AGENT_ID --agent-alias-id $_ --region $Region --profile $Profile --output text
            }
        }
        
        # Wait for aliases to be deleted
        Write-Host "Waiting for aliases to be deleted..."
        Start-Sleep -Seconds 10
        
        Write-Host "Deleting agent $AGENT_ID..."
        aws bedrock-agent delete-agent --agent-id $AGENT_ID --region $Region --profile $Profile --output text
    }
} else {
    Write-Host "No Bedrock agents found starting with $StackName"
}

# Delete the stack
Write-Host "Deleting stack: $StackName"
try {
    aws cloudformation delete-stack --stack-name $StackName --region $Region --profile $Profile --output text
} catch {
    Handle-Error "Failed to initiate stack deletion"
}

Write-Host "Waiting for stack deletion to complete..."
try {
    aws cloudformation wait stack-delete-complete --stack-name $StackName --region $Region --profile $Profile
} catch {
    Handle-Error "Stack deletion did not complete successfully"
}

Write-Host "Cleanup completed!"
Write-Host "Note: If there were any Bedrock agents created outside of CloudFormation, you may need to delete them manually."

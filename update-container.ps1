# PowerShell script for updating container on Windows
param(
    [string]$StackName = "netops",
    [string]$Region = "us-east-1", 
    [string]$Profile = "default"
)

$ErrorActionPreference = "Stop"

Write-Host "Updating container for $StackName in $Region using profile $Profile" -ForegroundColor Green

# Function to check if a command exists
function Test-Command {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

# Check prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor Yellow
$missingTools = @()
if (-not (Test-Command "aws")) { $missingTools += "AWS CLI" }
if (-not (Test-Command "docker")) { $missingTools += "Docker" }

if ($missingTools.Count -gt 0) {
    Write-Host "Missing required tools: $($missingTools -join ', ')" -ForegroundColor Red
    Write-Host "Please install the missing tools and try again." -ForegroundColor Red
    exit 1
}

# Get ECR repository URI
Write-Host "Getting ECR repository information..." -ForegroundColor Yellow
$ECR_REPO = "$StackName-network-operations-agent-streamlit"

try {
    $ECR_URI = aws ecr describe-repositories --repository-names $ECR_REPO --query 'repositories[0].repositoryUri' --output text --region $Region --profile $Profile
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrEmpty($ECR_URI)) {
        throw "ECR repository not found. Please run the full deployment first."
    }
} catch {
    Write-Host "Error: ECR repository '$ECR_REPO' not found. Please run the full deployment first." -ForegroundColor Red
    exit 1
}

Write-Host "ECR URI: $ECR_URI" -ForegroundColor Green

# Login to ECR
Write-Host "Logging in to ECR..." -ForegroundColor Yellow
try {
    $ECR_DOMAIN = $ECR_URI.Split('/')[0]
    $loginToken = aws ecr get-login-password --region $Region --profile $Profile
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to get ECR login token"
    }
    
    echo $loginToken | docker login --username AWS --password-stdin $ECR_DOMAIN
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to login to ECR"
    }
} catch {
    Write-Host "Error logging in to ECR: $_" -ForegroundColor Red
    exit 1
}

# Build Docker image
Write-Host "Building updated Docker image..." -ForegroundColor Yellow
try {
    docker build --platform linux/amd64 -t "${ECR_URI}:latest" .
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build Docker image"
    }
} catch {
    Write-Host "Error building Docker image: $_" -ForegroundColor Red
    exit 1
}

# Push Docker image
Write-Host "Pushing updated Docker image to ECR..." -ForegroundColor Yellow
try {
    docker push "${ECR_URI}:latest"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to push Docker image"
    }
} catch {
    Write-Host "Error pushing Docker image: $_" -ForegroundColor Red
    exit 1
}

# Force ECS service to update
Write-Host "Forcing ECS service to update..." -ForegroundColor Yellow
try {
    $CLUSTER_NAME = "$StackName-cluster"
    $SERVICE_NAME = "$StackName-service"
    
    aws ecs update-service --cluster $CLUSTER_NAME --service $SERVICE_NAME --force-new-deployment --region $Region --profile $Profile | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to update ECS service"
    }
    
    Write-Host "ECS service update initiated successfully" -ForegroundColor Green
} catch {
    Write-Host "Error updating ECS service: $_" -ForegroundColor Red
    exit 1
}

# Wait for deployment to complete
Write-Host "Waiting for deployment to complete..." -ForegroundColor Yellow
Write-Host "This may take a few minutes..." -ForegroundColor Gray

$maxWaitTime = 600  # 10 minutes
$waitInterval = 30  # 30 seconds
$elapsedTime = 0

while ($elapsedTime -lt $maxWaitTime) {
    try {
        $serviceStatus = aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --query 'services[0].deployments[?status==`RUNNING`].status' --output text --region $Region --profile $Profile
        
        if ($serviceStatus -eq "RUNNING") {
            Write-Host "Deployment completed successfully!" -ForegroundColor Green
            break
        }
        
        Write-Host "Still deploying... (elapsed: $elapsedTime seconds)" -ForegroundColor Gray
        Start-Sleep -Seconds $waitInterval
        $elapsedTime += $waitInterval
    } catch {
        Write-Host "Warning: Could not check deployment status: $_" -ForegroundColor Yellow
        break
    }
}

if ($elapsedTime -ge $maxWaitTime) {
    Write-Host "Warning: Deployment is taking longer than expected. Check the AWS console for status." -ForegroundColor Yellow
}

# Get application URLs
Write-Host "Retrieving application URLs..." -ForegroundColor Yellow
try {
    $CF_URL = aws cloudformation describe-stacks --stack-name $StackName --query "Stacks[0].Outputs[?OutputKey=='CloudFrontURL'].OutputValue" --output text --region $Region --profile $Profile
    $ALB_URL = aws cloudformation describe-stacks --stack-name $StackName --query "Stacks[0].Outputs[?OutputKey=='ALBEndpoint'].OutputValue" --output text --region $Region --profile $Profile
    
    Write-Host "`nContainer update completed!" -ForegroundColor Green
    Write-Host "Application URLs:" -ForegroundColor Cyan
    Write-Host "  CloudFront: $CF_URL" -ForegroundColor Green
    Write-Host "  ALB (direct): $ALB_URL" -ForegroundColor Green
} catch {
    Write-Host "Warning: Could not retrieve application URLs: $_" -ForegroundColor Yellow
}

Write-Host "`nTo monitor the deployment:" -ForegroundColor Yellow
Write-Host "1. Check ECS service status:" -ForegroundColor White
Write-Host "   aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $Region --profile $Profile" -ForegroundColor Gray
Write-Host ""
Write-Host "2. View CloudWatch logs:" -ForegroundColor White
Write-Host "   aws logs get-log-events --log-group-name /ecs/$StackName --log-stream-name `$(aws logs describe-log-streams --log-group-name /ecs/$StackName --order-by LastEventTime --descending --limit 1 --query 'logStreams[0].logStreamName' --output text --region $Region --profile $Profile) --region $Region --profile $Profile" -ForegroundColor Gray

Write-Host "`nContainer update completed successfully!" -ForegroundColor Green

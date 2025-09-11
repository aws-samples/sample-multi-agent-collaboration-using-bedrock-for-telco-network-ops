# PowerShell script for Windows deployment
param(
    [string]$StackName = "netops",
    [string]$Region = "us-east-1", 
    [string]$Profile = "default"
)

# Enable strict error handling but allow controlled error capture
$ErrorActionPreference = "Continue"

Write-Host "Deploying $StackName to $Region using profile $Profile" -ForegroundColor Green

# Validate AWS configuration
Write-Host "Validating AWS configuration..." -ForegroundColor Yellow
try {
    # Test basic AWS CLI functionality
    $identityCmd = "aws sts get-caller-identity --profile $Profile --region $Region"
    $awsIdentity = Invoke-Expression $identityCmd 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "AWS authentication failed. Command: $identityCmd" -ForegroundColor Red
        Write-Host "Output: $awsIdentity" -ForegroundColor Red
        Write-Host "Please run 'aws configure' to set up your credentials." -ForegroundColor Yellow
        exit 1
    }
    
    $identity = $awsIdentity | ConvertFrom-Json
    Write-Host "AWS Identity validated:" -ForegroundColor Green
    Write-Host "  Account: $($identity.Account)" -ForegroundColor Green
    Write-Host "  User/Role: $($identity.Arn)" -ForegroundColor Green
    
    # Test ECR permissions
    Write-Host "Testing ECR permissions..." -ForegroundColor Yellow
    $ecrTestCmd = "aws ecr describe-repositories --region $Region --profile $Profile --max-items 1"
    $ecrTest = Invoke-Expression $ecrTestCmd 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ECR access test failed. Command: $ecrTestCmd" -ForegroundColor Red
        Write-Host "Output: $ecrTest" -ForegroundColor Red
        Write-Host "Your AWS user/role needs ECR permissions. Required policies:" -ForegroundColor Yellow
        Write-Host "  - AmazonEC2ContainerRegistryFullAccess (or custom ECR permissions)" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "ECR permissions validated" -ForegroundColor Green
    
} catch {
    Write-Host "AWS configuration validation failed: $_" -ForegroundColor Red
    Write-Host "Please ensure AWS CLI is installed and configured properly." -ForegroundColor Yellow
    exit 1
}

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
if (-not (Test-Command "sam")) { $missingTools += "SAM CLI" }
if (-not (Test-Command "docker")) { $missingTools += "Docker" }
if (-not (Test-Command "python")) { $missingTools += "Python" }

if ($missingTools.Count -gt 0) {
    Write-Host "Missing required tools: $($missingTools -join ', ')" -ForegroundColor Red
    Write-Host "Please install the missing tools and try again." -ForegroundColor Red
    exit 1
}

# Create lambda layer directory
Write-Host "Creating lambda layer..." -ForegroundColor Yellow
if (Test-Path "lambda_layer") {
    Remove-Item -Recurse -Force "lambda_layer"
}
New-Item -ItemType Directory -Path "lambda_layer\python" -Force | Out-Null

# Install minimal dependencies to reduce layer size
Write-Host "Installing minimal dependencies for Lambda layer..." -ForegroundColor Yellow
try {
    python -m pip install pandas --no-deps -t lambda_layer\python --only-binary=:all: --platform manylinux2014_x86_64 --python-version 3.9 --implementation cp
    python -m pip install numpy --no-deps -t lambda_layer\python --only-binary=:all: --platform manylinux2014_x86_64 --python-version 3.9 --implementation cp
    python -m pip install pytz -t lambda_layer\python --only-binary=:all: --platform manylinux2014_x86_64 --python-version 3.9 --implementation cp
    python -m pip install python-dateutil -t lambda_layer\python --only-binary=:all: --platform manylinux2014_x86_64 --python-version 3.9 --implementation cp
    python -m pip install six -t lambda_layer\python --only-binary=:all: --platform manylinux2014_x86_64 --python-version 3.9 --implementation cp
} catch {
    Write-Host "Error installing Python dependencies: $_" -ForegroundColor Red
    exit 1
}

# Clean up unnecessary files to reduce size
Write-Host "Cleaning up unnecessary files to reduce layer size..." -ForegroundColor Yellow
Get-ChildItem -Path "lambda_layer\python" -Recurse -Directory | Where-Object { $_.Name -match "\.dist-info$|\.egg-info$|__pycache__$|tests$" } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path "lambda_layer\python" -Recurse -File | Where-Object { $_.Extension -match "\.pyc$|\.pyo$" } | Remove-Item -Force -ErrorAction SilentlyContinue

# Build and push Docker image
Write-Host "Building and pushing Docker image..." -ForegroundColor Yellow
$ECR_REPO = "$StackName-network-operations-agent-streamlit"

# Check if ECR repository exists
Write-Host "Checking ECR repository: $ECR_REPO" -ForegroundColor Yellow
$ECR_URI = $null

# First, check if repository exists
try {
    $repoCheckCmd = "aws ecr describe-repositories --repository-names `"$ECR_REPO`" --region $Region --profile $Profile"
    $repoCheckOutput = Invoke-Expression $repoCheckCmd 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        # Repository exists, get URI
        $uriCmd = "aws ecr describe-repositories --repository-names `"$ECR_REPO`" --query 'repositories[0].repositoryUri' --output text --region $Region --profile $Profile"
        $ECR_URI = Invoke-Expression $uriCmd
        Write-Host "Found existing ECR repository" -ForegroundColor Green
    } else {
        # Repository doesn't exist, create it
        Write-Host "ECR repository not found. Creating new repository..." -ForegroundColor Yellow
        $createCmd = "aws ecr create-repository --repository-name `"$ECR_REPO`" --region $Region --profile $Profile"
        $createOutput = Invoke-Expression $createCmd 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            $uriCmd = "aws ecr describe-repositories --repository-names `"$ECR_REPO`" --query 'repositories[0].repositoryUri' --output text --region $Region --profile $Profile"
            $ECR_URI = Invoke-Expression $uriCmd
            Write-Host "ECR repository created successfully" -ForegroundColor Green
        } else {
            Write-Host "Failed to create ECR repository. Error details:" -ForegroundColor Red
            Write-Host "Command: $createCmd" -ForegroundColor Yellow
            Write-Host "Output: $createOutput" -ForegroundColor Red
            
            # Check if it's a credentials issue
            if ($createOutput -match "Unable to locate credentials|No credentials|InvalidUserID.NotFound|UnauthorizedOperation") {
                Write-Host "This appears to be an AWS credentials issue. Please run:" -ForegroundColor Yellow
                Write-Host "  aws configure" -ForegroundColor Cyan
                Write-Host "Or set up your AWS credentials properly." -ForegroundColor Yellow
            }
            exit 1
        }
    }
} catch {
    Write-Host "Error executing AWS CLI command: $_" -ForegroundColor Red
    Write-Host "Please ensure AWS CLI is properly installed and configured." -ForegroundColor Yellow
    exit 1
}

if ([string]::IsNullOrEmpty($ECR_URI)) {
    Write-Host "Failed to get ECR repository URI" -ForegroundColor Red
    exit 1
}

Write-Host "ECR URI: $ECR_URI" -ForegroundColor Green

# Login to ECR
Write-Host "Logging in to ECR..." -ForegroundColor Yellow
$ECR_DOMAIN = $ECR_URI.Split('/')[0]

# Get ECR login token
try {
    $loginCmd = "aws ecr get-login-password --region $Region --profile $Profile"
    $loginToken = Invoke-Expression $loginCmd 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to get ECR login token. Output:" -ForegroundColor Red
        Write-Host $loginToken -ForegroundColor Red
        exit 1
    }
    
    # Login to Docker
    $loginToken | docker login --username AWS --password-stdin $ECR_DOMAIN
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to login to Docker. Make sure Docker is running." -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "Error during ECR login: $_" -ForegroundColor Red
    exit 1
}

Write-Host "Successfully logged in to ECR" -ForegroundColor Green

# Check Docker status
Write-Host "Checking Docker status..." -ForegroundColor Yellow
try {
    $dockerVersion = docker version --format json 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Docker is not running or not accessible. Error:" -ForegroundColor Red
        Write-Host $dockerVersion -ForegroundColor Red
        Write-Host "Please start Docker Desktop and ensure it's running properly." -ForegroundColor Yellow
        Write-Host "You can start Docker Desktop from the Start menu or system tray." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "Docker is running" -ForegroundColor Green
} catch {
    Write-Host "Error checking Docker status: $_" -ForegroundColor Red
    Write-Host "Please ensure Docker Desktop is installed and running." -ForegroundColor Yellow
    exit 1
}

# Build Docker image
Write-Host "Building Docker image with explicit platform..." -ForegroundColor Yellow
try {
    $buildOutput = docker build --platform linux/amd64 -t "${ECR_URI}:latest" . 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Docker build failed. Output:" -ForegroundColor Red
        Write-Host $buildOutput -ForegroundColor Red
        
        if ($buildOutput -match "pipe.*dockerDesktopLinuxEngine|cannot connect to the Docker daemon") {
            Write-Host "Docker Desktop appears to not be running properly." -ForegroundColor Yellow
            Write-Host "Please restart Docker Desktop and try again." -ForegroundColor Yellow
        }
        exit 1
    }
    Write-Host "Docker image built successfully" -ForegroundColor Green
} catch {
    Write-Host "Error building Docker image: $_" -ForegroundColor Red
    exit 1
}

# Push Docker image
Write-Host "Pushing Docker image to ECR..." -ForegroundColor Yellow
try {
    $pushOutput = docker push "${ECR_URI}:latest" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Docker push failed. Output:" -ForegroundColor Red
        Write-Host $pushOutput -ForegroundColor Red
        exit 1
    }
    Write-Host "Docker image pushed successfully" -ForegroundColor Green
} catch {
    Write-Host "Error pushing Docker image: $_" -ForegroundColor Red
    exit 1
}

# Clean up build artifacts
Write-Host "Cleaning up build artifacts..." -ForegroundColor Yellow
if (Test-Path ".aws-sam") {
    Remove-Item -Recurse -Force ".aws-sam" -ErrorAction SilentlyContinue
}

# Check Python version for SAM compatibility
Write-Host "Checking Python version for SAM compatibility..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Found Python version: $pythonVersion" -ForegroundColor Yellow
    
    if ($pythonVersion -notmatch "Python 3\.9") {
        Write-Host "Warning: SAM requires Python 3.9 for lambda runtime, but found $pythonVersion" -ForegroundColor Yellow
        Write-Host "Using container-based build to avoid version conflicts..." -ForegroundColor Yellow
        $useContainer = $true
    } else {
        $useContainer = $false
    }
} catch {
    Write-Host "Could not detect Python version, using container build..." -ForegroundColor Yellow
    $useContainer = $true
}

# Deploy SAM template
Write-Host "Deploying SAM template..." -ForegroundColor Yellow
try {
    if ($useContainer) {
        # Use container build to avoid Python version issues
        Write-Host "Building with container (this may take longer but avoids Python version conflicts)..." -ForegroundColor Yellow
        sam build --template template.yaml --use-container
    } else {
        sam build --template template.yaml
    }
    
    if ($LASTEXITCODE -ne 0) {
        if ($useContainer) {
            Write-Host "Container build failed, trying with skip-pull-image..." -ForegroundColor Yellow
            sam build --template template.yaml --use-container --skip-pull-image
            if ($LASTEXITCODE -ne 0) {
                throw "SAM build failed even with container options"
            }
        } else {
            throw "SAM build failed"
        }
    }
    
    sam deploy --stack-name $StackName --region $Region --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM --resolve-s3 --no-fail-on-empty-changeset --parameter-overrides "ContainerImageUri=${ECR_URI}:latest" --template-file .aws-sam\build\template.yaml
    if ($LASTEXITCODE -ne 0) {
        throw "SAM deploy failed"
    }
} catch {
    Write-Host "Error during SAM deployment: $_" -ForegroundColor Red
    exit 1
}

# Get CloudFront URL
Write-Host "Retrieving deployment information..." -ForegroundColor Yellow
try {
    $CF_URL = aws cloudformation describe-stacks --stack-name $StackName --query "Stacks[0].Outputs[?OutputKey=='CloudFrontURL'].OutputValue" --output text --region $Region --profile $Profile
    
    $USER_POOL_ID = aws cloudformation describe-stacks --stack-name $StackName --query "Stacks[0].Outputs[?OutputKey=='CognitoUserPoolId'].OutputValue" --output text --region $Region --profile $Profile
    
    $USER_POOL_NAME = aws cloudformation describe-stacks --stack-name $StackName --query "Stacks[0].Outputs[?OutputKey=='CognitoUserPoolName'].OutputValue" --output text --region $Region --profile $Profile
    
    $SUPERVISOR_AGENT_ID = aws cloudformation describe-stacks --stack-name $StackName --query "Stacks[0].Outputs[?OutputKey=='SupervisorAgentId'].OutputValue" --output text --region $Region --profile $Profile
    
    $SUPERVISOR_ALIAS_ID = aws cloudformation describe-stacks --stack-name $StackName --query "Stacks[0].Outputs[?OutputKey=='SupervisorAliasId'].OutputValue" --output text --region $Region --profile $Profile
    
    $ALB_URL = aws cloudformation describe-stacks --stack-name $StackName --query "Stacks[0].Outputs[?OutputKey=='ALBEndpoint'].OutputValue" --output text --region $Region --profile $Profile
} catch {
    Write-Host "Warning: Could not retrieve all deployment information: $_" -ForegroundColor Yellow
}

# Create a test user in Cognito
if (-not [string]::IsNullOrEmpty($USER_POOL_ID)) {
    Write-Host "Creating test user in Cognito User Pool ($USER_POOL_NAME)..." -ForegroundColor Yellow
    try {
        aws cognito-idp admin-create-user --user-pool-id $USER_POOL_ID --username "netopsuser@example.com" --user-attributes "Name=email,Value=netopsuser@example.com" "Name=email_verified,Value=true" "Name=name,Value=Network Ops User" --temporary-password "Demouser1!" --region $Region --profile $Profile 2>$null
        
        # Set the password permanently (skip the forced password change)
        Write-Host "Setting permanent password for test user..." -ForegroundColor Yellow
        aws cognito-idp admin-set-user-password --user-pool-id $USER_POOL_ID --username "netopsuser@example.com" --password "Demouser2!" --permanent --region $Region --profile $Profile
        
        Write-Host "Test user created successfully:" -ForegroundColor Green
        Write-Host "  Username: netopsuser@example.com" -ForegroundColor Green
        Write-Host "  Password: Demouser2!" -ForegroundColor Green
    } catch {
        Write-Host "Warning: Could not create test user: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "Warning: Could not find Cognito User Pool ID. Test user was not created." -ForegroundColor Yellow
}

# Display deployment results
Write-Host "`nDeployment complete!" -ForegroundColor Green
Write-Host "Streamlit application will be available at: $CF_URL" -ForegroundColor Green
Write-Host "Note: It may take a few minutes for the CloudFront distribution to deploy." -ForegroundColor Yellow
Write-Host ""
Write-Host "Supervisor Agent ID: $SUPERVISOR_AGENT_ID" -ForegroundColor Cyan
Write-Host "Supervisor Agent Alias ID: $SUPERVISOR_ALIAS_ID" -ForegroundColor Cyan
Write-Host ""
Write-Host "For troubleshooting, you can also access the ALB directly at: $ALB_URL" -ForegroundColor Cyan
Write-Host "Check CloudWatch logs for any issues: /ecs/$StackName" -ForegroundColor Cyan

# Add instructions for monitoring deployment
Write-Host "`nTo monitor the deployment:" -ForegroundColor Yellow
Write-Host "1. Check if the ECS service is running:" -ForegroundColor White
Write-Host "   aws ecs describe-services --cluster $StackName-cluster --services $StackName-service --region $Region --profile $Profile" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Check the target group health:" -ForegroundColor White
Write-Host "   aws elbv2 describe-target-health --target-group-arn `$(aws elbv2 describe-target-groups --names $StackName-tg --query 'TargetGroups[0].TargetGroupArn' --output text --region $Region --profile $Profile) --region $Region --profile $Profile" -ForegroundColor Gray
Write-Host ""
Write-Host "3. View CloudWatch logs:" -ForegroundColor White
Write-Host "   aws logs get-log-events --log-group-name /ecs/$StackName --log-stream-name `$(aws logs describe-log-streams --log-group-name /ecs/$StackName --order-by LastEventTime --descending --limit 1 --query 'logStreams[0].logStreamName' --output text --region $Region --profile $Profile) --region $Region --profile $Profile" -ForegroundColor Gray

Write-Host "`nDeployment script completed successfully!" -ForegroundColor Green

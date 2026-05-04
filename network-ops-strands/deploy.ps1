<#
.SYNOPSIS
    Network Operations Platform - Unified Deployment Script (Windows)

.DESCRIPTION
    Deploys the entire platform on Windows. Infrastructure, data, Knowledge Base,
    and frontend steps are native PowerShell. AgentCore agent and MCP deployment
    require WSL or Git Bash (agentcore CLI is Linux/macOS only).

.EXAMPLE
    .\deploy.ps1
    .\deploy.ps1 -CreateDemoUser
    .\deploy.ps1 -SkipInfra -SkipMemory -SkipMcp
#>

param(
    [string]$StackName = "netops",
    [string]$Region = "us-east-1",
    [switch]$SkipInfra,
    [switch]$SkipData,
    [switch]$SkipMemory,
    [switch]$SkipAgents,
    [switch]$SkipMcp,
    [switch]$SkipKb,
    [switch]$SkipFrontend,
    [switch]$CreateDemoUser,
    [string]$DemoUsername = "netopsuser@example.com",
    [string]$DemoPassword = "NetworkOps2026!"
)

$ErrorActionPreference = "Stop"
$Env = "dev"

function Write-Step($msg) { Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }

Write-Host @"

============================================
  Network Operations Platform Deployment
============================================
  Stack:  $StackName
  Region: $Region
  OS:     Windows (PowerShell)
============================================

"@ -ForegroundColor Cyan

# ── Step 1-3: Infrastructure (SAM) ────────────────────────────────
if (-not $SkipInfra) {
    Write-Step "Step 1-3: Building and deploying infrastructure (SAM)"
    sam build --template-file template.yaml --region $Region
    sam deploy `
        --template-file .aws-sam\build\template.yaml `
        --stack-name $StackName `
        --region $Region `
        --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND `
        --no-fail-on-empty-changeset `
        --resolve-s3
    Write-Ok "Infrastructure deployed"
} else { Write-Warn "Skipping infrastructure" }

# ── Get stack outputs ─────────────────────────────────────────────
$rawOutputs = aws cloudformation describe-stacks `
    --stack-name $StackName --region $Region `
    --query "Stacks[0].Outputs" --output json 2>$null
$outputs = $rawOutputs | ConvertFrom-Json

function Get-Output($key) {
    ($outputs | Where-Object { $_.OutputKey -eq $key }).OutputValue
}

$DATA_BUCKET       = Get-Output "DataBucketName"
$FRONTEND_BUCKET   = Get-Output "FrontendBucketName"
$DISTRIBUTION_ID   = Get-Output "CloudFrontDistributionId"
$AGENTCORE_ROLE    = Get-Output "AgentCoreExecutionRoleArn"
$USER_POOL_ID      = Get-Output "UserPoolId"
$USER_POOL_CLIENT  = Get-Output "UserPoolClientId"
$IDENTITY_POOL_ID  = Get-Output "IdentityPoolId"
$API_GW_URL        = Get-Output "ApiGatewayUrl"
$KB_ROLE_ARN       = Get-Output "KnowledgeBaseRoleArn"
$APP_URL           = Get-Output "ApplicationURL"

Write-Host "  Data Bucket:     $DATA_BUCKET"
Write-Host "  Frontend Bucket: $FRONTEND_BUCKET"

# ── Step 3.5: Demo user ──────────────────────────────────────────
if ($CreateDemoUser -and $USER_POOL_ID) {
    Write-Step "Step 3.5: Creating demo user"
    try {
        aws cognito-idp admin-create-user `
            --user-pool-id $USER_POOL_ID `
            --username $DemoUsername `
            --temporary-password $DemoPassword `
            --user-attributes "Name=email,Value=$DemoUsername" "Name=email_verified,Value=true" `
            --message-action SUPPRESS `
            --region $Region 2>$null | Out-Null
        aws cognito-idp admin-set-user-password `
            --user-pool-id $USER_POOL_ID `
            --username $DemoUsername `
            --password $DemoPassword `
            --permanent `
            --region $Region 2>$null | Out-Null
        Write-Ok "Demo user created: $DemoUsername / $DemoPassword"
    } catch { Write-Warn "Demo user may already exist" }
}

# ── Step 4: Generate and upload data ──────────────────────────────
if (-not $SkipData) {
    Write-Step "Step 4: Generating and uploading data"
    python scripts\generate_data.py --output data --profile datacenter
    python scripts\generate_topology.py --output data --profile datacenter 2>$null

    # Upload CSVs
    aws s3 sync data\ "s3://$DATA_BUCKET/" `
        --region $Region --exclude "*" --include "*.csv" --delete

    # Upload topology JSON
    Get-ChildItem data\topology_*.json -ErrorAction SilentlyContinue | ForEach-Object {
        aws s3 cp $_.FullName "s3://$DATA_BUCKET/$($_.Name)" `
            --region $Region --content-type "application/json"
    }

    # Upload branding config
    if (Test-Path "config\default-branding.json") {
        aws s3 cp config\default-branding.json "s3://$DATA_BUCKET/config.json" `
            --region $Region --content-type "application/json"
    }
    Write-Ok "Data uploaded to s3://$DATA_BUCKET"
} else { Write-Warn "Skipping data upload" }

# ── Step 4.5: Memory (requires bash/agentcore CLI) ───────────────
if (-not $SkipMemory) {
    Write-Step "Step 4.5: AgentCore Memory"
    Write-Warn "AgentCore Memory setup requires bash (WSL or Git Bash)."
    Write-Host "  Run in WSL: ./scripts/deploy_memory.sh --region $Region" -ForegroundColor Yellow
} else { Write-Warn "Skipping memory" }

# ── Step 4.6: Knowledge Base ──────────────────────────────────────
if (-not $SkipKb) {
    Write-Step "Step 4.6: Deploying Knowledge Base"

    # Upload KB documents
    if (Test-Path "data\knowledge-base") {
        aws s3 sync data\knowledge-base\ "s3://$DATA_BUCKET/knowledge-base/" `
            --delete --region $Region
        Write-Ok "KB documents uploaded"
    }

    # Check for existing KB
    $KB_NAME = "$StackName-$Env-kb"
    $EXISTING_KB = aws bedrock-agent list-knowledge-bases --region $Region `
        --query "knowledgeBaseSummaries[?name=='$KB_NAME'].knowledgeBaseId" `
        --output text 2>$null

    if ($EXISTING_KB -and $EXISTING_KB -ne "None" -and $EXISTING_KB.Trim()) {
        $KB_ID = $EXISTING_KB.Trim()
        Write-Ok "Found existing KB: $KB_ID"

        # Trigger re-ingestion
        $DS_ID = aws bedrock-agent list-data-sources `
            --knowledge-base-id $KB_ID --region $Region `
            --query "dataSourceSummaries[0].dataSourceId" --output text 2>$null
        if ($DS_ID -and $DS_ID -ne "None") {
            aws bedrock-agent start-ingestion-job `
                --knowledge-base-id $KB_ID --data-source-id $DS_ID `
                --region $Region 2>$null | Out-Null
            Write-Ok "Ingestion started"
        }
    } else {
        Write-Host "  Creating Knowledge Base with S3 Vectors..." -ForegroundColor Blue
        if (-not $KB_ROLE_ARN) {
            $ACCOUNT_ID = aws sts get-caller-identity --query Account --output text
            $KB_ROLE_ARN = "arn:aws:iam::${ACCOUNT_ID}:role/$StackName-$Env-kb-role"
        }

        # Use Python SDK (AWS CLI doesn't support S3_VECTORS type)
        $KB_ID = python scripts\create_kb.py `
            --name $KB_NAME `
            --role-arn $KB_ROLE_ARN `
            --region $Region `
            --bucket $DATA_BUCKET `
            --prefix "knowledge-base/"

        if ($KB_ID) { Write-Ok "Knowledge Base created: $KB_ID" }
        else { Write-Warn "KB creation failed" }
    }
} else { Write-Warn "Skipping Knowledge Base" }

# ── Step 5: MCP Server (requires bash/agentcore CLI) ─────────────
if (-not $SkipMcp) {
    Write-Step "Step 5: MCP Server"
    Write-Warn "MCP server deployment requires bash (WSL or Git Bash)."
    Write-Host "  Run in WSL: ./scripts/deploy_mcp_server.sh --region $Region --stack-name $StackName" -ForegroundColor Yellow
} else { Write-Warn "Skipping MCP server" }

# ── Step 5.5: Supervisor Agent (requires bash/agentcore CLI) ─────
if (-not $SkipAgents) {
    Write-Step "Step 5.5: Supervisor Agent"
    Write-Warn "AgentCore agent deployment requires bash (WSL or Git Bash)."

    $agentCmd = "./scripts/deploy_to_agentcore.sh --agent-name ${StackName}_supervisor --region $Region --data-bucket $DATA_BUCKET --execution-role $AGENTCORE_ROLE --skip-install"
    if ($KB_ID) { $agentCmd += " --kb-id $KB_ID" }

    Write-Host "  Run in WSL:" -ForegroundColor Yellow
    Write-Host "  $agentCmd" -ForegroundColor White
} else { Write-Warn "Skipping agent deployment" }

# ── Step 6: Frontend ──────────────────────────────────────────────
if (-not $SkipFrontend) {
    Write-Step "Step 6: Deploying frontend"

    # Try to find AgentCore ARN from backend/.env
    $AGENT_ARN = ""
    if (Test-Path "backend\.env") {
        $match = Select-String -Path "backend\.env" -Pattern "^AGENTCORE_ARN=(.+)" -ErrorAction SilentlyContinue
        if ($match) { $AGENT_ARN = $match.Matches.Groups[1].Value }
    }

    if ($AGENT_ARN) {
        @"
VITE_AGENTCORE_ARN=$AGENT_ARN
VITE_REGION=$Region
VITE_USER_POOL_ID=$USER_POOL_ID
VITE_USER_POOL_CLIENT_ID=$USER_POOL_CLIENT
VITE_IDENTITY_POOL_ID=$IDENTITY_POOL_ID
VITE_API_GW_ENDPOINT=$API_GW_URL
"@ | Set-Content "frontend\.env" -Encoding UTF8
        Write-Ok "Frontend .env updated with AgentCore config"
    } else {
        Write-Warn "No AgentCore ARN found — deploy agents first via WSL"
    }

    Push-Location frontend
    npm install
    npm run build
    Pop-Location

    if (Test-Path "frontend\dist") {
        aws s3 sync frontend\dist\ "s3://$FRONTEND_BUCKET/" --delete --region $Region
        aws cloudfront create-invalidation `
            --distribution-id $DISTRIBUTION_ID --paths "/*" `
            --region $Region 2>$null | Out-Null
        Write-Ok "Frontend deployed"
    } else {
        Write-Warn "Frontend build failed — check TypeScript errors"
    }
} else { Write-Warn "Skipping frontend" }

# ── Summary ───────────────────────────────────────────────────────
Write-Host @"

============================================
  Deployment Complete!
============================================
  Application URL: $APP_URL
  API Gateway:     $API_GW_URL
  Region:          $Region
  Stack:           $StackName

  NOTE: AgentCore steps (Memory, MCP, Agent)
  require bash. Run in WSL or Git Bash:
    ./deploy.sh --skip-infra --skip-data --skip-kb --skip-frontend
============================================

"@ -ForegroundColor Green

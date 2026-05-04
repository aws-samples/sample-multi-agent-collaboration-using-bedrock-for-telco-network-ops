<#
.SYNOPSIS
    Setup CodePipeline for Network Operations Platform (Windows)

.DESCRIPTION
    Creates a CodePipeline + CodeBuild that pulls from GitHub and runs
    the full deployment. Manual trigger only (no auto-deploy on push).

.EXAMPLE
    $env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxx"
    .\setup-pipeline.ps1 -RepoUrl https://github.com/org/repo

    .\setup-pipeline.ps1 -RepoUrl https://github.com/org/repo -GitHubToken ghp_xxx
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$RepoUrl,
    [string]$Branch = "main",
    [string]$Region = "us-east-1",
    [string]$Project = "netops",
    [string]$GitHubToken = $env:GITHUB_TOKEN
)

$ErrorActionPreference = "Stop"
$StackName = "$Project-pipeline"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $GitHubToken) {
    Write-Host "Error: GitHub token required." -ForegroundColor Red
    Write-Host "Set `$env:GITHUB_TOKEN or use -GitHubToken parameter"
    Write-Host "Create one at: https://github.com/settings/tokens (scopes: repo, admin:repo_hook)"
    exit 1
}

Write-Host @"

============================================
  Network Operations Pipeline Setup
============================================
  Repo:    $RepoUrl
  Branch:  $Branch
  Region:  $Region
  Project: $Project
  Stack:   $StackName
============================================

"@ -ForegroundColor Cyan

# Step 1: Deploy pipeline stack
Write-Host "Step 1: Creating pipeline infrastructure..." -ForegroundColor Cyan

aws cloudformation deploy `
    --template-file "$ScriptDir\pipeline-stack.yaml" `
    --stack-name $StackName `
    --parameter-overrides `
        "ProjectName=$Project" `
        "GitHubRepo=$RepoUrl" `
        "GitHubBranch=$Branch" `
        "GitHubToken=$GitHubToken" `
        "DeployRegion=$Region" `
    --capabilities CAPABILITY_NAMED_IAM `
    --region $Region `
    --no-fail-on-empty-changeset

Write-Host "  [OK] Pipeline infrastructure created" -ForegroundColor Green

# Step 2: Get outputs
$rawOutputs = aws cloudformation describe-stacks `
    --stack-name $StackName --region $Region `
    --query "Stacks[0].Outputs" --output json | ConvertFrom-Json

$PipelineName = ($rawOutputs | Where-Object { $_.OutputKey -eq "PipelineName" }).OutputValue
$PipelineUrl  = ($rawOutputs | Where-Object { $_.OutputKey -eq "PipelineUrl" }).OutputValue

# Step 3: Trigger pipeline
Write-Host "`nStep 2: Triggering first deployment..." -ForegroundColor Cyan
aws codepipeline start-pipeline-execution --name $PipelineName --region $Region 2>$null | Out-Null
Write-Host "  [OK] Pipeline triggered" -ForegroundColor Green

# Summary
Write-Host @"

============================================
  Pipeline Setup Complete!
============================================

  Pipeline: $PipelineName
  Console:  $PipelineUrl

  The deployment is now running in AWS.
  Monitor progress at the URL above.

  Estimated time: 15-20 minutes

  To re-deploy later:
    aws codepipeline start-pipeline-execution --name $PipelineName --region $Region

  To tear down the pipeline:
    aws cloudformation delete-stack --stack-name $StackName --region $Region

============================================

"@ -ForegroundColor Green

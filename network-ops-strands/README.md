# Network Operations Platform (Part 2)

AI-powered network operations monitoring and management platform built with [Strands Agents SDK](https://strandsagents.com/), [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/), and React.

This is Part 2 of the series. Part 1 (Amazon Bedrock Agents) is in the repository root.

## 🚀 Deployment Options

### Option 1: CodePipeline (Recommended — works from any OS)

Deploys everything via AWS CodePipeline + CodeBuild. No local bash/Python/Node required.

```bash
# Set your GitHub token
export GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# Create pipeline and trigger deployment
cd pipeline
./setup-pipeline.sh \
  --repo-url https://github.com/aws-samples/sample-multi-agent-collaboration-using-bedrock-for-telco-network-ops \
  --branch feature/strands-migration
```

On Windows PowerShell:
```powershell
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxx"
.\pipeline\setup-pipeline.ps1 `
  -RepoUrl https://github.com/aws-samples/sample-multi-agent-collaboration-using-bedrock-for-telco-network-ops `
  -Branch feature/strands-migration
```

Monitor progress in the [CodePipeline console](https://console.aws.amazon.com/codesuite/codepipeline/pipelines). Deployment takes ~15-20 minutes.

To re-deploy:
```bash
aws codepipeline start-pipeline-execution --name netops-pipeline --region us-east-1
```

### Option 2: Local Deploy (Linux/macOS)

```bash
# Full deployment
./deploy.sh --create-demo-user

# Skip specific steps
./deploy.sh --skip-kb --skip-mcp
```

### Option 3: Local Deploy (Windows PowerShell)

```powershell
# Infrastructure, data, KB, frontend (native PowerShell)
.\deploy.ps1 -CreateDemoUser

# Agent deployment requires WSL/Git Bash (agentcore CLI)
wsl ./deploy.sh --skip-infra --skip-data --skip-kb --skip-frontend
```

### Option 4: Local Development

```bash
./setup.sh          # First time only
./start-local.sh    # Start backend + frontend
```
- Backend: http://localhost:8000
- Frontend: http://localhost:3000

## 📋 Prerequisites

- AWS CLI configured (`aws configure`)
- Access to Amazon Bedrock models (Claude Sonnet, Nova Lite) in us-east-1
- For local deploy: Python 3.10+, Node.js 18+, AWS SAM CLI, Docker
- For pipeline deploy: Only AWS CLI + GitHub token

## 🏗️ Architecture

```
React Frontend → CloudFront → Lambda@Edge (JWT Auth)
                                    ↓
                            AgentCore Runtime
                                    ↓
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓
            Maintenance Agent  Alarm Agent    KPI Agent
            (Nova Lite)        (Nova Lite)    (Nova Lite)
                    ↓               ↓               ↓
                            S3 Data (CSV)
                                    
Supervisor Agent (Claude Sonnet) also connects to:
  → MCP Server (weather, power outages, 811 dig requests)
  → Bedrock Knowledge Base (troubleshooting articles, past tickets)
  → AgentCore Memory (conversation persistence)
```

### Key Components

| Component | Technology | Purpose |
|---|---|---|
| Supervisor Agent | Claude Sonnet + Extended Thinking | Query routing, complex reasoning |
| Sub-Agents (3) | Amazon Nova Lite | Maintenance, Alarms, KPIs |
| MCP Server | AgentCore Runtime | External context (weather, power, 811) |
| Knowledge Base | Bedrock KB + S3 Vectors | RAG — troubleshooting articles + past tickets |
| Memory | AgentCore Memory | Conversation persistence (STM + LTM) |
| Frontend | React + TypeScript + Tailwind | Chat, dashboard, topology, charts |
| Auth | Cognito + Lambda@Edge | JWT-based, per-user session isolation |
| Infra | SAM/CloudFormation | S3, CloudFront, Cognito, IAM, API Gateway |

## 💡 Example Queries

### Alarms & Maintenance
- `Show all critical alarms`
- `Check maintenance for site_atlanta_001`
- `Which sites have both active alarms and scheduled maintenance?`

### Performance & Charts
- `Analyze performance for site_dallas_003`
- `Plot a bar chart comparing throughput across all Dallas and Atlanta sites`
- `Are there any anomalies in the network performance today?`

### Knowledge Base (RAG)
- `How do I recover a site after a power outage?`
- `Has there been a fiber cut incident before? What was the resolution?`
- `Search the knowledge base for HVAC failure procedures`

### External Context (MCP)
- `What is the weather in Dallas?`
- `Site_dallas_003 has a SITE_DOWN alarm. Check for external factors.`
- `Check power outages and 811 dig requests near site_richmond_008`

### Multi-Turn
- `Give me a full report on site_dallas_003`
- `Compare that with site_atlanta_001` (follow-up)

## 📁 Project Structure

```
network-ops-strands/
├── deploy.sh / deploy.ps1     # Deployment scripts
├── delete.sh                  # Cleanup script
├── start-local.sh             # Local development
├── template.yaml              # SAM master template
├── pipeline/                  # CodePipeline deployment
│   ├── setup-pipeline.sh/ps1  # Create pipeline
│   ├── pipeline-stack.yaml    # Pipeline CloudFormation
│   └── buildspec.yml          # CodeBuild instructions
├── frontend/                  # React application
├── backend/                   # Strands agents
│   ├── strands_agents/        # Agent implementations
│   ├── tools/                 # Agent tools (S3 data access)
│   └── memory_hook.py         # AgentCore Memory integration
├── mcp-server/                # External context MCP server
├── infrastructure/            # CloudFormation templates
├── scripts/                   # Deploy helper scripts
├── config/                    # Whitelabel branding
├── knowledge-base/            # KB source documents (articles + tickets)
├── DEMO_SCRIPT.md             # Demo storyboard
└── BLOG_DRAFT.md              # Blog post draft
```

## 🔐 Demo Credentials

After deploying with `--create-demo-user`:
- Username: `netopsuser@example.com`
- Password: `NetworkOps2026!`

## 🗑️ Cleanup

```bash
# Delete application stack
./delete.sh

# Delete pipeline (if used)
aws cloudformation delete-stack --stack-name netops-pipeline --region us-east-1
```

## 📚 Related

- [Part 1 Blog: Multi-agent collaboration using Amazon Bedrock](https://aws.amazon.com/blogs/industries/multi-agent-collaboration-using-amazon-bedrock-for-telecom-network-operations/)
- [Strands Agents SDK](https://strandsagents.com/)
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)

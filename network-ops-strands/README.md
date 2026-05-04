# Network Operations Platform

AI-powered network operations monitoring and management platform built with AWS AgentCore, Strands Agents, and React.

## 🚀 Quick Start

### Local Development (Recommended for Testing)

```bash
# 1. Run setup (first time only)
./setup.sh

# 2. Start local development servers
./start-local.sh
```

This will:
- Start backend API server with Strands agents on http://localhost:8000
- Start frontend React dev server on http://localhost:3000
- Use AWS Bedrock for AI models (requires AWS credentials)

### AWS Deployment (Production)

```bash
# First time deployment (interactive)
./deploy.sh --guided

# Subsequent deployments
./deploy.sh

# Deploy with demo user
./deploy.sh --create-demo-user
```

### Create Demo User After Deployment

```bash
# Create demo user with default credentials
./deploy.sh --create-demo-user --skip-agents --skip-frontend

# Create demo user with custom credentials
./deploy.sh --create-demo-user \
  --demo-username admin@example.com \
  --demo-password "MySecurePass123!" \
  --skip-agents --skip-frontend
```

**Default Demo User**:
- Username: `netopsuser@example.com`
- Password: `NetworkOps2024!`

### Delete Everything (One Command)

```bash
./delete.sh
```

## 📋 Prerequisites

### For Local Development
- Python 3.10+
- Node.js 18+ and npm
- AWS CLI configured with valid credentials (`aws configure`)
- Access to AWS Bedrock (for AI models)

### For AWS Deployment
- All local development prerequisites
- AWS SAM CLI installed ([installation guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html))
- jq (for JSON parsing)

## 🏗️ Architecture

```
Frontend (React) → CloudFront → Lambda@Edge (Auth) → AgentCore Runtime
                                                            ↓
                                                    Strands Agents
                                                            ↓
                                                    S3 Data (CSV files)
```

### Components

- **Frontend**: React + TypeScript + Tailwind CSS (hosted on S3 for production, localhost:3000 for dev)
- **Backend**: Strands Agents with AWS Bedrock models
  - Supervisor Agent (Claude 4.5 Sonnet) - query routing
  - Maintenance Agent (Nova 2 Lite) - maintenance schedules
  - Alarm Agent (Nova 2 Lite) - network alarms
  - KPI Agent (Claude 4.5 Haiku) - performance metrics
- **CDN**: CloudFront with Lambda@Edge JWT validation (production only)
- **Authentication**: AWS Cognito (User Pool + Identity Pool) (production only)
- **Data**: CSV files (local for dev, S3 for production)

## 💡 Example Queries

Once the application is running, try these queries in the chat interface:

### Site Information
- "Check maintenance for site_atlanta_001"
- "What's the status of site_dallas_003?"
- "Show me all sites in Birmingham"

### Maintenance Queries
- "Show upcoming maintenance for site_dallas_002"
- "Is there any ongoing maintenance at site_atlanta_001?"
- "When is the next scheduled maintenance?"

### Alarm Queries
- "Show all critical alarms"
- "Are there any active alarms for site_birmingham_003?"
- "What alarms are affecting site_ridgeland_005?"

### Performance Queries
- "Analyze performance for site_dallas_003"
- "Show me KPI metrics for site_atlanta_001"
- "Are there any performance anomalies?"

### Complex Queries
- "Give me a full report on site_dallas_001"
- "Which sites have both active alarms and scheduled maintenance?"

## 📊 Data

The platform uses synthetic data for demonstration:

### Locations (4 total)
- Dallas, TX
- Birmingham, AL
- Atlanta, GA
- Ridgeland, MS

### Sites
- 5 sites per location (20 total)
- Site ID format: `site_{location}_{number}`
- Types: macro, micro, small
- Vendors: Ericsson, Nokia, Huawei

### Data Files (in `data/` directory)
- `sites.csv` - Site information
- `maintenance_schedule.csv` - Maintenance windows
- `alarms.csv` - Network alarms
- `kpi_metrics.csv` - Performance metrics (48 hours of hourly data)

### Regenerate Data

```bash
source backend/venv/bin/activate
python scripts/generate_data.py --sites 20 --profile qts --output data
```

## 📦 What Gets Deployed (AWS)

### Infrastructure (via SAM)
- ✅ S3 buckets (frontend, data, config)
- ✅ Cognito User Pool and Identity Pool
- ✅ IAM roles for AgentCore
- ✅ Lambda@Edge JWT authorizer
- ✅ CloudFront distribution

### Application
- ✅ Strands agents to AgentCore Runtime
- ✅ React frontend to S3
- ✅ Sample data to S3

## 🛠️ Deployment Options

### Full Deployment

```bash
./deploy.sh
```

### Skip Components

```bash
# Skip agent deployment
./deploy.sh --skip-agents

# Skip frontend deployment
./deploy.sh --skip-frontend
```

### Custom Configuration

```bash
# Deploy to production
./deploy.sh --stack-name netops-prod --region us-east-1

# Deploy to different region
./deploy.sh --region eu-west-1
```

## 🔧 Local Development

### Initial Setup

```bash
./setup.sh
```

This will:
- Create Python virtual environment in `backend/venv`
- Install Python dependencies (Strands, boto3, etc.)
- Install Node.js dependencies in `frontend/node_modules`
- Generate synthetic data in `data/` directory
- Create `.env` files from examples

### Start Development Servers

```bash
./start-local.sh
```

This will:
- Check AWS credentials (required for Bedrock)
- Start backend API server on http://localhost:8000
- Start frontend dev server on http://localhost:3000
- Display your AWS account info
- Show example queries to try

**Note**: Press Ctrl+C to stop both servers

### Manual Start (Alternative)

If you prefer to start servers separately:

```bash
# Terminal 1: Backend
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
python api_server.py

# Terminal 2: Frontend
cd frontend
npm run dev
```

### Test Individual Agents

```bash
# Activate virtual environment
source backend/venv/bin/activate

# Test agents directly
python backend/strands_agents/maintenance_agent.py
python backend/strands_agents/alarm_agent.py
python backend/strands_agents/kpi_agent.py
```

## 📚 Documentation

- **README.md** - This file (project overview and quick start)
- **DEPLOYMENT_COMPLETE.md** - Detailed deployment guide
- **QUICK_REFERENCE.md** - Quick command reference
- **MCP_INTEGRATION_GUIDE.md** - MCP server and Knowledge Base integration
- **MCP_AND_KB_SUMMARY.md** - MCP capabilities and benefits overview
- **AGENTCORE_AUTH_ARCHITECTURE.md** - Authentication architecture
- **LAMBDA_EDGE_AUTH.md** - Lambda@Edge setup guide
- **DEMO_USER_FEATURE.md** - Demo user creation guide

## 🔐 Authentication

### Demo User Creation

The deployment script can automatically create a demo user:

```bash
# Create demo user during deployment
./deploy.sh --create-demo-user

# Create demo user after deployment (skip other steps)
./deploy.sh --create-demo-user --skip-agents --skip-frontend

# Custom demo user credentials
./deploy.sh --create-demo-user \
  --demo-username myuser@example.com \
  --demo-password "MyPassword123!"
```

**Default credentials**:
- Username: `netopsuser@example.com`
- Password: `NetworkOps2024!`

### Manual User Management

```bash
# Create Cognito user
aws cognito-idp admin-create-user \
  --user-pool-id <USER_POOL_ID> \
  --username user@example.com \
  --user-attributes Name=email,Value=user@example.com

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id <USER_POOL_ID> \
  --username user@example.com \
  --password <PASSWORD> \
  --permanent
```

### Authentication Flow

1. User logs in via Cognito
2. Frontend receives JWT tokens
3. CloudFront Lambda@Edge validates tokens
4. Valid requests forwarded to AgentCore
5. Agents process queries and return responses

## 📊 Monitoring

### CloudWatch Logs

```bash
# View agent logs
aws logs tail /aws/agentcore/<agent-name> --follow

# View Lambda@Edge logs
aws logs tail /aws/lambda/us-east-1.<function-name> --follow
```

### Stack Outputs

```bash
# View all outputs
aws cloudformation describe-stacks \
  --stack-name netops \
  --query 'Stacks[0].Outputs'
```

## 🧪 Testing

### Test Authentication

```bash
# Access protected page (should redirect to login)
curl -I https://<cloudfront-url>/

# Access public page (should work)
curl -I https://<cloudfront-url>/login
```

### Test Agents

```bash
# Invoke agent via AgentCore CLI
agentcore invoke "Show me critical alarms" \
  --agent supervisor \
  --user-id test-user \
  --session-id test-session-12345678901234567890123456789012
```

## 🗑️ Cleanup

### Delete Stack

```bash
# With confirmation
./delete.sh

# Force delete (no prompts)
./delete.sh --force
```

### Manual Cleanup

```bash
# Delete SAM stack
sam delete --stack-name netops

# Empty S3 buckets first
aws s3 rm s3://<bucket-name> --recursive
```

## 📁 Project Structure

```
network-ops-strands/
├── template.yaml              # SAM master template
├── samconfig.toml            # SAM configuration
├── deploy.sh                 # Unified deployment script
├── delete.sh                 # Unified deletion script
│
├── frontend/                 # React application
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── services/        # API services
│   │   └── contexts/        # React contexts
│   └── package.json
│
├── backend/                  # Strands agents
│   ├── strands_agents/      # Agent implementations
│   ├── tools/               # Agent tools
│   └── requirements.txt
│
├── infrastructure/
│   ├── cloudformation/      # Nested stack templates
│   │   ├── s3-buckets.yaml
│   │   ├── cognito.yaml
│   │   ├── iam-roles.yaml
│   │   ├── lambda-edge.yaml
│   │   └── cloudfront.yaml
│   └── lambda-edge/         # Lambda@Edge function
│
└── scripts/                 # Deployment scripts
    ├── upload_data.sh
    ├── deploy_agentcore.sh
    └── deploy_frontend.sh
```

## 🎯 Key Features

- ✅ **One-Command Deployment** - Deploy entire stack with `./deploy.sh`
- ✅ **Serverless Architecture** - Auto-scaling with AgentCore Runtime
- ✅ **Multi-Agent System** - Specialized agents for different domains
- ✅ **Real-Time Streaming** - Token-by-token response streaming
- ✅ **JWT Authentication** - Secure authentication at CloudFront edge
- ✅ **Whitelabel Support** - Runtime-configurable branding
- ✅ **Dark Mode** - Professional UI with dark/light themes
- ✅ **External Context MCP Server** - Check power outages, 811 dig requests, weather
- ✅ **Knowledge Base Integration** - Troubleshooting articles and historical tickets

## 🔗 Useful Links

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/)
- [Strands Agents Documentation](https://strandsagents.com/)
- [React Documentation](https://react.dev/)

## 📝 License

MIT License - See LICENSE file for details

## 🤝 Support

For issues or questions:
1. Check documentation in `DEPLOYMENT_COMPLETE.md`
2. Review CloudWatch logs
3. Check stack outputs for configuration values

---

**Ready to deploy?** Run `./deploy.sh --guided` to get started! 🚀

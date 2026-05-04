# Quick Reference Guide

## 🚀 Deployment Commands

### One-Command Deployment

```bash
# Interactive deployment (first time)
./deploy.sh --guided

# Deploy with defaults
./deploy.sh

# Deploy with demo user
./deploy.sh --create-demo-user

# Deploy to production
./deploy.sh --stack-name netops-prod --region us-east-1
```

### Demo User Creation

```bash
# Create demo user during deployment
./deploy.sh --create-demo-user

# Create demo user after deployment (skip other steps)
./deploy.sh --create-demo-user --skip-agents --skip-frontend

# Custom demo user credentials
./deploy.sh --create-demo-user \
  --demo-username admin@example.com \
  --demo-password "SecurePass123!"
```

**Default Demo User**:
- Username: `netopsuser@example.com`
- Password: `NetworkOps2024!`

### Partial Deployment

```bash
# Skip agent deployment
./deploy.sh --skip-agents

# Skip frontend deployment
./deploy.sh --skip-frontend

# Update infrastructure only
sam deploy --stack-name netops
```

### Cleanup

```bash
# Delete everything (with confirmation)
./delete.sh

# Force delete (no prompts)
./delete.sh --force

# Delete specific stack
./delete.sh --stack-name netops-prod
```

## 📊 Stack Management

### View Outputs

```bash
# All outputs
aws cloudformation describe-stacks \
  --stack-name netops \
  --query 'Stacks[0].Outputs'

# Specific output
aws cloudformation describe-stacks \
  --stack-name netops \
  --query 'Stacks[0].Outputs[?OutputKey==`ApplicationURL`].OutputValue' \
  --output text
```

### Update Stack

```bash
# Update with new parameters
sam deploy --stack-name netops \
  --parameter-overrides \
    Environment=prod \
    EnableJWTAuthorizer=true
```

## 🔐 User Management

### Create Cognito User

```bash
# Get User Pool ID
USER_POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name netops \
  --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
  --output text)

# Create user
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username user@example.com \
  --user-attributes Name=email,Value=user@example.com \
  --message-action SUPPRESS

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username user@example.com \
  --password "YourPassword123!" \
  --permanent
```

### Delete User

```bash
aws cognito-idp admin-delete-user \
  --user-pool-id $USER_POOL_ID \
  --username user@example.com
```

## 🤖 AgentCore Management

### Deploy Agents

```bash
cd backend
agentcore configure -e strands_agents/supervisor_agent.py
agentcore deploy
```

### Invoke Agent

```bash
agentcore invoke "Show me critical alarms" \
  --agent supervisor \
  --user-id test-user \
  --session-id test-session-12345678901234567890123456789012
```

### View Agent Logs

```bash
# Tail logs
aws logs tail /aws/agentcore/supervisor --follow

# Get log groups
aws logs describe-log-groups \
  --log-group-name-prefix "/aws/agentcore"
```

## 🎨 Frontend Management

### Local Development

```bash
cd frontend
npm install
npm run dev
# Access at http://localhost:3000
```

### Deploy Frontend

```bash
# Build
cd frontend
npm run build

# Deploy to S3
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name netops \
  --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' \
  --output text)

aws s3 sync dist/ s3://$BUCKET/ --delete

# Invalidate CloudFront cache
DIST_ID=$(aws cloudformation describe-stacks \
  --stack-name netops \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
  --output text)

aws cloudfront create-invalidation \
  --distribution-id $DIST_ID \
  --paths "/*"
```

## 📦 Data Management

### Upload Data

```bash
# Generate sample data
python scripts/generate_data.py --sites 20 --profile qts

# Upload to S3
DATA_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name netops \
  --query 'Stacks[0].Outputs[?OutputKey==`DataBucketName`].OutputValue' \
  --output text)

aws s3 sync data/ s3://$DATA_BUCKET/ --exclude "*.md"
```

### Download Data

```bash
aws s3 sync s3://$DATA_BUCKET/ data/ --exclude "*.md"
```

## 🔍 Monitoring & Debugging

### CloudWatch Logs

```bash
# Agent logs
aws logs tail /aws/agentcore/supervisor --follow

# Lambda@Edge logs (check all regions)
aws logs tail /aws/lambda/us-east-1.netops-dev-jwt-authorizer --follow

# CloudFront logs
aws s3 ls s3://netops-dev-cloudfront-logs-123456789/
```

### CloudWatch Metrics

```bash
# Get agent invocation count
aws cloudwatch get-metric-statistics \
  --namespace AWS/AgentCore \
  --metric-name Invocations \
  --dimensions Name=AgentName,Value=supervisor \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Sum
```

### Test Authentication

```bash
# Get CloudFront URL
APP_URL=$(aws cloudformation describe-stacks \
  --stack-name netops \
  --query 'Stacks[0].Outputs[?OutputKey==`ApplicationURL`].OutputValue' \
  --output text)

# Test public page (should work)
curl -I $APP_URL/login

# Test protected page (should redirect or return 401)
curl -I $APP_URL/
```

## 🛠️ SAM CLI Commands

```bash
# Validate template
sam validate --lint

# Build application
sam build

# Deploy (interactive)
sam deploy --guided

# Deploy (saved config)
sam deploy

# Delete stack
sam delete --stack-name netops

# View logs
sam logs --stack-name netops

# Sync changes (fast)
sam sync --stack-name netops --watch
```

## 📝 Configuration Files

- **template.yaml** - SAM master template
- **samconfig.toml** - SAM configuration
- **infrastructure/cloudformation/** - Nested stack templates
- **config/qts-branding.json** - Whitelabel configuration

## 🔗 Useful URLs

### Local Development
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### AWS Console
- CloudFormation: https://console.aws.amazon.com/cloudformation
- Cognito: https://console.aws.amazon.com/cognito
- CloudFront: https://console.aws.amazon.com/cloudfront
- S3: https://console.aws.amazon.com/s3
- CloudWatch: https://console.aws.amazon.com/cloudwatch

## 🆘 Troubleshooting

### Deployment Failed

```bash
# Check CloudFormation events
aws cloudformation describe-stack-events \
  --stack-name netops \
  --max-items 20

# Check nested stack status
aws cloudformation list-stacks \
  --stack-status-filter CREATE_FAILED UPDATE_FAILED
```

### Lambda@Edge Not Working

```bash
# Check function version
aws lambda list-versions-by-function \
  --function-name netops-dev-jwt-authorizer \
  --region us-east-1

# Check CloudFront association
aws cloudfront get-distribution-config \
  --id $DIST_ID \
  | jq '.DistributionConfig.DefaultCacheBehavior.LambdaFunctionAssociations'
```

### Agent Not Responding

```bash
# Check agent status
agentcore list

# View recent logs
aws logs tail /aws/agentcore/supervisor --since 10m

# Test agent locally
cd backend
python -c "from strands_agents.supervisor_agent import create_supervisor_agent; agent = create_supervisor_agent(); print(agent('test'))"
```

## 📚 Documentation

- **README.md** - Main documentation
- **DEPLOYMENT_COMPLETE.md** - Detailed deployment guide
- **AGENTCORE_AUTH_ARCHITECTURE.md** - Authentication architecture
- **LAMBDA_EDGE_AUTH.md** - Lambda@Edge setup

---

**Need help?** Check the full documentation in `README.md` or `DEPLOYMENT_COMPLETE.md`

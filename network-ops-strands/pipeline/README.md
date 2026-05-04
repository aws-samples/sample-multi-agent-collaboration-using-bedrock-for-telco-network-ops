# CodePipeline Deployment

One-command deployment using AWS CodePipeline + CodeBuild.
Works from any OS (Windows, macOS, Linux) — all build/deploy runs in AWS.

## Usage

```bash
# Set your GitHub repo URL and a personal access token
export GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# Create pipeline and trigger first deployment
./setup-pipeline.sh --repo-url https://github.com/your-org/your-repo

# Or on Windows
.\setup-pipeline.ps1 -RepoUrl https://github.com/your-org/your-repo -GitHubToken ghp_xxxx
```

## What it creates

- CodeBuild project (Linux container with Python, Node, SAM, AgentCore CLI)
- CodePipeline (manual trigger — no auto-deploy on push)
- S3 artifact bucket
- IAM roles for CodeBuild and CodePipeline
- GitHub source connection

## Re-running

To trigger a new deployment without recreating the pipeline:

```bash
aws codepipeline start-pipeline-execution --name netops-pipeline --region us-east-1
```

## Cleanup

```bash
./teardown-pipeline.sh
```

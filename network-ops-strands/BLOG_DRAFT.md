# Building a Network Operations Assistant using Strands Agents SDK and Amazon Bedrock AgentCore

*This is Part 2 of our series on AI-powered network operations. In [Part 1](https://aws.amazon.com/blogs/industries/multi-agent-collaboration-using-amazon-bedrock-for-telecom-network-operations/), we built a Network Operations Assistant using Amazon Bedrock's fully managed multi-agent collaboration. In this post, we take a different approach—rebuilding the solution using the open-source [Strands Agents SDK](https://strandsagents.com/) and [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/), gaining greater control over agent behavior while adding new capabilities like conversation memory, knowledge base search, external context integration via MCP, and a modern React frontend.*

## Introduction

In Part 1, we demonstrated how Amazon Bedrock Agents can orchestrate specialized AI agents for network operations—routing queries to maintenance, alarm, and KPI agents through a supervisor pattern. The fully managed approach handled orchestration, task delegation, and inter-agent communication automatically.

However, production network operations teams often need more control: custom streaming behavior, fine-grained tool orchestration, integration with external data sources via the Model Context Protocol (MCP), and conversation persistence across sessions. This is where the Strands Agents SDK and Amazon Bedrock AgentCore come in.

In this post, we rebuild the Network Operations Assistant with several enhancements:

- **Strands Agents SDK** for flexible, code-first agent development with full control over the agent loop
- **Amazon Bedrock AgentCore Runtime** for serverless, auto-scaling agent deployment
- **AgentCore Memory** for conversation persistence across sessions (short-term and long-term)
- **Amazon Bedrock Knowledge Bases with S3 Vectors** for RAG-powered troubleshooting guidance with source citations
- **MCP integration** for real-time external context (weather, power outages, excavation activity)
- **Modern React frontend** with TypeScript, Tailwind CSS, streaming responses, and interactive charts
- **Cognito authentication** with per-user session isolation

## Architecture overview

The new architecture replaces the Bedrock Agents managed orchestration with Strands Agents running on AgentCore Runtime, while preserving the proven multi-agent supervisor pattern from Part 1.

<!-- [Figure 1: Insert architecture diagram showing: React Frontend → CloudFront → Lambda@Edge → AgentCore Runtime (Supervisor Agent) → Sub-agents + MCP + KB + Memory] -->
**Figure 1: Architecture — Strands Agents on AgentCore Runtime**

The key components are:

1. **Frontend**: React application with TypeScript and Tailwind CSS, deployed to S3 and served via CloudFront with Lambda@Edge authentication
2. **Agent Runtime**: Strands Agents deployed on AgentCore Runtime (serverless, auto-scaling)
3. **Supervisor Agent**: Powered by Claude Sonnet with extended thinking, orchestrates three specialized agents
4. **Specialized Agents**: Maintenance, Alarm, and KPI agents running on Amazon Nova Lite for cost efficiency
5. **MCP Server**: External context tools deployed on AgentCore, providing real-time weather data, power outage checks, and 811 dig request monitoring
6. **Knowledge Base**: Amazon Bedrock Knowledge Base with S3 Vectors for troubleshooting articles and historical incident tickets
7. **Memory**: AgentCore Memory for conversation persistence (STM for within-session, LTM for cross-session)
8. **Data Layer**: CSV files on S3 for sites, maintenance schedules, alarms, and KPI metrics

## Why Strands Agents SDK?

The Strands Agents SDK is an open-source framework that provides a model-driven approach to building AI agents. Unlike fully managed orchestration, Strands gives developers direct control over:

- **The agent loop**: Custom streaming, event handling, and error recovery
- **Tool definitions**: Python functions decorated with `@tool` become agent capabilities
- **Multi-agent patterns**: Agents-as-tools, where sub-agents are invoked as tool calls by the supervisor
- **Hook system**: Lifecycle hooks for monitoring, memory persistence, and custom behavior
- **Model flexibility**: Switch between Bedrock models (Claude, Nova) with a single configuration change

Here is how we define a specialized agent using Strands:

```python
from strands import Agent, tool
from strands.models import BedrockModel

@tool
def check_site_maintenance(site_id: str) -> str:
    """Check maintenance schedule for a specific network site."""
    data_loader = S3DataLoader(bucket_name=os.getenv("DATA_BUCKET_NAME"))
    schedule = data_loader.load_csv("maintenance_schedule.csv")
    # Filter by site_id, separate active vs upcoming, format response
    return formatted_result

def create_maintenance_agent() -> Agent:
    model = BedrockModel(model_id="us.amazon.nova-lite-v1:0")
    return Agent(
        model=model,
        system_prompt="You are a maintenance schedule specialist...",
        tools=[check_site_maintenance],
    )
```

The supervisor agent uses the agents-as-tools pattern, where each specialized agent is registered as a tool that the supervisor can invoke:

```python
@tool
async def maintenance_agent(query: str):
    """Get maintenance info: schedules, ongoing work, planned outages."""
    agent = create_maintenance_agent()
    async for event in agent.stream_async(query):
        yield SubAgentEvent(agent_name="maintenance_agent", event=event)
        if "result" in event:
            result = event["result"]
    yield str(result.message if result else "No response")

def create_supervisor_agent() -> Agent:
    model = BedrockModel(
        model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        additional_model_request_fields={
            "thinking": {"type": "enabled", "budget_tokens": 2048}
        }
    )
    return Agent(
        model=model,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        tools=[maintenance_agent, alarm_agent, kpi_agent,
               search_knowledge_base],
        hooks=[memory_hook],
    )
```

## Deploying to AgentCore Runtime

Amazon Bedrock AgentCore Runtime provides serverless infrastructure for running Strands agents in production. The agent code is packaged and deployed using the AgentCore CLI:

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

@app.entrypoint
async def agent_invocation(payload, context):
    """Streaming entrypoint — yields SSE events for real-time UI."""
    session_id = getattr(context, "session_id", "default")
    user_message = payload.get("prompt", "Hello")
    actor_id = payload.get("actor_id", session_id)

    supervisor = get_supervisor()
    supervisor._netops_session_id = session_id
    supervisor._netops_actor_id = actor_id

    async for event in supervisor.stream_async(user_message):
        if event.get("reasoning"):
            yield {"type": "thinking", "content": event["reasoningText"]}
        elif "data" in event:
            yield {"type": "token", "content": event["data"]}
        elif "result" in event:
            yield {"type": "done"}
```

Deployment is a single command:

```bash
agentcore launch --agent netops_supervisor \
  --env DATA_BUCKET_NAME=$BUCKET \
  --env MEMORY_ID=$MEMORY_ID \
  --env KNOWLEDGE_BASE_ID=$KB_ID
```

AgentCore handles container packaging, scaling, and session management automatically.

## Conversation memory with AgentCore Memory

One limitation of the Part 1 implementation was that conversations were stateless—each session started fresh. In the new implementation, we use AgentCore Memory to persist conversations using the Strands hooks system:

```python
from strands.hooks import HookProvider, HookRegistry, MessageAddedEvent
from bedrock_agentcore.memory.session import MemorySessionManager
from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole

class AgentCoreMemoryHook(HookProvider):
    def on_message_added(self, event: MessageAddedEvent):
        """Save each message to AgentCore Memory."""
        session_id = getattr(event.agent, "_netops_session_id", "default")
        actor_id = getattr(event.agent, "_netops_actor_id", "user")

        mgr = MemorySessionManager(memory_id=self.memory_id, region_name=self.region)
        session = mgr.create_memory_session(actor_id=actor_id, session_id=session_id)

        msg = event.agent.messages[-1]
        content = extract_text(msg)
        role = MessageRole.ASSISTANT if msg["role"] == "assistant" else MessageRole.USER
        session.add_turns(messages=[ConversationalMessage(content, role)])

    def register_hooks(self, registry: HookRegistry):
        registry.add_callback(MessageAddedEvent, self.on_message_added)
```

This enables:
- **Session persistence**: Users can close the browser and return to their conversation
- **Session history**: A sidebar shows all past sessions, which users can switch between or delete
- **Per-user isolation**: Each Cognito user has their own actor ID, so sessions are private

<!-- [Figure 2: Insert screenshot showing the session sidebar with multiple chat sessions] -->
**Figure 2: Session management — users can switch between and delete past conversations**

## Knowledge Base with S3 Vectors

Part 1 mentioned knowledge base integration as a future enhancement. In this implementation, we built it using Amazon Bedrock Knowledge Bases with S3 Vectors—a cost-effective vector storage option that eliminates the need for a separate OpenSearch cluster.

The knowledge base contains two types of documents:
- **Troubleshooting articles**: Power outage recovery, site down diagnosis, high latency resolution, fiber cut response, HVAC failure procedures, network congestion management
- **Historical incident tickets**: Past incidents with timelines, root causes, resolution steps, and lessons learned

The supervisor agent has a `search_knowledge_base` tool that queries the KB using semantic vector search and returns results with source citations:

```python
@tool
def search_knowledge_base(query: str) -> str:
    """Search troubleshooting articles and past incident tickets.
    IMPORTANT: Always include source citations in your response."""
    client = boto3.client("bedrock-agent-runtime")
    response = client.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": 5}
        },
    )
    results = []
    sources = []
    for i, item in enumerate(response["retrievalResults"], 1):
        text = item["content"]["text"]
        source = item["location"]["s3Location"]["uri"].split("/")[-1]
        score = item["score"]
        results.append(f"**[Source {i}: {source}]** (relevance: {score:.0%})\n{text}")
        sources.append(f"[{i}] {source}")

    return "\n\n".join(results) + "\n\n📚 Sources:\n" + "\n".join(sources)
```

When an engineer asks "How do I recover a site after a power outage?", the agent retrieves the relevant article with source citations, grounding its response in documented procedures rather than generating potentially inaccurate steps.

<!-- [Figure 3: Insert screenshot showing a KB query response with source citations, e.g., "How do I recover a site after a power outage?"] -->
**Figure 3: Knowledge Base search with source citations — responses grounded in documented procedures**

**Demo query for screenshot**: `How do I recover a site after a power outage?`

<!-- [Figure 4: Insert screenshot showing a past incident search, e.g., "Has there been a fiber cut incident before? What was the resolution?"] -->
**Figure 4: Historical incident search — finding similar past tickets with resolution details**

**Demo query for screenshot**: `Has there been a fiber cut incident before? What was the resolution?`

## External context via MCP

The Model Context Protocol (MCP) enables agents to access external data sources through a standardized interface. We deploy an MCP server on AgentCore that provides three tools for correlating network issues with external factors:

### Real-time weather data

The `get_real_weather` tool fetches live weather conditions from the Open-Meteo API. Given a city name or site ID, it returns current temperature, humidity, wind speed, and a 3-day forecast. This is a live API integration—the agent gets real weather data for any location.

When a site experiences performance degradation, the agent can check whether severe weather (storms, extreme heat) might be contributing to the issue.

### Power outage monitoring

The `check_power_outages` tool checks for utility power outages near a network site. In this implementation, it uses simulated data that mirrors the format of real utility company APIs (such as Oncor Electric, Dominion Energy, or Duke Energy). Each utility company typically exposes outage data through public APIs or outage maps that return affected areas, customer counts, estimated restoration times, and cause descriptions.

In a production deployment, this tool would integrate directly with utility company APIs or MCP servers that utility companies expose. Many utilities already provide REST APIs for outage data, and as MCP adoption grows, utilities may expose their outage data as MCP tools that agents can discover and use directly.

### Excavation activity (811 dig requests)

The `check_811_dig_requests` tool monitors for excavation activity near network sites that could damage buried fiber optic cables. The "Call Before You Dig" (811) system is a national program in the United States where contractors must file permits before excavating. In this implementation, the tool uses simulated data that mirrors the format of real 811 databases.

In production, this tool would integrate with state-level 811 databases or the national 811 system APIs. Some states expose dig request data through REST APIs, and organizations like the Common Ground Alliance maintain databases that could be accessed via MCP. When a site experiences a connectivity loss, the agent can check whether nearby excavation activity might have damaged fiber—a common cause of outages that is often missed in initial troubleshooting.

### Root cause analysis in action

When an engineer reports a site down alarm, the supervisor automatically correlates internal data with these external factors:

<!-- [Figure 5: Insert screenshot showing root cause analysis with MCP tools, e.g., "Site_dallas_003 has a SITE_DOWN alarm. Can you check for external factors?"] -->
**Figure 5: Root cause analysis — the agent correlates alarms with weather, power outages, and excavation activity**

**Demo query for screenshot**: `Site_dallas_003 has a SITE_DOWN alarm. Can you check for external factors that might explain the outage?`

## Modern React frontend

The Part 1 implementation used Streamlit deployed on Fargate. The new frontend is a React application with TypeScript and Tailwind CSS, deployed as static files to S3 with CloudFront—eliminating container management entirely.

<!-- [Figure 6: Insert screenshot of the Dashboard view showing metric cards (Active Alarms, Ongoing Maintenance, Sites Monitored, Avg Latency) and Quick Actions] -->
**Figure 6: Dashboard with live metrics and quick action buttons**

Key frontend features:

- **Real-time streaming**: Token-by-token response display with thinking indicators that can be shown or hidden
- **Interactive charts**: Chart.js visualizations generated by the agent on demand (bar, line, doughnut, radar)
- **Session management**: Create, switch, and delete chat sessions with per-user isolation
- **Dashboard**: Live metrics cards showing alarm counts, maintenance status, and latency
- **Network topology**: Interactive visualization of all 20 monitored sites across 10 locations
- **Quick actions**: Dashboard buttons for common queries—instant queries auto-send, site-specific queries prefill the input for customization
- **Whitelabel support**: Runtime-configurable branding (logo, colors, company name) loaded from S3
- **Authentication**: Cognito login with logout support

<!-- [Figure 7: Insert screenshot of the Chat interface showing a streaming response with thinking indicator and MCP tool badges] -->
**Figure 7: Chat interface with streaming response, thinking indicator, and MCP tool badges**

**Demo query for screenshot**: `Show all critical alarms`

<!-- [Figure 8: Insert screenshot of an interactive chart generated by the agent] -->
**Figure 8: Interactive Chart.js visualization generated by the agent**

**Demo query for screenshot**: `Plot a bar chart comparing throughput across all Dallas and Atlanta sites`

<!-- [Figure 9: Insert screenshot of the Network Topology view] -->
**Figure 9: Network topology — interactive visualization of 20 sites across 10 locations**

## Deployment

The entire platform deploys with a single command.

For Linux/macOS:
```bash
./deploy.sh
```

For Windows PowerShell:
```powershell
.\deploy.ps1
```

Parameters:
- `-StackName` / `--stack-name`: CloudFormation stack name (default: `netops`)
- `-Region` / `--region`: AWS region (default: `us-east-1`)
- `-CreateDemoUser` / `--create-demo-user`: Create demo users in Cognito
- `-SkipKb` / `--skip-kb`: Skip Knowledge Base deployment
- Various other skip flags for incremental deployments

The deployment script orchestrates:
1. **Infrastructure** (SAM/CloudFormation): S3 buckets, Cognito, CloudFront, Lambda@Edge, IAM roles, API Gateway
2. **Data generation**: Synthetic sites, maintenance, alarms, KPIs, and knowledge base content (troubleshooting articles + incident tickets)
3. **Knowledge Base**: S3 vector bucket, vector index, Bedrock KB with S3 Vectors, data source, and ingestion
4. **AgentCore Memory**: Short-term and long-term memory configuration
5. **MCP Server**: External context tools deployed to AgentCore Runtime
6. **Supervisor Agent**: Strands agent deployed to AgentCore Runtime with environment variables for Memory ID, KB ID, and MCP endpoint
7. **Frontend**: React build deployed to S3 with CloudFront cache invalidation

Each step can be skipped independently for incremental deployments during development.

### Prerequisites

- AWS CLI configured with appropriate credentials
- AWS SAM CLI installed
- Python 3.10+ with pip
- Node.js 18+ with npm
- Access to Amazon Bedrock models (Claude Sonnet, Nova Lite) in the deployment region
- Docker (for SAM build)

## Demonstration

After deployment, access the application via the CloudFront URL provided in the stack outputs. Here are key queries to explore each capability:

### Basic alarm monitoring
```
Show all critical alarms
```
<!-- [Figure 10: Insert screenshot of alarm monitoring response] -->

### Multi-agent site report
```
Give me a full report on site_dallas_003 including maintenance, alarms, and performance
```
<!-- [Figure 11: Insert screenshot of multi-agent coordinated response] -->

### Knowledge Base — troubleshooting guidance
```
We're seeing a POWER_ISSUE alarm at site_dallas_003. Search the knowledge base for similar past incidents and recommended resolution steps.
```
<!-- [Figure 12: Insert screenshot showing KB response with source citations] -->

### External context — root cause analysis
```
Site_richmond_008 has a SITE_DOWN alarm. Can you check for external factors that might explain the outage?
```
<!-- [Figure 13: Insert screenshot showing MCP tool invocations and root cause analysis] -->

### Interactive visualization
```
Plot a bar chart comparing throughput across all Dallas and Atlanta sites
```
<!-- [Figure 14: Insert screenshot of the generated chart] -->

### Multi-turn conversation
```
Compare that with the Chicago sites
```
<!-- [Figure 15: Insert screenshot showing context-aware follow-up] -->

## Comparing the two approaches

| Aspect | Part 1: Bedrock Agents | Part 2: Strands + AgentCore |
|---|---|---|
| Agent framework | Fully managed | Open-source SDK |
| Orchestration | Automatic | Code-controlled |
| Deployment | Lambda functions | AgentCore Runtime (serverless) |
| Streaming | Limited | Full SSE with thinking events |
| Memory | None | AgentCore Memory (STM + LTM) |
| Knowledge Base | Not implemented | Bedrock KB with S3 Vectors + citations |
| External context | Not implemented | MCP server (weather, power, 811) |
| Frontend | Streamlit on Fargate | React on S3/CloudFront |
| Charts | None | Interactive Chart.js |
| Session management | Basic | Full CRUD with per-user isolation |
| Model flexibility | Bedrock models only | Any Strands-supported model |
| Customization | Configuration-based | Full code control |
| Windows support | PowerShell script | PowerShell script |

Both approaches are valid for different use cases. The managed approach (Part 1) is ideal for rapid prototyping and teams that prefer configuration over code. The Strands approach (Part 2) is better suited for production deployments that need custom streaming, memory, external integrations, and fine-grained control over agent behavior.

## Conclusion

In this post, we rebuilt the Network Operations Assistant using the Strands Agents SDK and Amazon Bedrock AgentCore, demonstrating how open-source agent frameworks can complement AWS managed services. The result is a production-ready platform with conversation memory, knowledge base search with source citations, external context integration via MCP, and a modern React frontend—all deployed with a single command.

The combination of Strands Agents for flexible agent development, AgentCore Runtime for serverless deployment, AgentCore Memory for conversation persistence, and Bedrock Knowledge Bases with S3 Vectors for RAG provides a powerful foundation for building AI-powered operational tools. Network operations teams can now ask natural language questions, get answers grounded in real data and documented procedures, and maintain context across sessions.

The MCP integration pattern demonstrated here—with real-time weather data and simulated utility APIs—shows how agents can correlate internal monitoring data with external factors for root cause analysis. As utility companies and infrastructure providers adopt MCP, these integrations will become even more powerful, enabling agents to access live outage data, excavation permits, and environmental conditions directly.

To get started, clone the repository and deploy:

```bash
git clone <repository-url>
cd network-ops-strands
./deploy.sh --create-demo-user
```

Or on Windows:
```powershell
.\deploy.ps1 -CreateDemoUser
```

## About the authors

<!-- Add author bios here -->

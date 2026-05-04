"""Supervisor Agent - Orchestrates specialized agents using agents-as-tools pattern."""

import logging
import os
import sys
import traceback
from pathlib import Path
from typing import AsyncIterator
from dataclasses import dataclass
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

# Configure logging — INFO level for most, DEBUG only for our code
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("supervisor_agent")
logger.setLevel(logging.DEBUG)

# Keep MCP-related loggers at INFO (DEBUG floods with botocore noise)
logging.getLogger("mcp").setLevel(logging.INFO)
logging.getLogger("mcp_proxy_for_aws").setLevel(logging.INFO)
logging.getLogger("strands.tools.mcp").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
# Suppress botocore DEBUG spam (was causing massive log volume)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("s3transfer").setLevel(logging.WARNING)

try:
    from .maintenance_agent import create_maintenance_agent
    from .alarm_agent import create_alarm_agent
    from .kpi_agent import create_kpi_agent
except ImportError:
    # Fallback for direct execution (e.g., AgentCore runtime)
    from maintenance_agent import create_maintenance_agent
    from alarm_agent import create_alarm_agent
    from kpi_agent import create_kpi_agent

# Import memory hook (optional — works without it)
try:
    from memory_hook import create_memory_hook
except ImportError:
    create_memory_hook = lambda: None


# Dataclass for wrapping sub-agent events
@dataclass
class SubAgentEvent:
    """Wrapper for sub-agent streaming events."""
    agent_name: str
    event: dict


# System prompt for the supervisor agent
SUPERVISOR_SYSTEM_PROMPT = """You are a Network Operations Supervisor Agent for busy network engineers who need quick, actionable information.

**Core Principle**: Be concise. Engineers are troubleshooting in real-time and need facts fast, not lengthy explanations.

**Your Role**:
- Route queries to specialized agents (Maintenance, Alarm, KPI)
- Extract and present ONLY the most critical information
- Provide actionable insights, not verbose descriptions

**Available Agents**:
1. **Maintenance Agent**: Maintenance schedules, ongoing work, planned outages
2. **Alarm Agent**: Active alarms, severity levels, incidents
3. **KPI Agent**: Performance metrics, anomalies, trends

**External Context Tools** (MCP - use for root cause analysis):
4. **check_power_outages**: Check utility power outages near a site
5. **check_811_dig_requests**: Check for excavation/dig activity near a site
6. **get_external_context_summary**: Comprehensive external factor analysis for a site
7. **get_real_weather**: Get real-time weather by city name (e.g., "Atlanta") or site_id

**Knowledge Base Tool** (use for troubleshooting and past incidents):
8. **search_knowledge_base**: Search troubleshooting articles and past incident tickets

**When to use Knowledge Base**:
- When diagnosing an issue and need troubleshooting steps
- When looking for similar past incidents and their resolutions
- When asked "how do I fix..." or "has this happened before?"
- When providing root cause analysis with supporting evidence
- ALWAYS include the source citations (file names) from KB results in your response

**When to use External Context**:
- When a site has a SITE_DOWN or POWER_ISSUE alarm, check power outages and weather
- When a site has CONNECTIVITY_ISSUE, check 811 dig requests for cable damage
- When asked to diagnose or find root cause of an outage
- When asked "why is site X down?" or "what caused the outage?"
- IMPORTANT: Always use the exact site_id from the data (e.g., site_ashburn_011, site_suwanee_019). Do NOT guess or fabricate site IDs. If unsure, query the alarm or maintenance agent first to get the correct site_id.

**Site Naming Convention** (CRITICAL — never ask the user for a specific site_id):
Sites follow the pattern: site_{city}_{number} (e.g., site_dallas_003, site_atlanta_001)
Each city has multiple sites. When a user asks about a city (e.g., "Dallas sites", "any issues in Atlanta"), 
you MUST check ALL sites for that city by querying the relevant agents. Do NOT ask the user which specific site.
Known cities and their site ranges:
- Atlanta: site_atlanta_001, site_atlanta_002
- Dallas: site_dallas_003, site_dallas_004
- Chicago: site_chicago_005, site_chicago_006
- Richmond: site_richmond_007, site_richmond_008
- Phoenix: site_phoenix_009, site_phoenix_010
- Ashburn: site_ashburn_011, site_ashburn_012
- Piscataway: site_piscataway_013, site_piscataway_014
- Sacramento: site_sacramento_015, site_sacramento_016
- Irving: site_irving_017, site_irving_018
- Suwanee: site_suwanee_019, site_suwanee_020

**Response Guidelines**:

1. **Be Brief**: 
   - For simple queries: 2-4 sentences maximum
   - For complex queries: Use bullet points, not paragraphs
   - Skip introductions like "Let me check..." or "I'll analyze..."

2. **Prioritize Critical Info**:
   - Critical alarms first, then major, then minor
   - Active issues before historical data
   - Actionable items before context

3. **Format for Scanning**:
   - Use emojis sparingly (🔴 critical, 🟠 major, 🟡 minor)
   - Bold key numbers and statuses
   - Use tables for multiple items
   - One-line summaries when possible

4. **What to SKIP**:
   - Don't repeat the user's question
   - Don't explain what you're doing ("I'll check with the alarm agent...")
   - Don't add generic advice unless specifically asked
   - Don't include "let me know if you need more details" - they'll ask

5. **Multi-Domain Queries**:
   - Coordinate multiple agents silently
   - Present unified response with clear sections
   - Use headers: **Alarms** | **Maintenance** | **Performance**

6. **Visualization Requests** (IMPORTANT):
   - When the user asks for a chart, graph, trend, or visualization, first get the data from the KPI agent
   - Then generate a Chart.js configuration JSON wrapped in a <chart> tag
   - Do NOT use code_interpreter for charts — generate the Chart.js JSON directly
   - The frontend will render the chart interactively using Chart.js
   - Format: <chart>{"type":"line","data":{...},"options":{...}}</chart>
   - Example for a latency trend chart:
     <chart>{"type":"line","data":{"labels":["00:00","01:00","02:00"],"datasets":[{"label":"Latency (ms)","data":[18.5,19.2,17.8],"borderColor":"#3b82f6","backgroundColor":"rgba(59,130,246,0.1)","fill":true,"tension":0.3}]},"options":{"responsive":true,"plugins":{"title":{"display":true,"text":"Latency Trend - site_chicago_005 (24h)"},"legend":{"display":true}},"scales":{"y":{"title":{"display":true,"text":"Latency (ms)"},"beginAtZero":false},"x":{"title":{"display":true,"text":"Time"}}}}}</chart>
   - Use real data from the KPI agent response to populate the chart
   - Supported chart types: line, bar, doughnut, radar
   - Use colors: #3b82f6 (blue), #ef4444 (red), #f59e0b (amber), #10b981 (green), #8b5cf6 (purple)

**Example Good Response** (for "status of site_atlanta_001"):
```
**Status: DEGRADED** 🟠

**Active Issues**:
- 1 major alarm: Link down on port 24 (started 16:45)
- Maintenance ongoing: Software upgrade (ends 18:00)

**Performance**: Normal (avg latency 18ms, throughput 1.2 Gbps)
```

**Example Bad Response** (too verbose):
```
Let me check the status of site_atlanta_001 for you. I'll query the alarm agent to see if there are any active alarms, then check with the maintenance agent about any ongoing work, and finally analyze the performance metrics with the KPI agent.

After analyzing the data, I found that there is currently one major alarm active on this site. The alarm indicates that port 24 is experiencing a link down condition. This alarm started at 16:45 today. Additionally, there is ongoing maintenance scheduled for this site...
```

Remember: Network engineers are under pressure. Respect their time with concise, scannable responses."""


# Create specialized agents as tools with streaming support
@tool
async def maintenance_agent(query: str):
    """
    Get maintenance info: schedules, ongoing work, planned outages.
    Returns concise maintenance status and impact.
    """
    print(f"🔧 Routing to Maintenance Agent: {query}")
    agent = create_maintenance_agent()
    
    # Stream events from the specialized agent
    result = None
    async for event in agent.stream_async(query):
        # Yield the event wrapped so orchestrator can see it
        yield SubAgentEvent(agent_name="maintenance_agent", event=event)
        if "result" in event:
            result = event["result"]
    
    # Return the final result
    yield str(result.message if result else "No response from maintenance agent")


@tool
async def alarm_agent(query: str):
    """
    Get alarm info: active alarms, severity, incidents.
    Returns critical alarms first with actionable recommendations.
    """
    print(f"🚨 Routing to Alarm Agent: {query}")
    agent = create_alarm_agent()
    
    # Stream events from the specialized agent
    result = None
    async for event in agent.stream_async(query):
        # Yield the event wrapped so orchestrator can see it
        yield SubAgentEvent(agent_name="alarm_agent", event=event)
        if "result" in event:
            result = event["result"]
    
    # Return the final result
    yield str(result.message if result else "No response from alarm agent")


@tool
async def kpi_agent(query: str):
    """
    Get performance metrics: throughput, latency, anomalies.
    Returns key metrics and trends with brief analysis.
    When asked for charts/visualizations, generates them via code_interpreter.
    """
    print(f"📊 Routing to KPI Agent: {query}")
    agent = create_kpi_agent()
    
    # Stream events from the specialized agent, capture images from tool results
    result = None
    captured_images = []
    async for event in agent.stream_async(query):
        yield SubAgentEvent(agent_name="kpi_agent", event=event)

        # Capture images from code_interpreter tool results
        if "tool_result" in event:
            tr_content = event["tool_result"].get("content", "")
            if isinstance(tr_content, list):
                for item in tr_content:
                    if isinstance(item, dict) and item.get("image"):
                        img = item["image"]
                        fmt = img.get("format", "png")
                        b64 = img.get("source", {}).get("bytes", "")
                        if b64:
                            captured_images.append(
                                {"format": fmt, "data": b64}
                            )
                            logger.info(
                                f"[KPI_AGENT] Captured image: image/{fmt} "
                                f"({len(b64)} chars)")

        if "result" in event:
            result = event["result"]
    
    # Build response text
    text = str(result.message if result else "No response from KPI agent")

    # Append captured images as inline base64 data URIs so the supervisor
    # streams them as text and the frontend can render them
    for img in captured_images:
        fmt = img["format"]
        b64 = img["data"]
        text += f"\n\n![Chart](data:image/{fmt};base64,{b64})"

    yield text


# Resolve MCP server path
_MCP_SERVER_PATH = str(
    Path(__file__).parent.parent.parent / "mcp-server" / "external_context_mcp.py"
)

# Knowledge Base ID for Bedrock KB search
_KNOWLEDGE_BASE_ID = os.getenv("KNOWLEDGE_BASE_ID", "")


@tool
def search_knowledge_base(query: str) -> str:
    """
    Search troubleshooting articles and past incident tickets.
    Use for: root cause analysis, resolution steps, similar past incidents.
    Returns relevant articles and tickets with source citations.
    IMPORTANT: Always include the source citations in your response to the user.
    """
    if not _KNOWLEDGE_BASE_ID:
        return "Knowledge Base not configured (KNOWLEDGE_BASE_ID not set)"
    try:
        import boto3
        client = boto3.client(
            "bedrock-agent-runtime",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        response = client.retrieve(
            knowledgeBaseId=_KNOWLEDGE_BASE_ID,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {"numberOfResults": 5}
            },
        )
        results = []
        sources = []
        for i, item in enumerate(response.get("retrievalResults", []), 1):
            text = item.get("content", {}).get("text", "")
            score = item.get("score", 0)
            loc = item.get("location", {}).get("s3Location", {})
            uri = loc.get("uri", "")
            # Extract a readable source name from the S3 URI
            source_name = uri.split("/")[-1] if uri else f"source-{i}"
            if text:
                results.append(
                    f"**[Source {i}: {source_name}]** "
                    f"(relevance: {score:.0%})\n{text[:600]}"
                )
                sources.append(f"[{i}] {source_name} — {uri}")
        if not results:
            return f"No knowledge base results found for: {query}"
        output = "\n\n---\n\n".join(results)
        output += "\n\n**📚 Sources:**\n" + "\n".join(sources)
        return output
    except Exception as e:
        return f"Knowledge base search failed: {e}"


def _create_mcp_client():
    """Create MCPClient for the external context MCP server.

    Uses stdio transport locally (spawns the MCP server as a subprocess).
    For AgentCore deployment, uses mcp-proxy-for-aws for SigV4 auth.
    Returns None if MCP is not available.
    """
    agentcore_mcp_url = os.getenv("MCP_EXTERNAL_CONTEXT_URL")
    logger.info("=" * 60)
    logger.info("[MCP CLIENT] Initializing MCP connection")
    logger.info(f"  MCP_EXTERNAL_CONTEXT_URL = {agentcore_mcp_url or '(not set)'}")
    logger.info(f"  AWS_REGION = {os.getenv('AWS_REGION', '(not set)')}")
    logger.info(f"  ENVIRONMENT = {os.getenv('ENVIRONMENT', '(not set)')}")

    if agentcore_mcp_url:
        # Production: connect to MCP server on AgentCore with SigV4 auth
        # Uses mcp-proxy-for-aws which handles SigV4 signing correctly
        # Ref: https://pypi.org/project/mcp-proxy-for-aws/
        import urllib.parse
        from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client

        region = os.getenv("AWS_REGION", "us-east-1")

        # Resolve the endpoint URL from ARN or full URL
        if agentcore_mcp_url.startswith("arn:"):
            logger.info(f"  Input is ARN, constructing invocations URL")
            encoded_arn = urllib.parse.quote(agentcore_mcp_url, safe="")
            endpoint_url = (
                f"https://bedrock-agentcore.{region}.amazonaws.com"
                f"/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
            )
        elif "invocations" in agentcore_mcp_url:
            logger.info(f"  Input is full invocations URL")
            endpoint_url = agentcore_mcp_url
        else:
            logger.info(f"  Input is plain URL, appending qualifier")
            endpoint_url = agentcore_mcp_url
            if "qualifier" not in endpoint_url:
                sep = "&" if "?" in endpoint_url else "?"
                endpoint_url += f"{sep}qualifier=DEFAULT"

        logger.info(f"  Resolved endpoint: {endpoint_url}")
        logger.info(f"  Using mcp-proxy-for-aws aws_iam_streamablehttp_client")
        logger.info(f"  aws_service=bedrock-agentcore, aws_region={region}")
        logger.info("=" * 60)

        _url = endpoint_url
        _region = region
        return MCPClient(
            lambda: aws_iam_streamablehttp_client(
                endpoint=_url,
                aws_region=_region,
                aws_service="bedrock-agentcore",
            )
        )

    # Local: spawn MCP server as a subprocess via stdio
    # Only if the MCP server script actually exists on disk
    if not os.path.isfile(_MCP_SERVER_PATH):
        logger.warning(f"  MCP server script not found: {_MCP_SERVER_PATH}")
        logger.info("  MCP external context tools DISABLED")
        logger.info("=" * 60)
        return None

    from mcp import stdio_client, StdioServerParameters
    python_cmd = sys.executable
    logger.info(f"  Mode: LOCAL (stdio)")
    logger.info(f"  Python: {python_cmd}")
    logger.info(f"  Script: {_MCP_SERVER_PATH}")
    logger.info("=" * 60)
    return MCPClient(lambda: stdio_client(
        StdioServerParameters(
            command=python_cmd,
            args=[_MCP_SERVER_PATH],
        )
    ))


# Create the supervisor agent with Bedrock model
def create_supervisor_agent() -> Agent:
    """Create and return the supervisor agent with Bedrock model.

    Includes MCP tools for external context (power outages, weather, 811 dig requests).
    The MCP server is connected via stdio locally, or via HTTP on AgentCore.
    """
    logger.info("=" * 60)
    logger.info("[SUPERVISOR] Creating supervisor agent")
    logger.info(f"  AWS_REGION: {os.getenv('AWS_REGION', 'not set')}")
    logger.info(f"  ENVIRONMENT: {os.getenv('ENVIRONMENT', 'not set')}")
    logger.info(f"  DATA_BUCKET_NAME: {os.getenv('DATA_BUCKET_NAME', 'not set')}")
    logger.info(f"  MCP_EXTERNAL_CONTEXT_URL: "
                f"{os.getenv('MCP_EXTERNAL_CONTEXT_URL', 'not set')}")
    logger.info(f"  MEMORY_ID: {os.getenv('MEMORY_ID', 'not set')}")
    
    # Use Claude 4.5 Sonnet for supervisor (best for complex reasoning and coordination)
    # Note: BedrockModel uses AWS_REGION environment variable for region configuration
    try:
        model = BedrockModel(
            model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            temperature=0.5,  # Moderate temperature for natural responses
            max_tokens=4096,
            # Enable extended thinking for complex reasoning
            # This allows Claude to show its step-by-step thought process
            additional_model_request_fields={
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": 2048  # Allocate tokens for reasoning process
                }
            }
        )
        logger.info("  Bedrock model created OK")
    except Exception as e:
        logger.error(f"  Bedrock model creation FAILED: {e}")
        logger.error(traceback.format_exc())
        raise

    # Build tools list: sub-agents + MCP external context + KB
    tools = [
        maintenance_agent,
        alarm_agent,
        kpi_agent,
    ]
    logger.info(f"  Base tools: maintenance_agent, alarm_agent, kpi_agent")

    # Add knowledge base search if configured
    if _KNOWLEDGE_BASE_ID:
        tools.append(search_knowledge_base)
        logger.info(f"[SUPERVISOR] Knowledge Base tool ENABLED "
                    f"(id={_KNOWLEDGE_BASE_ID})")
    else:
        logger.info("[SUPERVISOR] Knowledge Base not configured "
                    "(KNOWLEDGE_BASE_ID not set)")

    # Add MCP client for external context tools (includes real weather)
    try:
        mcp_client = _create_mcp_client()
        if mcp_client:
            tools.append(mcp_client)
            logger.info("[SUPERVISOR] MCP external context tools ENABLED")
        else:
            logger.info("[SUPERVISOR] MCP external context tools NOT AVAILABLE")
    except Exception as e:
        logger.error(f"[SUPERVISOR] MCP client creation FAILED: {e}")
        logger.error(traceback.format_exc())
        logger.warning("  Supervisor will work without external context tools")

    # Set up memory hook for conversation persistence
    hooks = []
    memory_hook = create_memory_hook()
    if memory_hook:
        hooks.append(memory_hook)
        logger.info("[SUPERVISOR] AgentCore Memory hook ATTACHED "
                    f"(enabled={memory_hook.enabled}, "
                    f"memory_id={memory_hook.memory_id})")
    else:
        logger.info("[SUPERVISOR] AgentCore Memory hook returned None — "
                    "NOT attached")
    
    agent = Agent(
        model=model,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        tools=tools,
        hooks=hooks if hooks else None,
    )
    
    logger.info(f"[SUPERVISOR] Agent created with {len(tools)} tools")
    logger.info("=" * 60)
    return agent


if __name__ == "__main__":
    # Test the supervisor agent locally
    print("Testing Supervisor Agent with Bedrock...")
    print("\n" + "="*80 + "\n")
    
    agent = create_supervisor_agent()
    
    # Test queries
    test_queries = [
        "Check maintenance for site_atlanta_001",
        "Show me all critical alarms",
        "Analyze performance for site_dallas_003",
        "Give me a full report on site_atlanta_001 including maintenance, alarms, and performance",
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        print("-" * 80)
        response = agent(query)
        print(response.message)
        print("\n" + "="*80 + "\n")

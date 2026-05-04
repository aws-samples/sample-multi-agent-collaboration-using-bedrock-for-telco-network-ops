"""FastAPI server for Network Operations Platform."""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import AsyncGenerator
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from strands_agents import create_supervisor_agent
from session_manager import get_session_manager

# Create the supervisor agent once at startup
print("🤖 Initializing Strands Supervisor Agent...")
supervisor_agent = create_supervisor_agent()
print("✓ Supervisor agent ready!")

# Initialize session manager
print("💾 Initializing Session Manager...")
session_manager = get_session_manager()
print("✓ Session manager ready!")

app = FastAPI(title="Network Operations API")

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    session_id: str = "default"
    user_id: str = "anonymous"


class DashboardMetrics(BaseModel):
    """Dashboard metrics model with camelCase JSON serialization."""
    active_alarms: dict = Field(..., alias="activeAlarms")
    ongoing_maintenance: int = Field(..., alias="ongoingMaintenance")
    sites_monitored: int = Field(..., alias="sitesMonitored")
    average_latency: float = Field(..., alias="averageLatency")
    
    class Config:
        populate_by_name = True
        by_alias = True


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Network Operations API", "status": "running"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


async def generate_response(message: str, session_id: str = "default", user_id: str = "anonymous") -> AsyncGenerator[str, None]:
    """
    Generate streaming response using Strands Supervisor Agent with native streaming.
    
    The supervisor agent will:
    1. Analyze the query
    2. Route to appropriate specialized agent(s)
    3. Stream response with reasoning events
    
    Args:
        message: User message
        session_id: Session identifier for context preservation
        user_id: User identifier for memory actor mapping
    """
    start_time = datetime.now()
    print(f"\n{'='*60}")
    print(f"[{start_time.isoformat()}] 📨 NEW REQUEST")
    print(f"Session: {session_id}")
    print(f"User: {user_id}")
    print(f"Query: {message}")
    print(f"{'='*60}\n")
    
    try:
        # Add user message to session
        session_manager.add_message(session_id, "user", message)
        
        # Set session context on the agent for memory hook
        # JSONSerializableDict is immutable — use regular Python attributes
        supervisor_agent._netops_session_id = session_id
        supervisor_agent._netops_actor_id = user_id
        
        # Get conversation context (last 10 messages)
        context = session_manager.get_context(session_id, max_messages=10)
        print(f"📚 Context: {len(context)} previous messages")
        
        first_token_sent = False
        reasoning_buffer = []
        content_buffer = []
        tool_events = []
        announced_tools = set()  # Track which tools we've already announced
        tool_inputs = {}  # Track tool inputs as they stream in
        
        # Known MCP tool names from the external context server
        MCP_TOOLS = {
            'check_power_outages', 'check_811_dig_requests',
            'check_weather_events', 'get_external_context_summary'
        }
        # Code Interpreter tool name
        CODE_INTERPRETER_TOOLS = {'code_interpreter'}

        # Use Strands native async streaming
        async for event in supervisor_agent.stream_async(message):
            # Debug: Log event structure for understanding
            event_type = event.get("type") if isinstance(event, dict) else type(event).__name__
            
            # Log all events except common data events
            if event_type not in ["data"]:
                print(f"🔍 Event type: {event_type}, keys: {list(event.keys()) if isinstance(event, dict) else 'N/A'}")
            
            # Handle reasoning events (thinking) - from extended thinking mode
            if event.get("reasoning", False):
                reasoning_text = event.get("reasoningText", "")
                if reasoning_text:
                    reasoning_buffer.append(reasoning_text)
                    if not first_token_sent:
                        first_token_time = datetime.now()
                        print(f"[{first_token_time.isoformat()}] 💭 First reasoning after {(first_token_time - start_time).total_seconds():.2f}s")
                        first_token_sent = True
                    # Send reasoning as thinking event
                    yield f"data: {json.dumps({'type': 'thinking', 'content': reasoning_text})}\n\n"
            
            # Handle tool stream events - these contain sub-agent events including reasoning
            elif "tool_stream_event" in event:
                tool_stream_data = event["tool_stream_event"].get("data")
                
                print(f"🔍 Tool stream event received:")
                print(f"   Type: {type(tool_stream_data)}")
                print(f"   Has agent_name: {hasattr(tool_stream_data, 'agent_name')}")
                print(f"   Has event: {hasattr(tool_stream_data, 'event')}")
                
                # Check if this is a SubAgentEvent from our specialized agents
                if hasattr(tool_stream_data, 'agent_name') and hasattr(tool_stream_data, 'event'):
                    sub_agent_name = tool_stream_data.agent_name
                    sub_event = tool_stream_data.event
                    
                    print(f"   Sub-agent: {sub_agent_name}")
                    print(f"   Sub-event keys: {list(sub_event.keys()) if isinstance(sub_event, dict) else 'N/A'}")
                    
                    # The sub_event might have nested 'event' key - check for that
                    actual_event = sub_event
                    if isinstance(sub_event, dict) and 'event' in sub_event and len(sub_event) == 1:
                        # This is a wrapper, unwrap it
                        actual_event = sub_event['event']
                        print(f"   Unwrapped event keys: {list(actual_event.keys()) if isinstance(actual_event, dict) else 'N/A'}")
                    
                    # Handle reasoning from sub-agent
                    if actual_event.get("reasoning", False):
                        sub_reasoning = actual_event.get("reasoningText", "")
                        if sub_reasoning:
                            print(f"💭 Sub-agent ({sub_agent_name}) reasoning: {sub_reasoning[:100]}...")
                            # Send sub-agent reasoning as thinking event
                            thinking_text = f"\n**{sub_agent_name} reasoning:**\n{sub_reasoning}"
                            yield f"data: {json.dumps({'type': 'thinking', 'content': thinking_text})}\n\n"
                    
                    # Handle tool use from sub-agent
                    if "current_tool_use" in actual_event:
                        tool_use = actual_event["current_tool_use"]
                        tool_name = tool_use.get("name")
                        if tool_name:
                            print(f"🔧 Sub-agent ({sub_agent_name}) using tool: {tool_name}")
                            thinking_text = f"\n**{sub_agent_name}** calling tool: `{tool_name}`"
                            yield f"data: {json.dumps({'type': 'thinking', 'content': thinking_text})}\n\n"
                    
                    # Handle data from sub-agent (text output)
                    if "data" in actual_event:
                        data_chunk = actual_event["data"]
                        print(f"📝 Sub-agent ({sub_agent_name}) data: {data_chunk[:50]}...")
                        # Don't send sub-agent data as thinking, let it flow through normally
                else:
                    print(f"   ⚠️ Not a SubAgentEvent - might be string data")
                    if isinstance(tool_stream_data, str):
                        print(f"   String content: {tool_stream_data[:100]}...")
            
            # Handle tool result events - these contain the specialized agent responses
            elif event_type == "tool_result" or "tool_result" in event:
                tool_result = event.get("tool_result", {})
                tool_name = tool_result.get("name", "")
                tool_output = tool_result.get("content", "")
                
                # Check for image content from Code Interpreter
                if isinstance(tool_output, list):
                    for item in tool_output:
                        if isinstance(item, dict):
                            if item.get("type") == "image" and "data" in item:
                                print(f"🖼️  Image from {tool_name}: {item.get('mimeType', 'image/png')}")
                                yield f"data: {json.dumps({'type': 'image', 'data': item['data'], 'mimeType': item.get('mimeType', 'image/png')})}\n\n"
                            elif item.get("image"):
                                # Alternative format: {"image": {"format": "png", "source": {"bytes": "..."}}}
                                img = item["image"]
                                fmt = img.get("format", "png")
                                b64 = img.get("source", {}).get("bytes", "")
                                if b64:
                                    print(f"🖼️  Image from {tool_name}: image/{fmt}")
                                    yield f"data: {json.dumps({'type': 'image', 'data': b64, 'mimeType': f'image/{fmt}' })}\n\n"
                elif tool_output and isinstance(tool_output, str):
                    print(f"📦 Tool result from {tool_name}: {len(tool_output)} chars")
                    # Check if the string contains base64 image markers
                    if "data:image/" in tool_output:
                        print(f"🖼️  Inline image detected in {tool_name} result")
                        yield f"data: {json.dumps({'type': 'image_inline', 'content': tool_output})}\n\n"
            
            # Handle tool use streaming events
            elif event_type == "tool_use_stream" or "current_tool_use" in event:
                tool_use = event.get("current_tool_use", {})
                tool_name = tool_use.get("name")
                tool_use_id = tool_use.get("toolUseId")
                tool_input_str = tool_use.get("input", "")
                
                # Store the latest input for this tool (it streams in chunks)
                if tool_use_id:
                    tool_inputs[tool_use_id] = tool_input_str
                
                # Only announce when we have complete input (ends with })
                if tool_name and tool_use_id not in announced_tools and tool_input_str.endswith('}'):
                    announced_tools.add(tool_use_id)
                    tool_events.append(tool_name)
                    
                    # Parse the JSON string input
                    query_text = ""
                    tool_params = {}
                    try:
                        tool_params = json.loads(tool_input_str)
                        query_text = tool_params.get("query", "")
                    except json.JSONDecodeError:
                        query_text = tool_input_str
                    
                    is_mcp = tool_name in MCP_TOOLS
                    is_code = tool_name in CODE_INTERPRETER_TOOLS
                    tool_type = "MCP" if is_mcp else ("CodeInterpreter" if is_code else "Agent")
                    
                    print(f"{'🌐' if is_mcp else '💻' if is_code else '🔧'} Tool invocation [{tool_type}]: {tool_name}")
                    if query_text:
                        print(f"   Query: {query_text}")
                    if is_mcp:
                        print(f"   MCP Params: {json.dumps(tool_params, default=str)}")
                    
                    if is_mcp:
                        # Send MCP-specific event for distinct UI treatment
                        yield f"data: {json.dumps({'type': 'mcp_tool', 'tool': tool_name, 'params': tool_params})}\n\n"
                    elif is_code:
                        # Send Code Interpreter event
                        yield f"data: {json.dumps({'type': 'code_interpreter', 'tool': tool_name, 'params': tool_params})}\n\n"
                    else:
                        # Send regular tool event as thinking
                        if query_text:
                            thinking_text = f"🔧 Calling {tool_name}\n   Query: \"{query_text}\""
                        else:
                            thinking_text = f"🔧 Calling {tool_name}"
                        yield f"data: {json.dumps({'type': 'thinking', 'content': thinking_text})}\n\n"
            
            # Handle text content deltas
            elif "data" in event:
                text_chunk = event["data"]
                
                # Regular content
                content_buffer.append(text_chunk)
                if not first_token_sent:
                    first_token_time = datetime.now()
                    print(f"[{first_token_time.isoformat()}] ⚡ First token after {(first_token_time - start_time).total_seconds():.2f}s")
                    first_token_sent = True
                # Send text token
                yield f"data: {json.dumps({'type': 'token', 'content': text_chunk})}\n\n"
            
            # Handle result (final message)
            elif "result" in event:
                result = event["result"]
                print(f"\n✅ Agent completed")
                print(f"Reasoning events: {len(reasoning_buffer)}")
                print(f"Tool invocations: {len(tool_events)}")
                print(f"Content chunks: {len(content_buffer)}")
        
        # Send done event
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        
        end_time = datetime.now()
        print(f"\n[{end_time.isoformat()}] ✅ RESPONSE COMPLETE")
        print(f"Total time: {(end_time - start_time).total_seconds():.2f}s")
        
        full_response = ''.join(content_buffer)
        full_reasoning = ''.join(reasoning_buffer)
        print(f"Response length: {len(full_response)} chars")
        if full_reasoning:
            print(f"Reasoning length: {len(full_reasoning)} chars")
        if tool_events:
            mcp_tools_used = [t for t in tool_events if t in MCP_TOOLS]
            agent_tools_used = [t for t in tool_events if t not in MCP_TOOLS]
            print(f"Tools used: {', '.join(tool_events)}")
            if mcp_tools_used:
                print(f"  🌐 MCP tools: {', '.join(mcp_tools_used)}")
            if agent_tools_used:
                print(f"  🔧 Agent tools: {', '.join(agent_tools_used)}")
        print(f"\nFull response:\n{'-'*60}\n{full_response}\n{'-'*60}\n")
        
        # Add assistant response to session
        session_manager.add_message(session_id, "assistant", full_response)
        
    except Exception as e:
        error_time = datetime.now()
        print(f"\n[{error_time.isoformat()}] ❌ ERROR")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")
        
        error_message = f"I encountered an error processing your request: {str(e)}"
        yield f"data: {json.dumps({'type': 'token', 'content': error_message})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream chat responses.
    
    Args:
        request: Chat request with message and session_id.
        
    Returns:
        Streaming response with Server-Sent Events.
    """
    return StreamingResponse(
        generate_response(request.message, request.session_id, request.user_id),
        media_type="text/event-stream"
    )


@app.get("/api/dashboard/metrics")
async def get_dashboard_metrics() -> DashboardMetrics:
    """
    Get dashboard metrics using tool functions.
    
    Returns:
        Dashboard metrics including alarm counts and site statistics.
    """
    print("\n" + "="*60)
    print("📊 DASHBOARD METRICS REQUEST")
    print("="*60)
    
    try:
        # Import the tool functions and data loader
        print("📦 Importing tool functions...")
        from tools.alarm_tools import get_active_alarms
        from tools.maintenance_tools import get_ongoing_maintenance
        from tools import DataLoader
        import os
        from pathlib import Path
        
        # Initialize data loader based on environment
        environment = os.getenv("ENVIRONMENT", "local")
        print(f"🌍 Environment: {environment}")
        
        if environment == "local":
            project_root = Path(__file__).parent.parent
            data_dir = str(project_root / "data")
            print(f"📁 Data directory: {data_dir}")
            print(f"📁 Directory exists: {Path(data_dir).exists()}")
            if Path(data_dir).exists():
                files = list(Path(data_dir).glob("*.csv"))
                print(f"📄 CSV files found: {[f.name for f in files]}")
            data_loader = DataLoader(data_dir=data_dir)
        else:
            from tools import S3DataLoader
            bucket_name = os.getenv("DATA_BUCKET_NAME")
            print(f"☁️ S3 bucket: {bucket_name}")
            data_loader = S3DataLoader(bucket_name=bucket_name)
        
        # Get active alarms
        print("\n🚨 Fetching active alarms...")
        alarms_data = get_active_alarms(data_loader)
        print(f"   Total alarms: {alarms_data.get('total_count', 0)}")
        print(f"   Critical: {alarms_data.get('critical_count', 0)}")
        print(f"   Major: {alarms_data.get('major_count', 0)}")
        print(f"   Minor: {alarms_data.get('minor_count', 0)}")
        print(f"   Warning: {alarms_data.get('warning_count', 0)}")
        if 'error' in alarms_data:
            print(f"   ⚠️ Error: {alarms_data['error']}")
        
        # Get ongoing maintenance
        print("\n🔧 Fetching ongoing maintenance...")
        ongoing_maintenance_list = get_ongoing_maintenance(data_loader)
        print(f"   Ongoing maintenance count: {len(ongoing_maintenance_list)}")
        
        metrics = DashboardMetrics(
            activeAlarms={
                "critical": alarms_data.get("critical_count", 0),
                "major": alarms_data.get("major_count", 0),
                "minor": alarms_data.get("minor_count", 0),
                "warning": alarms_data.get("warning_count", 0)
            },
            ongoingMaintenance=len(ongoing_maintenance_list),
            sitesMonitored=20,  # From our generated data
            averageLatency=18.5  # Approximate from KPI data
        )
        
        print("\n✅ Returning metrics:")
        print(f"   Active alarms: {metrics.active_alarms}")
        print(f"   Ongoing maintenance: {metrics.ongoing_maintenance}")
        print(f"   Sites monitored: {metrics.sites_monitored}")
        print(f"   Average latency: {metrics.average_latency}")
        print("="*60 + "\n")
        
        return metrics
        
    except Exception as e:
        print(f"\n❌ ERROR getting dashboard metrics:")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {str(e)}")
        import traceback
        print("\n📋 Full traceback:")
        traceback.print_exc()
        print("="*60 + "\n")
        
        # Return default metrics on error
        return DashboardMetrics(
            activeAlarms={"critical": 0, "major": 0, "minor": 0, "warning": 0},
            ongoingMaintenance=0,
            sitesMonitored=20,
            averageLatency=18.5
        )


@app.get("/api/chat/history")
async def get_chat_history(session_id: str = "default"):
    """Return conversation history for a session from the supervisor agent."""
    messages = []
    try:
        if supervisor_agent:
            for msg in getattr(supervisor_agent, "messages", []):
                role = msg.get("role", "")
                content_parts = msg.get("content", [])
                text = ""
                for part in content_parts:
                    if isinstance(part, dict) and "text" in part:
                        text += part["text"]
                    elif isinstance(part, str):
                        text += part
                if text and role in ("user", "assistant"):
                    messages.append({"role": role, "content": text})
    except Exception as e:
        print(f"History error: {e}")
    return {"messages": messages, "session_id": session_id}


@app.get("/api/topology")
async def get_topology(profile: str = "qts"):
    """
    Get network topology data for visualization.
    
    Args:
        profile: Topology profile ('qts' for data center or 'telco' for CSP).
        
    Returns:
        Network topology with nodes and edges.
    """
    print(f"\n📡 Topology request for profile: {profile}")
    
    topology_file = Path(__file__).parent.parent / "data" / f"topology_{profile}.json"
    
    try:
        with open(topology_file, 'r') as f:
            topology = json.load(f)
        print(f"✅ Loaded topology: {len(topology['nodes'])} nodes, {len(topology['edges'])} edges")
        return topology
    except FileNotFoundError:
        print(f"❌ Topology file not found: {topology_file}")
        raise HTTPException(status_code=404, detail=f"Topology profile '{profile}' not found")
    except Exception as e:
        print(f"❌ Error loading topology: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config")
async def get_config():
    """
    Get runtime configuration including whitelabel settings.
    
    Returns:
        Configuration including branding.
    """
    config_path = Path(__file__).parent.parent / "config" / "qts-branding.json"
    
    try:
        with open(config_path, 'r') as f:
            branding = json.load(f)
    except FileNotFoundError:
        # Return default branding
        branding = {
            "companyName": "Network Operations Platform",
            "logoUrl": "/logo.svg",
            "primaryColor": "#3B82F6",
            "secondaryColor": "#8B5CF6"
        }
    
    return {
        "branding": branding,
        "apiEndpoint": "http://localhost:8000",
        "features": branding.get("features", {
            "darkMode": True,
            "dashboard": True
        })
    }


@app.post("/api/session/create")
async def create_session():
    """
    Create a new session.
    
    Returns:
        Session ID.
    """
    session = session_manager.get_or_create_session()
    return {"session_id": session.session_id}


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a session.
    
    Args:
        session_id: Session identifier.
        
    Returns:
        Success message.
    """
    session_manager.delete_session(session_id)
    return {"message": "Session deleted", "session_id": session_id}


@app.get("/api/session/{session_id}/history")
async def get_session_history(session_id: str, limit: int = 50):
    """
    Get session message history.
    
    Args:
        session_id: Session identifier.
        limit: Maximum number of messages to return.
        
    Returns:
        List of messages.
    """
    context = session_manager.get_context(session_id, max_messages=limit)
    return {"session_id": session_id, "messages": context}


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Network Operations API Server...")
    print("📍 API: http://localhost:8000")
    print("📚 Docs: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

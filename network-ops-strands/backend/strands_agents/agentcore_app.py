"""AgentCore deployment entry point for Network Operations Strands Platform.

Supports both streaming (chat) and non-streaming (metrics) invocations.
The agent is lazy-initialized on first invocation.
"""

import logging
import os
import sys
import json
import traceback
from pathlib import Path

# Configure logging — INFO for most, DEBUG for our code
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
ac_logger = logging.getLogger("agentcore_app")
ac_logger.setLevel(logging.DEBUG)
# Suppress botocore DEBUG spam
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("s3transfer").setLevel(logging.WARNING)

_backend_dir = str(Path(__file__).parent.parent)
_agents_dir = str(Path(__file__).parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
if _agents_dir not in sys.path:
    sys.path.insert(0, _agents_dir)

ac_logger.info("=" * 60)
ac_logger.info("AGENTCORE APP STARTING")
ac_logger.info(f"  Python: {sys.version}")
ac_logger.info(f"  PID: {os.getpid()}")
ac_logger.info(f"  ENVIRONMENT: {os.environ.get('ENVIRONMENT', 'not set')}")
ac_logger.info(f"  AWS_REGION: {os.environ.get('AWS_REGION', 'not set')}")
ac_logger.info(f"  DATA_BUCKET_NAME: {os.environ.get('DATA_BUCKET_NAME', 'not set')}")
ac_logger.info(f"  MCP_EXTERNAL_CONTEXT_URL: "
               f"{os.environ.get('MCP_EXTERNAL_CONTEXT_URL', 'not set')}")
ac_logger.info(f"  MEMORY_ID: {os.environ.get('MEMORY_ID', 'not set')}")
ac_logger.info(f"  sys.path[0:3]: {sys.path[:3]}")
ac_logger.info("=" * 60)

from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

_supervisor = None


def _get_supervisor():
    """Lazy-init the supervisor agent."""
    global _supervisor
    if _supervisor is None:
        ac_logger.info("[INIT] First invocation — initializing supervisor agent...")
        app.logger.info("Initializing supervisor agent...")
        try:
            from supervisor_agent import create_supervisor_agent
            _supervisor = create_supervisor_agent()
            ac_logger.info("[INIT] Supervisor agent ready")
            app.logger.info("Supervisor agent ready")
        except Exception as e:
            ac_logger.error(f"[INIT] Supervisor init FAILED: {e}")
            ac_logger.error(traceback.format_exc())
            raise
    return _supervisor


def _handle_metrics(session_id: str) -> dict:
    """Handle metrics request directly — no LLM, reads S3 data."""
    try:
        from tools.alarm_tools import get_active_alarms
        from tools.maintenance_tools import get_ongoing_maintenance
        from tools import S3DataLoader, DataLoader

        environment = os.getenv("ENVIRONMENT", "local")
        if environment == "local":
            project_root = Path(__file__).parent.parent.parent
            data_loader = DataLoader(data_dir=str(project_root / "data"))
        else:
            bucket_name = os.getenv("DATA_BUCKET_NAME", "")
            data_loader = S3DataLoader(bucket_name=bucket_name)

        alarms = get_active_alarms(data_loader)
        maintenance = get_ongoing_maintenance(data_loader)

        return {
            "action": "metrics",
            "data": {
                "activeAlarms": {
                    "critical": alarms.get("critical_count", 0),
                    "major": alarms.get("major_count", 0),
                    "minor": alarms.get("minor_count", 0),
                    "warning": alarms.get("warning_count", 0),
                },
                "ongoingMaintenance": len(maintenance),
                "sitesMonitored": 20,
                "averageLatency": 18.5,
            },
            "session_id": session_id,
        }
    except Exception as e:
        app.logger.error(f"Metrics error: {e}")
        return {
            "action": "metrics",
            "data": {
                "activeAlarms": {
                    "critical": 0, "major": 0, "minor": 0, "warning": 0
                },
                "ongoingMaintenance": 0,
                "sitesMonitored": 20,
                "averageLatency": 18.5,
            },
            "session_id": session_id,
        }


# Known MCP tool names for tagging events
MCP_TOOLS = {
    'check_power_outages', 'check_811_dig_requests',
    'get_external_context_summary', 'get_real_weather',
}
# Code Interpreter tool name
CODE_INTERPRETER_TOOLS = {'code_interpreter'}


@app.entrypoint
async def agent_invocation(payload, context):
    """Streaming entrypoint — yields SSE events for real-time UI updates."""
    session_id = getattr(context, "session_id", "default") or "default"

    ac_logger.info(f"[INVOKE] payload keys: {list(payload.keys())} | "
                   f"session: {session_id}")

    # Non-streaming actions (metrics)
    action = payload.get("action")
    if action == "metrics":
        ac_logger.info("[INVOKE] Handling metrics request (no LLM)")
        yield _handle_metrics(session_id)
        return

    # Return conversation history from the supervisor's message store
    if action == "history":
        ac_logger.info(f"[INVOKE] Handling history request | session: {session_id}")
        try:
            supervisor = _get_supervisor()
            messages = []
            # Strands agents store conversation in agent.messages
            for msg in getattr(supervisor, "messages", []):
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
            yield {"action": "history", "messages": messages,
                   "session_id": session_id}
        except Exception as e:
            ac_logger.error(f"[INVOKE] History error: {e}")
            yield {"action": "history", "messages": [],
                   "session_id": session_id}
        return

    user_message = payload.get("prompt", "Hello")
    ac_logger.info(f"[INVOKE] Query: {user_message}")
    app.logger.info(f"Query: {user_message} | Session: {session_id}")

    try:
        supervisor = _get_supervisor()
        # Store session context as regular attributes (JSONSerializableDict is immutable)
        actor_id = payload.get("actor_id", session_id)
        supervisor._netops_session_id = session_id
        supervisor._netops_actor_id = actor_id
        ac_logger.info(f"[INVOKE] Memory context SET on supervisor:")
        ac_logger.info(f"[INVOKE]   actor_id={actor_id!r} "
                       f"(from payload 'actor_id'={payload.get('actor_id')!r})")
        ac_logger.info(f"[INVOKE]   session_id={session_id!r}")
        ac_logger.info(f"[INVOKE]   verify: supervisor._netops_session_id="
                       f"{getattr(supervisor, '_netops_session_id', 'MISSING')!r}")
        ac_logger.info(f"[INVOKE]   verify: supervisor._netops_actor_id="
                       f"{getattr(supervisor, '_netops_actor_id', 'MISSING')!r}")
        ac_logger.info(f"[INVOKE]   MEMORY_ID env="
                       f"{os.environ.get('MEMORY_ID', 'NOT SET')!r}")
        announced_tools = set()

        async for event in supervisor.stream_async(user_message):
            # Reasoning / thinking events
            if event.get("reasoning", False):
                text = event.get("reasoningText", "")
                if text:
                    yield {"type": "thinking", "content": text}

            # Sub-agent stream events (from kpi_agent, alarm_agent, etc.)
            # These may contain code_interpreter images
            elif "tool_stream_event" in event:
                tse_data = event["tool_stream_event"].get("data")
                # Check for SubAgentEvent with nested tool_result containing images
                if hasattr(tse_data, 'event'):
                    sub_event = tse_data.event
                    if isinstance(sub_event, dict) and "tool_result" in sub_event:
                        tr = sub_event["tool_result"]
                        content = tr.get("content", "")
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict):
                                    # Format: {"image": {"format":"png","source":{"bytes":"..."}}}
                                    if item.get("image"):
                                        img = item["image"]
                                        fmt = img.get("format", "png")
                                        b64 = img.get("source", {}).get("bytes", "")
                                        if b64:
                                            ac_logger.info(
                                                f"[IMAGE] from sub-agent: image/{fmt} "
                                                f"({len(b64)} chars)")
                                            yield {
                                                "type": "image",
                                                "data": b64,
                                                "mimeType": f"image/{fmt}",
                                            }
                                    # Format: {"type":"image","data":"...","mimeType":"..."}
                                    elif (item.get("type") == "image"
                                            and "data" in item):
                                        ac_logger.info(
                                            f"[IMAGE] from sub-agent: "
                                            f"{item.get('mimeType', 'image/png')}")
                                        yield {
                                            "type": "image",
                                            "data": item["data"],
                                            "mimeType": item.get(
                                                "mimeType", "image/png"),
                                        }

            # Tool use events
            elif "current_tool_use" in event:
                tool_use = event["current_tool_use"]
                tool_name = tool_use.get("name")
                tool_id = tool_use.get("toolUseId")
                tool_input = tool_use.get("input", "")

                if (tool_name and tool_id
                        and tool_id not in announced_tools
                        and isinstance(tool_input, str)
                        and tool_input.endswith("}")):
                    announced_tools.add(tool_id)

                    params = {}
                    try:
                        params = json.loads(tool_input)
                    except json.JSONDecodeError:
                        pass

                    ac_logger.info(f"[TOOL] {tool_name} | params: "
                                   f"{json.dumps(params)[:200]}")

                    if tool_name in MCP_TOOLS:
                        yield {
                            "type": "mcp_tool",
                            "tool": tool_name,
                            "params": params,
                        }
                    elif tool_name in CODE_INTERPRETER_TOOLS:
                        ac_logger.info(f"[CODE_INTERPRETER] Invoked")
                        yield {
                            "type": "code_interpreter",
                            "tool": tool_name,
                            "params": params,
                        }
                    else:
                        query = params.get("query", "")
                        yield {
                            "type": "thinking",
                            "content": (
                                f"🔧 Calling {tool_name}"
                                + (f'\n   Query: "{query}"' if query else "")
                            ),
                        }

            # Text content
            elif "data" in event:
                yield {"type": "token", "content": event["data"]}

            # Tool results — check for images from Code Interpreter
            elif "tool_result" in event:
                tool_result = event.get("tool_result", {})
                tool_output = tool_result.get("content", "")
                tool_name = tool_result.get("name", "")
                ac_logger.info(f"[TOOL_RESULT] {tool_name} | "
                               f"type={type(tool_output).__name__}")
                # Check for image content
                if isinstance(tool_output, list):
                    for item in tool_output:
                        if isinstance(item, dict):
                            if (item.get("type") == "image"
                                    and "data" in item):
                                ac_logger.info(
                                    f"[IMAGE] from {tool_name}: "
                                    f"{item.get('mimeType', 'image/png')}")
                                yield {
                                    "type": "image",
                                    "data": item["data"],
                                    "mimeType": item.get(
                                        "mimeType", "image/png"),
                                }
                            elif item.get("image"):
                                img = item["image"]
                                fmt = img.get("format", "png")
                                b64 = img.get("source", {}).get("bytes", "")
                                if b64:
                                    ac_logger.info(
                                        f"[IMAGE] from {tool_name}: "
                                        f"image/{fmt}")
                                    yield {
                                        "type": "image",
                                        "data": b64,
                                        "mimeType": f"image/{fmt}",
                                    }

            # Final result
            elif "result" in event:
                ac_logger.info("[INVOKE] Stream complete (result received)")

        yield {"type": "done"}
        ac_logger.info("[INVOKE] Done event sent")
        ac_logger.info(f"[INVOKE] Post-stream verify: "
                       f"supervisor._netops_actor_id="
                       f"{getattr(supervisor, '_netops_actor_id', 'MISSING')!r}, "
                       f"supervisor._netops_session_id="
                       f"{getattr(supervisor, '_netops_session_id', 'MISSING')!r}")

    except Exception as e:
        ac_logger.error(f"[INVOKE] Error: {e}")
        ac_logger.error(traceback.format_exc())
        app.logger.error(f"Error: {e}")
        yield {"type": "token", "content": f"Error: {e}"}
        yield {"type": "done"}


if __name__ == "__main__":
    app.run()

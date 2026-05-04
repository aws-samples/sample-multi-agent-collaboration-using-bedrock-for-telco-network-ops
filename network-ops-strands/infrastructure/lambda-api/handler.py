"""
Lambda handler for Network Operations API.

Provides non-LLM endpoints for the frontend:
- GET /api/metrics       — dashboard alarm/maintenance counts from S3
- GET /api/topology      — network topology graph from S3
- GET /api/chat/history  — conversation history from AgentCore Memory STM
- GET /api/config        — branding configuration from S3
"""

import json
import os
import csv
import io
import logging
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DATA_BUCKET = os.environ.get("DATA_BUCKET", "")
CONFIG_BUCKET = os.environ.get("CONFIG_BUCKET", "")
MEMORY_ID = os.environ.get("MEMORY_ID", "")
REGION = os.environ.get("AWS_REGION", "us-east-1")

s3 = boto3.client("s3", region_name=REGION)

# CORS headers for all responses
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,DELETE,OPTIONS",
    "Content-Type": "application/json",
}


def respond(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body, default=str),
    }


def _read_csv_from_s3(key: str) -> list[dict]:
    """Read a CSV file from S3 and return as list of dicts."""
    try:
        obj = s3.get_object(Bucket=DATA_BUCKET, Key=key)
        content = obj["Body"].read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))
        return [row for row in reader]
    except Exception as e:
        logger.error(f"Failed to read {key} from S3: {e}")
        return []


def _read_json_from_s3(bucket: str, key: str) -> dict:
    """Read a JSON file from S3."""
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to read {key} from {bucket}: {e}")
        return {}


# ── GET /api/metrics ──────────────────────────────────────────────

def handle_metrics() -> dict:
    """Return dashboard metrics: alarm counts, maintenance, etc."""
    now = datetime.now(timezone.utc)

    # Count active alarms by severity
    alarms = _read_csv_from_s3("alarms.csv")
    counts = {"critical": 0, "major": 0, "minor": 0, "warning": 0}
    for alarm in alarms:
        if alarm.get("status", "").strip().lower() == "active":
            sev = alarm.get("severity", "").strip().lower()
            if sev in counts:
                counts[sev] += 1

    # Count ongoing maintenance
    maint = _read_csv_from_s3("maintenance_schedule.csv")
    ongoing = 0
    for m in maint:
        try:
            start = datetime.fromisoformat(m.get("start_time", "").strip())
            end = datetime.fromisoformat(m.get("end_time", "").strip())
            if start <= now.replace(tzinfo=None) <= end:
                ongoing += 1
        except (ValueError, TypeError):
            pass

    return respond(200, {
        "activeAlarms": counts,
        "ongoingMaintenance": ongoing,
        "sitesMonitored": 20,
        "averageLatency": 18.5,
    })


# ── GET /api/topology ─────────────────────────────────────────────

def handle_topology(event: dict) -> dict:
    """Return network topology graph data from S3."""
    params = event.get("queryStringParameters") or {}
    profile = params.get("profile", "datacenter")
    key = f"topology_{profile}.json"
    data = _read_json_from_s3(DATA_BUCKET, key)
    if not data:
        return respond(404, {"error": f"Topology '{profile}' not found"})
    return respond(200, data)


# ── GET /api/chat/sessions ─────────────────────────────────────────

def handle_chat_sessions(event: dict) -> dict:
    """Return list of chat sessions for a user from AgentCore Memory."""
    params = event.get("queryStringParameters") or {}
    actor_id = params.get("actor_id", "")

    if not MEMORY_ID:
        return respond(200, {"sessions": [], "error": "MEMORY_ID not configured"})
    if not actor_id:
        return respond(400, {"error": "actor_id is required"})

    # actor_id should be Cognito sub (UUID) — already valid for AgentCore
    try:
        agentcore = boto3.client("bedrock-agentcore", region_name=REGION)
        response = agentcore.list_sessions(
            memoryId=MEMORY_ID,
            actorId=actor_id,
            maxResults=20,
        )

        sessions = []
        for s in response.get("sessionSummaries", []):
            sessions.append({
                "sessionId": s.get("sessionId", ""),
                "createdAt": s.get("createdAt", ""),
            })

        return respond(200, {"sessions": sessions, "actor_id": actor_id})

    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        # ResourceNotFoundException = actor has no sessions yet — not an error
        return respond(200, {"sessions": [], "actor_id": actor_id})


# ── GET /api/chat/history ─────────────────────────────────────────

def handle_chat_history(event: dict) -> dict:
    """Return conversation history from AgentCore Memory STM."""
    params = event.get("queryStringParameters") or {}
    session_id = params.get("session_id", "")
    actor_id = params.get("actor_id", "")

    if not MEMORY_ID:
        return respond(200, {"messages": [], "error": "MEMORY_ID not configured"})
    if not session_id or not actor_id:
        return respond(400, {"error": "session_id and actor_id are required"})

    # Pad session_id to 33 chars to match AgentCore runtime format
    # (the frontend pads session IDs before sending to AgentCore invocations)
    padded_session_id = session_id.ljust(33, '0')

    # actor_id should be Cognito sub (UUID) — already valid for AgentCore
    try:
        agentcore = boto3.client("bedrock-agentcore", region_name=REGION)
        response = agentcore.list_events(
            memoryId=MEMORY_ID,
            actorId=actor_id,
            sessionId=padded_session_id,
            maxResults=50,
        )

        messages = []
        events = list(reversed(response.get("events", [])))
        for evt in events:
            payload_items = evt.get("payload", [])
            # payload is a list of items, each with "conversational" key
            for item in payload_items:
                conv = item.get("conversational", {})
                text = conv.get("content", {}).get("text", "")
                role = conv.get("role", "").lower()  # API returns "USER"/"ASSISTANT"
                if text and role in ("user", "assistant"):
                    messages.append({"role": role, "content": text})

        return respond(200, {"messages": messages, "session_id": session_id})

    except Exception as e:
        logger.error(f"Failed to list events: {e}")
        # ResourceNotFoundException = no events for this session yet
        return respond(200, {"messages": [], "session_id": session_id})


# ── DELETE /api/chat/sessions ──────────────────────────────────────

def handle_delete_session(event: dict) -> dict:
    """Delete a chat session by removing all its events from AgentCore Memory."""
    params = event.get("queryStringParameters") or {}
    session_id = params.get("session_id", "")
    actor_id = params.get("actor_id", "")

    if not MEMORY_ID:
        return respond(200, {"deleted": False, "error": "MEMORY_ID not configured"})
    if not session_id or not actor_id:
        return respond(400, {"error": "session_id and actor_id are required"})

    padded_session_id = session_id.ljust(33, '0')

    try:
        agentcore = boto3.client("bedrock-agentcore", region_name=REGION)

        # List all events for this session
        events_to_delete = []
        next_token = None
        while True:
            params_req = {
                "memoryId": MEMORY_ID,
                "actorId": actor_id,
                "sessionId": padded_session_id,
                "maxResults": 100,
            }
            if next_token:
                params_req["nextToken"] = next_token
            response = agentcore.list_events(**params_req)
            for evt in response.get("events", []):
                events_to_delete.append(evt.get("eventId"))
            next_token = response.get("nextToken")
            if not next_token:
                break

        # Delete each event
        deleted_count = 0
        for event_id in events_to_delete:
            if event_id:
                try:
                    agentcore.delete_event(
                        memoryId=MEMORY_ID,
                        actorId=actor_id,
                        sessionId=padded_session_id,
                        eventId=event_id,
                    )
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete event {event_id}: {e}")

        return respond(200, {
            "deleted": True,
            "session_id": session_id,
            "events_deleted": deleted_count,
        })

    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        return respond(200, {"deleted": False, "error": str(e)})


# ── GET /api/config ───────────────────────────────────────────────

def handle_config() -> dict:
    """Return branding configuration from S3."""
    data = _read_json_from_s3(CONFIG_BUCKET or DATA_BUCKET, "config.json")
    if not data:
        data = {
            "companyName": "Network Operations",
            "primaryColor": "#3B82F6",
            "secondaryColor": "#8B5CF6",
        }
    return respond(200, {"branding": data})


# ── Lambda entry point ────────────────────────────────────────────

def lambda_handler(event, context):
    """Route API Gateway requests to the appropriate handler."""
    path = event.get("path", "") or event.get("rawPath", "")
    method = (event.get("httpMethod", "") or
              event.get("requestContext", {}).get("http", {}).get("method", ""))

    logger.info(f"{method} {path}")

    # CORS preflight
    if method == "OPTIONS":
        return respond(200, {})

    if path == "/api/metrics":
        return handle_metrics()
    elif path == "/api/topology":
        return handle_topology(event)
    elif path == "/api/chat/sessions":
        params = event.get("queryStringParameters") or {}
        if params.get("action") == "delete" or method == "DELETE":
            return handle_delete_session(event)
        return handle_chat_sessions(event)
    elif path == "/api/chat/history":
        return handle_chat_history(event)
    elif path == "/api/config":
        return handle_config()
    else:
        return respond(404, {"error": f"Not found: {path}"})

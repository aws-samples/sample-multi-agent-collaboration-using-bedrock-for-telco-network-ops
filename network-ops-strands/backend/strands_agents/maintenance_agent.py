"""Maintenance Agent - Strands implementation with Bedrock."""

import os
import sys
from pathlib import Path
from typing import Dict, Any

from strands import Agent, tool
from strands.models import BedrockModel

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import DataLoader, S3DataLoader
from tools.maintenance_tools import (
    get_maintenance_by_site,
    get_ongoing_maintenance,
    get_maintenance_by_date_range
)


# Initialize data loader based on environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
if ENVIRONMENT == "local":
    project_root = Path(__file__).parent.parent.parent
    data_loader = DataLoader(data_dir=str(project_root / "data"))
else:
    bucket_name = os.getenv("DATA_BUCKET_NAME")
    data_loader = S3DataLoader(bucket_name=bucket_name)


# System prompt for the maintenance agent
MAINTENANCE_SYSTEM_PROMPT = """You are a specialized Network Maintenance Agent responsible for monitoring and reporting on network maintenance schedules.

Your capabilities:
- Check maintenance schedules for specific sites
- Identify ongoing maintenance windows
- Report upcoming maintenance activities
- Assess maintenance impact on network operations

When responding:
1. Always provide clear, structured information about maintenance windows
2. Highlight active maintenance that may be affecting services
3. Include time remaining for ongoing maintenance
4. Note if maintenance requires service outages
5. Prioritize critical and high-priority maintenance in your reports

Format your responses with:
- Clear headers for active vs upcoming maintenance
- All relevant details (ID, type, times, priority, team, outage requirements)
- Time-based context (e.g., "ending in 45 minutes")
- Actionable insights about potential service impacts
"""


@tool
def check_site_maintenance(site_id: str) -> str:
    """
    Check maintenance schedule for a specific network site.
    
    Args:
        site_id: Site identifier (e.g., site_atlanta_001, site_dallas_003).
        
    Returns:
        Detailed maintenance information including active and upcoming windows.
    """
    result = get_maintenance_by_site(site_id, data_loader)
    
    if "error" in result:
        return f"Error checking maintenance for {site_id}: {result['error']}"
    
    response = []
    
    # Active maintenance
    if result["active_maintenance"]:
        response.append(f"## 🔧 ACTIVE MAINTENANCE for {site_id}\n")
        for m in result["active_maintenance"]:
            time_left = m.time_remaining()
            time_str = f"{time_left} minutes remaining" if time_left else "ending soon"
            response.append(f"""
**Maintenance ID:** {m.maintenance_id}
**Type:** {m.maintenance_type}
**Description:** {m.description}
**Start Time:** {m.start_time.strftime('%Y-%m-%d %H:%M:%S')}
**End Time:** {m.end_time.strftime('%Y-%m-%d %H:%M:%S')}
**Status:** {m.status} ({time_str})
**Priority:** {m.priority}
**Team:** {m.team}
**Requires Outage:** {m.requires_outage}
""")
    else:
        response.append(f"✅ No active maintenance for {site_id}\n")
    
    # Upcoming maintenance
    if result["upcoming_maintenance"]:
        response.append(f"\n## 📅 UPCOMING MAINTENANCE for {site_id}\n")
        for m in result["upcoming_maintenance"]:
            response.append(f"""
**Maintenance ID:** {m.maintenance_id}
**Type:** {m.maintenance_type}
**Description:** {m.description}
**Start Time:** {m.start_time.strftime('%Y-%m-%d %H:%M:%S')}
**End Time:** {m.end_time.strftime('%Y-%m-%d %H:%M:%S')}
**Status:** {m.status}
**Priority:** {m.priority}
**Team:** {m.team}
**Requires Outage:** {m.requires_outage}
""")
    else:
        response.append(f"No upcoming maintenance scheduled for {site_id}\n")
    
    return "\n".join(response)


@tool
def check_all_ongoing_maintenance() -> str:
    """
    Check all ongoing maintenance across all network sites.
    
    Returns:
        List of all currently active maintenance windows.
    """
    ongoing = get_ongoing_maintenance(data_loader)
    
    if not ongoing:
        return "✅ No ongoing maintenance at this time across all sites."
    
    response = [f"## 🔧 ONGOING MAINTENANCE ({len(ongoing)} active)\n"]
    
    for m in ongoing:
        time_left = m.time_remaining()
        time_str = f"{time_left} minutes remaining" if time_left else "ending soon"
        response.append(f"""
**Site:** {m.site_id}
**Maintenance ID:** {m.maintenance_id}
**Type:** {m.maintenance_type}
**Description:** {m.description}
**End Time:** {m.end_time.strftime('%Y-%m-%d %H:%M:%S')} ({time_str})
**Priority:** {m.priority}
**Team:** {m.team}
""")
    
    return "\n".join(response)


@tool
def check_maintenance_by_date_range(start_date: str, end_date: str) -> str:
    """
    Check maintenance scheduled within a specific date range.
    
    Args:
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        
    Returns:
        List of maintenance windows in the specified date range.
    """
    maintenance = get_maintenance_by_date_range(start_date, end_date, data_loader)
    
    if not maintenance:
        return f"No maintenance scheduled between {start_date} and {end_date}."
    
    response = [f"## 📅 MAINTENANCE SCHEDULE ({start_date} to {end_date})\n"]
    response.append(f"Found {len(maintenance)} maintenance windows\n")
    
    for m in maintenance:
        response.append(f"""
**Site:** {m.site_id}
**Type:** {m.maintenance_type}
**Start:** {m.start_time.strftime('%Y-%m-%d %H:%M:%S')}
**End:** {m.end_time.strftime('%Y-%m-%d %H:%M:%S')}
**Status:** {m.status}
**Priority:** {m.priority}
""")
    
    return "\n".join(response)


# Create the maintenance agent with Bedrock model
def create_maintenance_agent() -> Agent:
    """Create and return the maintenance agent with Bedrock model."""
    
    # Use Amazon Nova 2 Lite for maintenance agent (cost-effective for structured queries)
    model = BedrockModel(
        model_id="us.amazon.nova-lite-v1:0",
        temperature=0.3,  # Lower temperature for more consistent responses
        max_tokens=2048,
        # Enable extended thinking to show reasoning process
        additional_model_request_fields={
            "thinking": {
                "type": "enabled",
                "budget_tokens": 1024  # Allocate tokens for reasoning
            }
        }
    )
    
    agent = Agent(
        model=model,
        system_prompt=MAINTENANCE_SYSTEM_PROMPT,
        tools=[
            check_site_maintenance,
            check_all_ongoing_maintenance,
            check_maintenance_by_date_range,
        ],
    )
    
    return agent


if __name__ == "__main__":
    # Test the agent locally
    print("Testing Maintenance Agent with Bedrock...")
    print("\n" + "="*80 + "\n")
    
    agent = create_maintenance_agent()
    
    # Test query
    response = agent("Check maintenance for site_atlanta_001")
    print(response.message)

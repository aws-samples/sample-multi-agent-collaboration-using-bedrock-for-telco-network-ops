"""Alarm Agent - Strands implementation with Bedrock."""

import os
import sys
from pathlib import Path

from strands import Agent, tool
from strands.models import BedrockModel

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import DataLoader, S3DataLoader
from tools.alarm_tools import (
    get_alarms_by_site,
    get_alarms_by_severity,
    get_active_alarms,
    get_alarm_recommendation
)


# Initialize data loader based on environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
if ENVIRONMENT == "local":
    project_root = Path(__file__).parent.parent.parent
    data_loader = DataLoader(data_dir=str(project_root / "data"))
else:
    bucket_name = os.getenv("DATA_BUCKET_NAME")
    data_loader = S3DataLoader(bucket_name=bucket_name)


# System prompt for the alarm agent
ALARM_SYSTEM_PROMPT = """You are a specialized Network Alarm Monitoring Agent responsible for tracking and analyzing network alarms.

Your capabilities:
- Monitor active alarms across all network sites
- Analyze alarm severity and impact
- Provide recommendations based on alarm criticality
- Track alarm trends and patterns

Alarm Severity Levels:
- **Critical**: Service-affecting, requires immediate action
- **Major**: Significant impact, urgent attention needed
- **Minor**: Limited impact, should be addressed soon
- **Warning**: Informational, monitor for trends

When responding:
1. Always prioritize critical and major alarms
2. Provide clear severity counts and breakdowns
3. Include specific alarm details (type, description, affected services)
4. Give actionable recommendations based on severity
5. Highlight any patterns or concerning trends

Format your responses with:
- Clear severity indicators (🔴 Critical, 🟠 Major, 🟡 Minor, 🔵 Warning)
- Alarm counts by severity
- Detailed information for each alarm
- Specific recommendations for action
- Service impact assessment
"""


@tool
def check_site_alarms(site_id: str) -> str:
    """
    Check active alarms for a specific network site.
    
    Args:
        site_id: Site identifier (e.g., site_atlanta_001, site_dallas_003).
        
    Returns:
        Detailed alarm information including severity breakdown and recommendations.
    """
    result = get_alarms_by_site(site_id, data_loader)
    
    if "error" in result:
        return f"Error checking alarms for {site_id}: {result['error']}"
    
    if result["total_count"] == 0:
        return f"✅ No active alarms for {site_id}. All systems operating normally."
    
    response = []
    response.append(f"## 🚨 ACTIVE ALARMS for {site_id}\n")
    response.append(f"**Total:** {result['total_count']} active alarms")
    response.append(f"- 🔴 Critical: {result['critical_count']}")
    response.append(f"- 🟠 Major: {result['major_count']}")
    response.append(f"- 🟡 Minor: {result['minor_count']}")
    response.append(f"- 🔵 Warning: {result['warning_count']}\n")
    
    response.append("### ALARM DETAILS\n")
    for alarm in result["alarms"]:
        severity_icon = {
            "Critical": "🔴",
            "Major": "🟠",
            "Minor": "🟡",
            "Warning": "🔵"
        }.get(alarm.severity, "⚪")
        
        response.append(f"""
{severity_icon} **Alarm ID:** {alarm.alarm_id}
**Type:** {alarm.alarm_type}
**Severity:** {alarm.severity}
**Description:** {alarm.description}
**Start Time:** {alarm.start_time.strftime('%Y-%m-%d %H:%M:%S')}
**Affected Service:** {alarm.affected_service}
**Incident ID:** {alarm.incident_id}
""")
    
    # Add recommendation
    recommendation = get_alarm_recommendation(result)
    response.append(f"\n### RECOMMENDATION\n{recommendation}")
    
    return "\n".join(response)


@tool
def check_critical_alarms() -> str:
    """
    Check all critical alarms across all network sites.
    
    Returns:
        List of all critical severity alarms requiring immediate attention.
    """
    critical = get_alarms_by_severity("Critical", data_loader)
    
    if not critical:
        return "✅ No critical alarms at this time. All critical systems operating normally."
    
    response = [f"## 🔴 CRITICAL ALARMS ({len(critical)} active)\n"]
    response.append("⚠️ **IMMEDIATE ACTION REQUIRED**\n")
    
    for alarm in critical:
        response.append(f"""
**Site:** {alarm.site_id}
**Type:** {alarm.alarm_type}
**Description:** {alarm.description}
**Start Time:** {alarm.start_time.strftime('%Y-%m-%d %H:%M:%S')}
**Affected Service:** {alarm.affected_service}
**Incident ID:** {alarm.incident_id}
""")
    
    return "\n".join(response)


@tool
def check_all_active_alarms() -> str:
    """
    Check all active alarms across all network sites.
    
    Returns:
        Summary of all active alarms with severity breakdown and top priority items.
    """
    result = get_active_alarms(data_loader)
    
    if result["total_count"] == 0:
        return "✅ No active alarms across all sites. All systems operating normally."
    
    response = []
    response.append(f"## 🚨 ACTIVE ALARMS SUMMARY\n")
    response.append(f"**Total Active:** {result['total_count']}")
    response.append(f"- 🔴 Critical: {result['critical_count']}")
    response.append(f"- 🟠 Major: {result['major_count']}")
    response.append(f"- 🟡 Minor: {result['minor_count']}")
    response.append(f"- 🔵 Warning: {result['warning_count']}\n")
    
    # Show top 10 alarms by priority
    top_alarms = result["alarms"][:10]
    response.append("### TOP PRIORITY ALARMS\n")
    
    for alarm in top_alarms:
        severity_icon = {
            "Critical": "🔴",
            "Major": "🟠",
            "Minor": "🟡",
            "Warning": "🔵"
        }.get(alarm.severity, "⚪")
        
        response.append(f"""
{severity_icon} **{alarm.site_id}** - {alarm.alarm_type}
- Severity: {alarm.severity} | Service: {alarm.affected_service}
- Description: {alarm.description}
""")
    
    if result["total_count"] > 10:
        response.append(f"\n... and {result['total_count'] - 10} more alarms")
    
    # Add recommendation
    recommendation = get_alarm_recommendation(result)
    response.append(f"\n### RECOMMENDATION\n{recommendation}")
    
    return "\n".join(response)


# Create the alarm agent with Bedrock model
def create_alarm_agent() -> Agent:
    """Create and return the alarm agent with Bedrock model."""
    
    # Use Amazon Nova 2 Lite for alarm agent (cost-effective for monitoring queries)
    model = BedrockModel(
        model_id="us.amazon.nova-lite-v1:0",
        temperature=0.2,  # Very low temperature for consistent alarm reporting
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
        system_prompt=ALARM_SYSTEM_PROMPT,
        tools=[
            check_site_alarms,
            check_critical_alarms,
            check_all_active_alarms,
        ],
    )
    
    return agent


if __name__ == "__main__":
    # Test the agent locally
    print("Testing Alarm Agent with Bedrock...")
    print("\n" + "="*80 + "\n")
    
    agent = create_alarm_agent()
    
    # Test query
    response = agent("Show me all critical alarms")
    print(response.message)

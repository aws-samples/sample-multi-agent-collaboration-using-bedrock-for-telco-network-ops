"""KPI Agent - Strands implementation with Bedrock."""

import logging
import os
import sys
from pathlib import Path

from strands import Agent, tool
from strands.models import BedrockModel

logger = logging.getLogger("kpi_agent")
logger.setLevel(logging.DEBUG)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import DataLoader, S3DataLoader
from tools.kpi_tools import (
    get_kpis_by_site,
    get_kpis_by_metric,
    compare_sites,
    get_kpi_recommendation
)


# Initialize data loader based on environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
if ENVIRONMENT == "local":
    project_root = Path(__file__).parent.parent.parent
    data_loader = DataLoader(data_dir=str(project_root / "data"))
else:
    bucket_name = os.getenv("DATA_BUCKET_NAME")
    data_loader = S3DataLoader(bucket_name=bucket_name)


# System prompt for the KPI agent
KPI_SYSTEM_PROMPT = """You are a specialized Network Performance Analysis Agent responsible for analyzing KPIs and identifying performance issues.

Your capabilities:
- Analyze network performance metrics (throughput, latency, packet loss, CPU, memory)
- Identify performance anomalies and trends
- Compare performance across multiple sites
- Provide actionable recommendations for optimization

Key Performance Indicators:
- **Throughput (Mbps)**: Network data transfer rate
  - Excellent: >2000 Mbps
  - Good: >1000 Mbps
  - Average: <1000 Mbps
- **Latency (ms)**: Response time
  - Excellent: <15ms
  - Good: <20ms
  - Needs Attention: >20ms
  - Critical: >50ms
- **Packet Loss (%)**: Data loss rate
  - Minimal: <0.1%
  - Acceptable: <0.5%
  - High: >0.5%
  - Critical: >1.0%
- **CPU Utilization (%)**: Processing load
  - Warning: >80%
  - Critical: >90%
- **Memory Utilization (%)**: Memory usage
  - Warning: >80%
  - Critical: >90%

When responding:
1. Provide 24-hour average metrics with context
2. Identify and explain any anomalies detected
3. Analyze trends (improving, stable, degrading)
4. Give specific, actionable recommendations
5. Highlight performance concerns that need attention
6. When asked for deeper analysis, trend calculations, or visualizations,
   use the code_interpreter tool to run Python code (pandas, numpy, matplotlib)
   against the data for precise results
7. When the query mentions "chart", "graph", "plot", "visualization", or "trend",
   return the raw data in a structured format so the supervisor can generate
   an interactive Chart.js visualization for the frontend

Format your responses with:
- Clear metric summaries with performance ratings
- Detailed anomaly information with timestamps
- Trend analysis and insights
- Specific recommendations for optimization
- Comparison data when analyzing multiple sites
"""


@tool
def analyze_site_kpis(site_id: str) -> str:
    """
    Analyze KPI metrics for a specific network site.
    
    Args:
        site_id: Site identifier (e.g., site_atlanta_001, site_dallas_003).
        
    Returns:
        Comprehensive KPI analysis including averages, insights, and anomalies.
    """
    result = get_kpis_by_site(site_id, data_loader)
    
    if "error" in result:
        return f"Error analyzing KPIs for {site_id}: {result['error']}"
    
    response = []
    response.append(f"## 📊 KPI ANALYSIS for {site_id}\n")
    
    # Performance metrics
    avg = result["averages"]
    response.append("### PERFORMANCE METRICS (24-hour average)\n")
    response.append(f"- **Connected Users:** {avg['connected_users']:.0f}")
    response.append(f"- **Throughput:** {avg['throughput_mbps']:.2f} Mbps")
    response.append(f"- **Latency:** {avg['latency_ms']:.2f} ms")
    response.append(f"- **Packet Loss:** {avg['packet_loss_pct']:.3f}%")
    response.append(f"- **CPU Utilization:** {avg['cpu_utilization']:.2f}%")
    response.append(f"- **Memory Utilization:** {avg['memory_utilization']:.2f}%\n")
    
    # Insights
    response.append("### ANALYSIS INSIGHTS\n")
    for insight in result["insights"]:
        response.append(f"- {insight}")
    
    # Anomalies
    if result["anomaly_count"] > 0:
        response.append(f"\n### ⚠️ DETECTED ANOMALIES ({result['anomaly_count']})\n")
        for anomaly in result["anomalies"][:5]:  # Show first 5
            response.append(f"""
**Timestamp:** {anomaly.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
- Throughput: {anomaly.throughput_mbps:.2f} Mbps
- Latency: {anomaly.latency_ms:.2f} ms
- Packet Loss: {anomaly.packet_loss_pct:.3f}%
- CPU: {anomaly.cpu_utilization:.2f}%
- Memory: {anomaly.memory_utilization:.2f}%
""")
        
        if result["anomaly_count"] > 5:
            response.append(f"... and {result['anomaly_count'] - 5} more anomalies")
    else:
        response.append("\n✅ No anomalies detected in the last 24 hours")
    
    # Recommendation
    recommendation = get_kpi_recommendation(result)
    response.append(f"\n### RECOMMENDATION\n{recommendation}")
    
    return "\n".join(response)


@tool
def check_high_latency_sites() -> str:
    """
    Check for network sites experiencing high latency issues.
    
    Returns:
        List of sites with latency above acceptable thresholds.
    """
    high_latency_kpis = get_kpis_by_metric("latency", data_loader)
    
    if not high_latency_kpis:
        return "✅ No high latency issues detected across all sites."
    
    # Group by site
    sites_with_issues = {}
    for kpi in high_latency_kpis:
        if kpi.site_id not in sites_with_issues:
            sites_with_issues[kpi.site_id] = []
        sites_with_issues[kpi.site_id].append(kpi)
    
    response = [f"## ⚠️ HIGH LATENCY DETECTED ({len(sites_with_issues)} sites)\n"]
    
    for site_id, kpis in sites_with_issues.items():
        avg_latency = sum(k.latency_ms for k in kpis) / len(kpis)
        response.append(f"""
**Site:** {site_id}
- Average Latency: {avg_latency:.2f} ms (threshold: 50ms)
- Occurrences: {len(kpis)} in last 24 hours
""")
    
    response.append("\n### RECOMMENDATION")
    response.append("🔧 Investigate network paths and routing for affected sites")
    response.append("📊 Check for bandwidth congestion or hardware issues")
    
    return "\n".join(response)


@tool
def compare_site_performance(site_ids: str) -> str:
    """
    Compare performance metrics across multiple network sites.
    
    Args:
        site_ids: Comma-separated list of site identifiers (e.g., "site_atlanta_001,site_dallas_003").
        
    Returns:
        Comparative analysis of performance metrics across specified sites.
    """
    # Parse comma-separated site IDs
    site_list = [s.strip() for s in site_ids.split(",")]
    
    comparison = compare_sites(site_list, data_loader)
    
    if not comparison:
        return "Error: Unable to compare sites. Please check site IDs."
    
    response = [f"## 📊 SITE PERFORMANCE COMPARISON\n"]
    
    for site_id, data in comparison.items():
        if "error" in data:
            response.append(f"**{site_id}:** {data['error']}")
            continue
        
        avg = data["averages"]
        response.append(f"""
### {site_id}
- Throughput: {avg['throughput_mbps']:.2f} Mbps
- Latency: {avg['latency_ms']:.2f} ms
- Packet Loss: {avg['packet_loss_pct']:.3f}%
- CPU: {avg['cpu_utilization']:.2f}%
- Memory: {avg['memory_utilization']:.2f}%
- Anomalies: {data['anomaly_count']}
""")
    
    return "\n".join(response)


# Create the KPI agent with Bedrock model
def create_kpi_agent() -> Agent:
    """Create and return the KPI agent with Bedrock model.

    Includes AgentCore Code Interpreter for advanced data analysis
    when available (requires AWS credentials with Code Interpreter access).
    """
    
    # Use Amazon Nova 2 Lite for KPI agent (cost-effective for analysis)
    model = BedrockModel(
        model_id="us.amazon.nova-lite-v1:0",
        temperature=0.4,  # Moderate temperature for analytical insights
        max_tokens=3072,
    )

    tools = [
        analyze_site_kpis,
        check_high_latency_sites,
        compare_site_performance,
    ]

    # Add Code Interpreter for advanced analysis (optional)
    try:
        from strands_tools.code_interpreter import AgentCoreCodeInterpreter
        ci_region = os.getenv("AWS_REGION", "us-east-1")
        logger.info(f"  Initializing Code Interpreter (region={ci_region})...")
        code_interpreter = AgentCoreCodeInterpreter(region=ci_region)
        tools.append(code_interpreter.code_interpreter)
        logger.info("  ✓ Code Interpreter enabled for KPI agent")
    except ImportError as e:
        logger.warning(f"  Code Interpreter import failed: {e}")
        logger.warning("  Install: pip install strands-agents-tools")
    except Exception as e:
        logger.error(f"  Code Interpreter init FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    agent = Agent(
        model=model,
        system_prompt=KPI_SYSTEM_PROMPT,
        tools=tools,
    )
    
    return agent


if __name__ == "__main__":
    # Test the agent locally
    print("Testing KPI Agent with Bedrock...")
    print("\n" + "="*80 + "\n")
    
    agent = create_kpi_agent()
    
    # Test query
    response = agent("Analyze KPIs for site_atlanta_001")
    print(response.message)

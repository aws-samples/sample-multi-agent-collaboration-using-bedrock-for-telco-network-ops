"""Tools for KPI Agent."""

from typing import List, Dict, Any
from datetime import datetime, timedelta
import logging

from .data_loader import DataLoader
from .models import KPI

logger = logging.getLogger(__name__)


def get_kpis_by_site(site_id: str, data_loader: DataLoader) -> Dict[str, Any]:
    """
    Get KPI metrics for a specific site (last 24 records).
    
    Args:
        site_id: Site identifier.
        data_loader: Data loader instance.
        
    Returns:
        Dictionary with KPI metrics and analysis.
    """
    try:
        all_kpis = data_loader.load_kpis()
        site_kpis = [k for k in all_kpis if k.site_id == site_id]
        
        # Sort by timestamp descending, get last 24
        site_kpis.sort(key=lambda x: x.timestamp, reverse=True)
        recent_kpis = site_kpis[:24]
        
        if not recent_kpis:
            return {
                "site_id": site_id,
                "error": "No KPI data available"
            }
        
        # Calculate averages
        avg_throughput = sum(k.throughput_mbps for k in recent_kpis) / len(recent_kpis)
        avg_latency = sum(k.latency_ms for k in recent_kpis) / len(recent_kpis)
        avg_packet_loss = sum(k.packet_loss_pct for k in recent_kpis) / len(recent_kpis)
        avg_cpu = sum(k.cpu_utilization for k in recent_kpis) / len(recent_kpis)
        avg_memory = sum(k.memory_utilization for k in recent_kpis) / len(recent_kpis)
        avg_users = sum(k.connected_users for k in recent_kpis) / len(recent_kpis)
        
        # Identify anomalies
        anomalies = [k for k in recent_kpis if k.is_anomaly == "1"]
        
        # Generate insights
        insights = []
        
        if avg_throughput > 2000:
            insights.append("📈 Excellent throughput performance (>2000 Mbps)")
        elif avg_throughput > 1000:
            insights.append("✅ Good throughput performance (>1000 Mbps)")
        else:
            insights.append("📊 Average throughput performance")
        
        if avg_latency < 15:
            insights.append("⚡ Excellent latency (<15ms)")
        elif avg_latency < 20:
            insights.append("✅ Good latency (<20ms)")
        else:
            insights.append("⚠️ Latency needs attention (>20ms)")
        
        if avg_packet_loss < 0.1:
            insights.append("✅ Minimal packet loss (<0.1%)")
        elif avg_packet_loss < 0.5:
            insights.append("📊 Acceptable packet loss (<0.5%)")
        else:
            insights.append("⚠️ High packet loss (>0.5%)")
        
        if avg_cpu > 80:
            insights.append("⚠️ High CPU utilization (>80%)")
        
        if avg_memory > 80:
            insights.append("⚠️ High memory utilization (>80%)")
        
        return {
            "site_id": site_id,
            "averages": {
                "connected_users": round(avg_users, 0),
                "throughput_mbps": round(avg_throughput, 2),
                "latency_ms": round(avg_latency, 2),
                "packet_loss_pct": round(avg_packet_loss, 3),
                "cpu_utilization": round(avg_cpu, 2),
                "memory_utilization": round(avg_memory, 2)
            },
            "insights": insights,
            "anomalies": anomalies,
            "anomaly_count": len(anomalies),
            "data_points": len(recent_kpis)
        }
    except Exception as e:
        logger.error(f"Error getting KPIs for site {site_id}: {e}")
        return {
            "site_id": site_id,
            "error": str(e)
        }


def get_kpis_by_metric(metric_name: str, data_loader: DataLoader) -> List[KPI]:
    """
    Get KPI records filtered by metric threshold.
    
    Args:
        metric_name: Name of metric to filter (latency, packet_loss, etc.).
        data_loader: Data loader instance.
        
    Returns:
        List of KPI records exceeding threshold.
    """
    try:
        all_kpis = data_loader.load_kpis()
        
        # Filter based on metric thresholds
        if metric_name == "latency":
            return [k for k in all_kpis if k.latency_ms > 50]
        elif metric_name == "packet_loss":
            return [k for k in all_kpis if k.packet_loss_pct > 1.0]
        elif metric_name == "cpu":
            return [k for k in all_kpis if k.cpu_utilization > 80]
        elif metric_name == "memory":
            return [k for k in all_kpis if k.memory_utilization > 80]
        else:
            return all_kpis
    except Exception as e:
        logger.error(f"Error getting KPIs by metric {metric_name}: {e}")
        return []


def compare_sites(site_ids: List[str], data_loader: DataLoader) -> Dict[str, Any]:
    """
    Compare KPI metrics across multiple sites.
    
    Args:
        site_ids: List of site identifiers.
        data_loader: Data loader instance.
        
    Returns:
        Dictionary with comparison data for each site.
    """
    try:
        comparison = {}
        
        for site_id in site_ids:
            site_data = get_kpis_by_site(site_id, data_loader)
            comparison[site_id] = site_data
        
        return comparison
    except Exception as e:
        logger.error(f"Error comparing sites: {e}")
        return {}


def get_kpi_recommendation(kpi_data: Dict[str, Any]) -> str:
    """
    Generate recommendation based on KPI analysis.
    
    Args:
        kpi_data: KPI analysis data.
        
    Returns:
        Recommendation string.
    """
    anomaly_count = kpi_data.get("anomaly_count", 0)
    averages = kpi_data.get("averages", {})
    
    recommendations = []
    
    if anomaly_count > 5:
        recommendations.append("⚠️ Multiple anomalies detected - investigate immediately")
    
    if averages.get("latency_ms", 0) > 50:
        recommendations.append("🔧 High latency detected - check network paths")
    
    if averages.get("packet_loss_pct", 0) > 1.0:
        recommendations.append("🔧 Packet loss exceeds threshold - check connections")
    
    if averages.get("cpu_utilization", 0) > 80:
        recommendations.append("💻 High CPU usage - consider scaling resources")
    
    if averages.get("memory_utilization", 0) > 80:
        recommendations.append("💾 High memory usage - monitor for memory leaks")
    
    if not recommendations:
        recommendations.append("✅ All metrics within normal ranges")
    
    return " | ".join(recommendations)

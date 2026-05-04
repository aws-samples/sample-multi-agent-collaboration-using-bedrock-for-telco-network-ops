"""Tools for Alarm Agent."""

from typing import List, Dict, Any
from collections import Counter
import logging

from .data_loader import DataLoader
from .models import Alarm

logger = logging.getLogger(__name__)


def get_alarms_by_site(site_id: str, data_loader: DataLoader) -> Dict[str, Any]:
    """
    Get active alarms for a specific site.
    
    Args:
        site_id: Site identifier.
        data_loader: Data loader instance.
        
    Returns:
        Dictionary with alarm details and counts by severity.
    """
    try:
        all_alarms = data_loader.load_alarms()
        site_alarms = [
            a for a in all_alarms
            if a.site_id == site_id and a.status == "Active"
        ]
        
        # Count by severity
        severity_counts = Counter(a.severity for a in site_alarms)
        
        # Sort by priority (Critical first)
        site_alarms.sort(key=lambda x: x.priority_score(), reverse=True)
        
        return {
            "site_id": site_id,
            "alarms": site_alarms,
            "total_count": len(site_alarms),
            "critical_count": severity_counts.get("Critical", 0),
            "major_count": severity_counts.get("Major", 0),
            "minor_count": severity_counts.get("Minor", 0),
            "warning_count": severity_counts.get("Warning", 0)
        }
    except Exception as e:
        logger.error(f"Error getting alarms for site {site_id}: {e}")
        return {
            "site_id": site_id,
            "alarms": [],
            "total_count": 0,
            "error": str(e)
        }


def get_alarms_by_severity(severity: str, data_loader: DataLoader) -> List[Alarm]:
    """
    Get all active alarms of a specific severity.
    
    Args:
        severity: Alarm severity (Critical, Major, Minor, Warning).
        data_loader: Data loader instance.
        
    Returns:
        List of alarms with specified severity.
    """
    try:
        all_alarms = data_loader.load_alarms()
        filtered = [
            a for a in all_alarms
            if a.severity == severity and a.status == "Active"
        ]
        return filtered
    except Exception as e:
        logger.error(f"Error getting alarms by severity {severity}: {e}")
        return []


def get_active_alarms(data_loader: DataLoader) -> Dict[str, Any]:
    """
    Get all active alarms across all sites.
    
    Args:
        data_loader: Data loader instance.
        
    Returns:
        Dictionary with all active alarms and counts.
    """
    try:
        all_alarms = data_loader.load_alarms()
        active_alarms = [a for a in all_alarms if a.status == "Active"]
        
        # Count by severity
        severity_counts = Counter(a.severity for a in active_alarms)
        
        # Sort by priority
        active_alarms.sort(key=lambda x: x.priority_score(), reverse=True)
        
        return {
            "alarms": active_alarms,
            "total_count": len(active_alarms),
            "critical_count": severity_counts.get("Critical", 0),
            "major_count": severity_counts.get("Major", 0),
            "minor_count": severity_counts.get("Minor", 0),
            "warning_count": severity_counts.get("Warning", 0)
        }
    except Exception as e:
        logger.error(f"Error getting active alarms: {e}")
        return {
            "alarms": [],
            "total_count": 0,
            "error": str(e)
        }


def get_alarm_recommendation(severity_counts: Dict[str, int]) -> str:
    """
    Get recommendation based on alarm severity.
    
    Args:
        severity_counts: Dictionary with counts by severity.
        
    Returns:
        Recommendation string.
    """
    if severity_counts.get("critical_count", 0) > 0:
        return "⚠️ IMMEDIATE ACTION REQUIRED - Critical alarms detected"
    elif severity_counts.get("major_count", 0) > 0:
        return "⚡ URGENT ATTENTION NEEDED - Major alarms require prompt response"
    elif severity_counts.get("minor_count", 0) > 0:
        return "📋 Monitor the situation - Minor alarms should be addressed soon"
    else:
        return "✅ All systems operating normally - No critical issues detected"

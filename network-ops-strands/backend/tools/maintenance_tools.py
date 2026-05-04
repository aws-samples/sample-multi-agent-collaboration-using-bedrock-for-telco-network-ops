"""Tools for Maintenance Agent."""

from datetime import datetime
from typing import List, Dict, Any
import logging

from .data_loader import DataLoader
from .models import Maintenance

logger = logging.getLogger(__name__)


def get_maintenance_by_site(site_id: str, data_loader: DataLoader) -> Dict[str, Any]:
    """
    Get maintenance records for a specific site.
    
    Args:
        site_id: Site identifier.
        data_loader: Data loader instance.
        
    Returns:
        Dictionary with active and upcoming maintenance.
    """
    try:
        all_maintenance = data_loader.load_maintenance()
        site_maintenance = [m for m in all_maintenance if m.site_id == site_id]
        
        now = datetime.now()
        active = []
        upcoming = []
        
        for m in site_maintenance:
            if m.status == "In Progress":
                active.append(m)
            elif m.status == "Scheduled" and m.start_time > now:
                upcoming.append(m)
        
        # Sort upcoming by start time, show first 3
        upcoming.sort(key=lambda x: x.start_time)
        upcoming = upcoming[:3]
        
        return {
            "site_id": site_id,
            "active_maintenance": active,
            "upcoming_maintenance": upcoming,
            "total_count": len(site_maintenance)
        }
    except Exception as e:
        logger.error(f"Error getting maintenance for site {site_id}: {e}")
        return {
            "site_id": site_id,
            "active_maintenance": [],
            "upcoming_maintenance": [],
            "error": str(e)
        }


def get_ongoing_maintenance(data_loader: DataLoader) -> List[Maintenance]:
    """
    Get all ongoing maintenance across all sites.
    
    Args:
        data_loader: Data loader instance.
        
    Returns:
        List of ongoing maintenance records.
    """
    try:
        all_maintenance = data_loader.load_maintenance()
        ongoing = [m for m in all_maintenance if m.status == "In Progress"]
        return ongoing
    except Exception as e:
        logger.error(f"Error getting ongoing maintenance: {e}")
        return []


def get_maintenance_by_date_range(
    start_date: str,
    end_date: str,
    data_loader: DataLoader
) -> List[Maintenance]:
    """
    Get maintenance records within a date range.
    
    Args:
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        data_loader: Data loader instance.
        
    Returns:
        List of maintenance records in date range.
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        all_maintenance = data_loader.load_maintenance()
        filtered = [
            m for m in all_maintenance
            if start_dt <= m.start_time <= end_dt
        ]
        
        return filtered
    except Exception as e:
        logger.error(f"Error getting maintenance by date range: {e}")
        return []

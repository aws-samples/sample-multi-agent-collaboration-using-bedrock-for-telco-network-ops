"""Data models for network operations platform."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum


class AlarmSeverity(Enum):
    """Alarm severity levels."""
    CRITICAL = "Critical"
    MAJOR = "Major"
    MINOR = "Minor"
    WARNING = "Warning"


@dataclass
class Site:
    """Site data model."""
    site_id: str
    site_name: str
    location: str
    type: str
    commissioned_date: str
    status: str
    service_type: Optional[str] = None


@dataclass
class Maintenance:
    """Maintenance schedule data model."""
    maintenance_id: str
    site_id: str
    maintenance_type: str
    start_time: datetime
    end_time: datetime
    status: str
    priority: str
    description: str
    team: str
    requires_outage: str
    
    def time_remaining(self) -> Optional[int]:
        """
        Calculate minutes remaining for ongoing maintenance.
        
        Returns:
            Minutes remaining if maintenance is ongoing, None otherwise.
        """
        if self.status == "In Progress":
            now = datetime.now()
            if now < self.end_time:
                return int((self.end_time - now).total_seconds() / 60)
        return None


@dataclass
class Alarm:
    """Alarm data model."""
    alarm_id: str
    site_id: str
    alarm_type: str
    severity: str
    start_time: datetime
    end_time: Optional[datetime]
    status: str
    description: str
    affected_service: str
    incident_id: str
    
    def priority_score(self) -> int:
        """
        Calculate priority score for sorting alarms.
        
        Returns:
            Priority score (4=Critical, 3=Major, 2=Minor, 1=Warning, 0=Unknown).
        """
        severity_scores = {
            "Critical": 4,
            "Major": 3,
            "Minor": 2,
            "Warning": 1
        }
        return severity_scores.get(self.severity, 0)


@dataclass
class KPI:
    """KPI metrics data model."""
    kpi_id: str
    site_id: str
    timestamp: datetime
    location: str
    connected_users: int
    throughput_mbps: float
    latency_ms: float
    packet_loss_pct: float
    cpu_utilization: float
    memory_utilization: float
    is_anomaly: str
    
    def has_anomaly(self) -> bool:
        """
        Check if any metric exceeds threshold.
        
        Returns:
            True if anomaly detected, False otherwise.
        """
        return (
            self.latency_ms > 50 or
            self.packet_loss_pct > 1.0 or
            self.cpu_utilization > 80 or
            self.memory_utilization > 80
        )

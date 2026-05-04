"""Data loader for CSV files (local and S3)."""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import logging

from .models import Site, Maintenance, Alarm, KPI

logger = logging.getLogger(__name__)


class DataLoader:
    """Base data loader for CSV files."""
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize data loader.
        
        Args:
            data_dir: Directory containing CSV files.
        """
        self.data_dir = Path(data_dir)
    
    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        """Parse datetime string, return None if empty or invalid."""
        if not dt_str or dt_str.strip() == "":
            return None
        try:
            return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            logger.warning(f"Invalid datetime format: {dt_str}")
            return None
    
    def load_sites(self) -> List[Site]:
        """
        Load sites from CSV file.
        
        Returns:
            List of Site objects.
        """
        sites = []
        csv_file = self.data_dir / "sites.csv"
        
        try:
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    site = Site(
                        site_id=row['site_id'],
                        site_name=row['site_name'],
                        location=row['location'],
                        type=row['type'],
                        commissioned_date=row['commissioned_date'],
                        status=row['status'],
                        service_type=row.get('service_type')
                    )
                    sites.append(site)
            logger.info(f"Loaded {len(sites)} sites from {csv_file}")
        except FileNotFoundError:
            logger.error(f"Sites file not found: {csv_file}")
        except Exception as e:
            logger.error(f"Error loading sites: {e}")
        
        return sites
    
    def load_maintenance(self) -> List[Maintenance]:
        """
        Load maintenance schedules from CSV file.
        
        Returns:
            List of Maintenance objects.
        """
        maintenance_records = []
        csv_file = self.data_dir / "maintenance_schedule.csv"
        
        try:
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    start_time = self._parse_datetime(row['start_time'])
                    end_time = self._parse_datetime(row['end_time'])
                    
                    if start_time and end_time:
                        maintenance = Maintenance(
                            maintenance_id=row['maintenance_id'],
                            site_id=row['site_id'],
                            maintenance_type=row['maintenance_type'],
                            start_time=start_time,
                            end_time=end_time,
                            status=row['status'],
                            priority=row['priority'],
                            description=row['description'],
                            team=row['team'],
                            requires_outage=row['requires_outage']
                        )
                        maintenance_records.append(maintenance)
            logger.info(f"Loaded {len(maintenance_records)} maintenance records")
        except FileNotFoundError:
            logger.error(f"Maintenance file not found: {csv_file}")
        except Exception as e:
            logger.error(f"Error loading maintenance: {e}")
        
        return maintenance_records
    
    def load_alarms(self) -> List[Alarm]:
        """
        Load alarms from CSV file.
        
        Returns:
            List of Alarm objects.
        """
        alarms = []
        csv_file = self.data_dir / "alarms.csv"
        
        try:
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    start_time = self._parse_datetime(row['start_time'])
                    end_time = self._parse_datetime(row.get('end_time', ''))
                    
                    if start_time:
                        alarm = Alarm(
                            alarm_id=row['alarm_id'],
                            site_id=row['site_id'],
                            alarm_type=row['alarm_type'],
                            severity=row['severity'],
                            start_time=start_time,
                            end_time=end_time,
                            status=row['status'],
                            description=row['description'],
                            affected_service=row['affected_service'],
                            incident_id=row['incident_id']
                        )
                        alarms.append(alarm)
            logger.info(f"Loaded {len(alarms)} alarms")
        except FileNotFoundError:
            logger.error(f"Alarms file not found: {csv_file}")
        except Exception as e:
            logger.error(f"Error loading alarms: {e}")
        
        return alarms
    
    def load_kpis(self) -> List[KPI]:
        """
        Load KPI metrics from CSV file.
        
        Returns:
            List of KPI objects.
        """
        kpis = []
        csv_file = self.data_dir / "kpi_metrics.csv"
        
        try:
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    timestamp = self._parse_datetime(row['timestamp'])
                    
                    if timestamp:
                        kpi = KPI(
                            kpi_id=row['kpi_id'],
                            site_id=row['site_id'],
                            timestamp=timestamp,
                            location=row['location'],
                            connected_users=int(row['connected_users']),
                            throughput_mbps=float(row['throughput_mbps']),
                            latency_ms=float(row['latency_ms']),
                            packet_loss_pct=float(row['packet_loss_pct']),
                            cpu_utilization=float(row['cpu_utilization']),
                            memory_utilization=float(row['memory_utilization']),
                            is_anomaly=row['is_anomaly']
                        )
                        kpis.append(kpi)
            logger.info(f"Loaded {len(kpis)} KPI records")
        except FileNotFoundError:
            logger.error(f"KPI file not found: {csv_file}")
        except Exception as e:
            logger.error(f"Error loading KPIs: {e}")
        
        return kpis


class S3DataLoader(DataLoader):
    """Data loader for S3-stored CSV files."""
    
    def __init__(self, bucket_name: str, prefix: str = ""):
        """
        Initialize S3 data loader.
        
        Args:
            bucket_name: S3 bucket name.
            prefix: S3 key prefix for data files (empty = root of bucket).
        """
        self.bucket_name = bucket_name
        self.prefix = prefix
        self._cache = {}
        
        try:
            import boto3
            self.s3_client = boto3.client('s3')
        except ImportError:
            logger.error("boto3 not installed. Install with: pip install boto3")
            raise
    
    def _download_file(self, filename: str) -> str:
        """
        Download file from S3 to local temp directory.
        
        Args:
            filename: Name of the file to download.
            
        Returns:
            Path to downloaded file.
        """
        import tempfile
        
        cache_key = f"{self.bucket_name}/{self.prefix}/{filename}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        s3_key = f"{self.prefix}/{filename}" if self.prefix else filename
        temp_dir = Path(tempfile.gettempdir()) / "netops_data"
        temp_dir.mkdir(exist_ok=True)
        local_path = temp_dir / filename
        
        try:
            self.s3_client.download_file(self.bucket_name, s3_key, str(local_path))
            self._cache[cache_key] = str(local_path)
            logger.info(f"Downloaded {s3_key} from S3")
            return str(local_path)
        except Exception as e:
            logger.error(f"Error downloading {s3_key} from S3: {e}")
            raise
    
    def load_sites(self) -> List[Site]:
        """Load sites from S3."""
        local_file = self._download_file("sites.csv")
        self.data_dir = Path(local_file).parent
        return super().load_sites()
    
    def load_maintenance(self) -> List[Maintenance]:
        """Load maintenance from S3."""
        local_file = self._download_file("maintenance_schedule.csv")
        self.data_dir = Path(local_file).parent
        return super().load_maintenance()
    
    def load_alarms(self) -> List[Alarm]:
        """Load alarms from S3."""
        local_file = self._download_file("alarms.csv")
        self.data_dir = Path(local_file).parent
        return super().load_alarms()
    
    def load_kpis(self) -> List[KPI]:
        """Load KPIs from S3."""
        local_file = self._download_file("kpi_metrics.csv")
        self.data_dir = Path(local_file).parent
        return super().load_kpis()

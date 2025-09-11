import json
import boto3
import csv
import io
import os
import random
import uuid
from datetime import datetime, timedelta
import cfnresponse

def lambda_handler(event, context):
    if event['RequestType'] == 'Create' or event['RequestType'] == 'Update':
        try:
            s3 = boto3.client('s3')
            bucket_name = os.environ['BUCKET_NAME']
            
            # Generate synthetic data and upload to S3
            generate_synthetic_data(s3, bucket_name)
            
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
        except Exception as e:
            print(f"Error: {str(e)}")
            cfnresponse.send(event, context, cfnresponse.FAILED, {'Error': str(e)})
    else:
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {})

def generate_synthetic_data(s3, bucket_name):
    """Generate synthetic network operations data and upload to S3"""
    try:
        # Check if data already exists
        try:
            s3.head_object(Bucket=bucket_name, Key='data/sites.csv')
            print("Data already exists, skipping generation")
            return
        except:
            print("Generating synthetic data")
            # Create data directory if it doesn't exist
            try:
                s3.put_object(Bucket=bucket_name, Key='data/', Body='')
            except:
                pass
    
        # Generate sites data
        sites = generate_site_data()
        sites_csv = convert_to_csv(sites)
        s3.put_object(Bucket=bucket_name, Key='data/sites.csv', Body=sites_csv)
        print(f"Generated {len(sites)} sites")
        
        # Generate maintenance schedule
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now() + timedelta(days=30)
        maintenance = generate_maintenance_schedule(sites, start_date, end_date)
        maintenance_csv = convert_to_csv(maintenance)
        s3.put_object(Bucket=bucket_name, Key='data/maintenance_schedule.csv', Body=maintenance_csv)
        print(f"Generated {len(maintenance)} maintenance records")
        
        # Generate alarms
        alarms = generate_alarm_data(sites, start_date, end_date)
        alarms_csv = convert_to_csv(alarms)
        s3.put_object(Bucket=bucket_name, Key='data/alarms.csv', Body=alarms_csv)
        print(f"Generated {len(alarms)} alarms")
        
        # Generate KPI metrics
        kpi_metrics = generate_kpi_data(sites, start_date, end_date)
        kpi_csv = convert_to_csv(kpi_metrics)
        s3.put_object(Bucket=bucket_name, Key='data/kpi_metrics.csv', Body=kpi_csv)
        print(f"Generated {len(kpi_metrics)} KPI metrics")
        
    except Exception as e:
        print(f"Error generating synthetic data: {str(e)}")
        raise

def generate_site_data():
    """Generate basic site information"""
    sites = []
    locations = ['Dallas', 'Birmingham', 'Atlanta', 'Ridgeland']
    site_types = ['macro', 'micro', 'small']
    
    for location in locations:
        for i in range(1, 6):  # 5 sites per location
            site = {
                'site_id': f"site_{location.lower()}_{i:03d}",
                'location': location,
                'type': random.choice(site_types),
                'latitude': str(random.uniform(-47, -35)),
                'longitude': str(random.uniform(166, 178)),
                'vendor': random.choice(['Ericsson', 'Nokia', 'Huawei']),
                'commissioning_date': (datetime.now() - timedelta(days=random.randint(100, 1000))).strftime('%Y-%m-%d')
            }
            sites.append(site)
    
    return sites

def generate_maintenance_schedule(sites, start_date, end_date):
    """Generate maintenance schedule data"""
    maintenance_data = []
    maintenance_types = [
        'Planned Maintenance',
        'Software Upgrade',
        'Hardware Replacement',
        'Network Optimization',
        'Emergency Maintenance'
    ]
    
    for site in sites:
        # Generate 2-3 maintenance windows per site
        for i in range(random.randint(2, 3)):
            start = start_date + timedelta(days=random.randint(0, 30))
            duration_hours = random.randint(2, 6)
            
            maintenance = {
                'maintenance_id': f"MNT-{str(uuid.uuid4())[:8]}",
                'site_id': site['site_id'],
                'maintenance_type': random.choice(maintenance_types),
                'start_time': start.strftime('%Y-%m-%d %H:%M:%S'),
                'end_time': (start + timedelta(hours=duration_hours)).strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'Scheduled',
                'priority': random.choice(['High', 'Medium', 'Low']),
                'description': f"Scheduled {random.choice(maintenance_types)} for {site['site_id']}",
                'team': random.choice(['Team A', 'Team B', 'Team C']),
                'requires_outage': str(random.choice([True, False])).lower()
            }
            maintenance_data.append(maintenance)
    
    return maintenance_data

def generate_alarm_data(sites, start_date, end_date):
    """Generate alarm data"""
    alarm_data = []
    alarm_types = [
        ('SITE_DOWN', 'Critical'),
        ('HIGH_TEMPERATURE', 'Major'),
        ('POWER_ISSUE', 'Major'),
        ('HARDWARE_FAULT', 'Major'),
        ('CONNECTIVITY_ISSUE', 'Minor'),
        ('SOFTWARE_ERROR', 'Minor')
    ]
    
    for site in sites:
        # Generate random number of alarms per site
        num_alarms = random.randint(3, 8)
        for i in range(num_alarms):
            alarm_type, severity = random.choice(alarm_types)
            start = start_date + timedelta(days=random.randint(0, 30))
            
            # Some alarms are active, some are cleared
            status = random.choice(['Active', 'Cleared'])
            end_time = (start + timedelta(hours=random.randint(1, 24))).strftime('%Y-%m-%d %H:%M:%S') if status == 'Cleared' else None
            
            alarm = {
                'alarm_id': f"ALM-{str(uuid.uuid4())[:8]}",
                'site_id': site['site_id'],
                'alarm_type': alarm_type,
                'severity': severity,
                'start_time': start.strftime('%Y-%m-%d %H:%M:%S'),
                'end_time': end_time,
                'status': status,
                'description': f"{alarm_type} detected on {site['site_id']}",
                'affected_service': random.choice(['Voice', 'Data', 'Both']),
                'incident_id': f"INC{random.randint(10000, 99999)}"
            }
            alarm_data.append(alarm)
    
    return alarm_data

def generate_kpi_data(sites, start_date, end_date):
    """Generate KPI metrics data"""
    kpi_data = []
    current_time = start_date
    
    while current_time <= end_date:
        for site in sites:
            # Only generate hourly data for the last 48 hours to keep the dataset manageable
            if current_time >= datetime.now() - timedelta(hours=48):
                # Base metrics with daily patterns
                hour = current_time.hour
                base_traffic = 1000 + 500 * (hour / 12)  # Simplified pattern
                
                # Add some randomness and occasional anomalies
                is_anomaly = random.random() < 0.05  # 5% chance of anomaly
                anomaly_multiplier = 3 if is_anomaly else 1
                
                kpi = {
                    'site_id': site['site_id'],
                    'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'location': site['location'],
                    'connected_users': str(int(base_traffic * 0.1 * random.uniform(0.8, 1.2) * anomaly_multiplier)),
                    'throughput_mbps': str(base_traffic * random.uniform(0.8, 1.2) * anomaly_multiplier),
                    'latency_ms': str(20 + random.uniform(-5, 5) * anomaly_multiplier),
                    'packet_loss_pct': str(0.1 + random.uniform(-0.05, 0.05) * anomaly_multiplier),
                    'cpu_utilization': str(50 + random.uniform(-10, 10) * anomaly_multiplier),
                    'memory_utilization': str(60 + random.uniform(-10, 10) * anomaly_multiplier),
                    'is_anomaly': '1' if is_anomaly else '0'
                }
                kpi_data.append(kpi)
        
        current_time += timedelta(hours=1)
    
    return kpi_data

def convert_to_csv(data):
    """Convert list of dictionaries to CSV string"""
    if not data:
        return ""
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    return output.getvalue()

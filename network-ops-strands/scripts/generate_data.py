#!/usr/bin/env python3
"""
Synthetic data generator for Network Operations Platform.
Generates realistic CSV data for sites, maintenance, alarms, and KPIs.
"""

import argparse
import csv
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

# Data center locations (10 cities, 2 sites each = 20 sites)
DC_LOCATIONS = [
    "Atlanta GA", "Dallas TX", "Chicago IL", "Richmond VA",
    "Phoenix AZ", "Ashburn VA", "Piscataway NJ", "Sacramento CA",
    "Irving TX", "Suwanee GA"
]

# Site types and vendors
SITE_TYPES = ["macro", "micro", "small"]
VENDORS = ["Ericsson", "Nokia", "Huawei"]

# Maintenance types
MAINTENANCE_TYPES = [
    "Planned Maintenance", "Software Upgrade", "Hardware Replacement",
    "Network Optimization", "Emergency Maintenance"
]

# Alarm types with severity
ALARM_TYPES = {
    "SITE_DOWN": "Critical",
    "HIGH_TEMPERATURE": "Major",
    "POWER_ISSUE": "Major",
    "HARDWARE_FAULT": "Major",
    "CONNECTIVITY_ISSUE": "Minor",
    "SOFTWARE_ERROR": "Minor"
}

# Service types
SERVICE_TYPES = ["Colocation", "Cloud Connectivity", "Managed Services"]


def generate_sites(num_sites: int, profile: str, output_dir: Path) -> List[Dict]:
    """Generate sites data."""
    sites = []
    locations = DC_LOCATIONS
    sites_per_location = max(1, num_sites // len(locations))
    
    site_id = 1
    for location in locations:
        for i in range(sites_per_location):
            if site_id > num_sites:
                break
            
            location_key = location.split()[0].lower()
            site = {
                "site_id": f"site_{location_key}_{site_id:03d}",
                "site_name": f"{location} DC {i+1}",
                "location": location,
                "type": random.choice(SITE_TYPES),
                "commissioned_date": (
                    datetime.now() - timedelta(days=random.randint(100, 1000))
                ).strftime("%Y-%m-%d"),
                "status": "Active",
                "service_type": random.choice(SERVICE_TYPES),
            }
            
            sites.append(site)
            site_id += 1
    
    # Write to CSV
    output_file = output_dir / "sites.csv"
    fieldnames = list(sites[0].keys())
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sites)
    
    print(f"✓ Generated {len(sites)} sites -> {output_file}")
    return sites


def generate_maintenance(sites: List[Dict], output_dir: Path) -> None:
    """Generate maintenance schedule data."""
    maintenance_records = []
    now = datetime.now()
    
    for site in sites:
        # Generate 2-3 maintenance windows per site
        num_maintenance = random.randint(2, 3)
        
        for _ in range(num_maintenance):
            start_time = now + timedelta(
                days=random.randint(-10, 30),
                hours=random.randint(0, 23)
            )
            duration_hours = random.randint(2, 6)
            end_time = start_time + timedelta(hours=duration_hours)
            
            # Determine status based on time
            # Force some to be "In Progress" for testing
            if end_time < now:
                status = "Completed"
            elif start_time <= now <= end_time:
                status = "In Progress"
            else:
                status = "Scheduled"
            
            # Force 20% of future maintenance to be "In Progress" for demo
            if status == "Scheduled" and random.random() < 0.2:
                # Adjust times to make it ongoing
                start_time = now - timedelta(hours=random.randint(1, 3))
                end_time = now + timedelta(hours=random.randint(1, 4))
                status = "In Progress"
            
            maintenance = {
                "maintenance_id": f"MNT-{uuid.uuid4().hex[:8]}",
                "site_id": site["site_id"],
                "maintenance_type": random.choice(MAINTENANCE_TYPES),
                "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
                "status": status,
                "priority": random.choice(["High", "Medium", "Low"]),
                "description": f"Scheduled {random.choice(MAINTENANCE_TYPES)} "
                              f"for {site['site_id']}",
                "team": random.choice(["Team A", "Team B", "Team C"]),
                "requires_outage": random.choice(["true", "false"])
            }
            maintenance_records.append(maintenance)
    
    # Write to CSV
    output_file = output_dir / "maintenance_schedule.csv"
    fieldnames = list(maintenance_records[0].keys())
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(maintenance_records)
    
    print(f"✓ Generated {len(maintenance_records)} maintenance records -> {output_file}")


def generate_alarms(sites: List[Dict], output_dir: Path) -> None:
    """Generate alarms data."""
    alarm_records = []
    now = datetime.now()
    
    for site in sites:
        # Generate 3-8 alarms per site
        num_alarms = random.randint(3, 8)
        
        for _ in range(num_alarms):
            alarm_type = random.choice(list(ALARM_TYPES.keys()))
            severity = ALARM_TYPES[alarm_type]
            
            start_time = now - timedelta(
                days=random.randint(0, 7),
                hours=random.randint(0, 23)
            )
            
            # 70% of alarms are cleared
            status = "Cleared" if random.random() < 0.7 else "Active"
            end_time = ""
            
            if status == "Cleared":
                end_time = (start_time + timedelta(
                    hours=random.randint(1, 48)
                )).strftime("%Y-%m-%d %H:%M:%S")
            
            alarm = {
                "alarm_id": f"ALM-{uuid.uuid4().hex[:8]}",
                "site_id": site["site_id"],
                "alarm_type": alarm_type,
                "severity": severity,
                "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_time,
                "status": status,
                "description": f"{alarm_type} detected on {site['site_id']}",
                "affected_service": random.choice(["Voice", "Data", "Both"]),
                "incident_id": f"INC{random.randint(10000, 99999)}"
            }
            alarm_records.append(alarm)
    
    # Write to CSV
    output_file = output_dir / "alarms.csv"
    fieldnames = list(alarm_records[0].keys())
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(alarm_records)
    
    print(f"✓ Generated {len(alarm_records)} alarm records -> {output_file}")


def generate_kpis(sites: List[Dict], output_dir: Path) -> None:
    """Generate KPI metrics data."""
    kpi_records = []
    now = datetime.now()
    
    # Generate hourly data for last 48 hours
    for site in sites:
        for hour_offset in range(48):
            timestamp = now - timedelta(hours=hour_offset)
            
            # Base metrics with daily patterns (higher during business hours)
            hour = timestamp.hour
            business_multiplier = 1.5 if 8 <= hour <= 18 else 1.0
            
            # 5% chance of anomaly
            is_anomaly = random.random() < 0.05
            anomaly_multiplier = 3.0 if is_anomaly else 1.0
            
            kpi = {
                "kpi_id": f"KPI-{uuid.uuid4().hex[:8]}",
                "site_id": site["site_id"],
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "location": site["location"],
                "connected_users": int(random.randint(50, 200) * business_multiplier),
                "throughput_mbps": round(
                    random.uniform(500, 2000) * business_multiplier, 2
                ),
                "latency_ms": round(
                    random.uniform(5, 25) * anomaly_multiplier, 2
                ),
                "packet_loss_pct": round(
                    random.uniform(0.01, 0.5) * anomaly_multiplier, 3
                ),
                "cpu_utilization": round(random.uniform(30, 85), 2),
                "memory_utilization": round(random.uniform(40, 80), 2),
                "is_anomaly": "1" if is_anomaly else "0"
            }
            kpi_records.append(kpi)
    
    # Write to CSV
    output_file = output_dir / "kpi_metrics.csv"
    fieldnames = list(kpi_records[0].keys())
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kpi_records)
    
    print(f"✓ Generated {len(kpi_records)} KPI records -> {output_file}")


def generate_knowledge_base(sites: List[Dict], output_dir: Path) -> None:
    """Generate troubleshooting articles and incident tickets for the knowledge base."""
    kb_dir = output_dir / "knowledge-base"
    articles_dir = kb_dir / "articles"
    tickets_dir = kb_dir / "tickets"
    articles_dir.mkdir(parents=True, exist_ok=True)
    tickets_dir.mkdir(parents=True, exist_ok=True)

    # --- Troubleshooting Articles ---
    articles = [
        {
            "filename": "power-outage-recovery.md",
            "title": "Power Outage Recovery Procedures",
            "category": "Power",
            "content": """## Overview
Standard procedures for recovering network sites after utility power restoration.

## Immediate Actions (First 15 Minutes)
1. Verify utility power is stable and voltage levels are normal
2. Check UPS switched back to utility power and review battery status
3. Follow proper power-on sequence: core devices first, then edge

## Recovery Steps
- Verify all PDUs operational and circuit breakers in correct position
- Confirm HVAC running and temperature sensors normal
- Verify routers/switches boot successfully and routing protocols converge
- Test end-to-end connectivity and validate backup paths

## Common Issues
- Equipment fails to power on: check connections, breakers, try different source
- Services don't auto-start: manually start, check for config corruption
- Performance degradation: may be battery charging load or thermal issues

## Escalation
Contact vendor support if equipment fails to power on after 30 minutes or unusual errors in logs.""",
        },
        {
            "filename": "site-down-troubleshooting.md",
            "title": "Site Down Troubleshooting Guide",
            "category": "Connectivity",
            "content": """## Overview
Step-by-step guide for diagnosing and resolving complete site outages.

## Initial Triage (First 5 Minutes)
1. Check if site responds to ICMP ping
2. Verify physical layer: fiber light levels, copper link status
3. Check power status via remote PDU or UPS management
4. Review recent change history for the site

## Diagnostic Decision Tree
- **No ping response + no power**: Power outage — check utility status, UPS
- **No ping response + power OK**: Network issue — check fiber, routing
- **Partial response**: Degraded — check individual services, interfaces
- **Intermittent**: Flapping — check for loose connections, environmental

## External Factor Checks
- Check utility power outage maps for the area
- Check 811 dig request database for nearby excavation
- Check weather conditions for severe weather impact
- Check for scheduled utility maintenance

## Resolution Procedures
1. For power outages: follow Power Outage Recovery Procedures
2. For fiber cuts: dispatch field tech, coordinate emergency repair
3. For equipment failure: attempt remote restart, dispatch if needed
4. For environmental: address root cause (cooling, flooding, etc.)""",
        },
        {
            "filename": "high-latency-diagnosis.md",
            "title": "High Latency Diagnosis and Resolution",
            "category": "Performance",
            "content": """## Overview
Guide for diagnosing and resolving high network latency issues.

## Normal Baselines
- Intra-site latency: < 5ms
- Cross-city latency: < 20ms
- Cross-region latency: < 50ms

## Diagnostic Steps
1. Run traceroute to identify where latency is introduced
2. Check interface utilization — congestion causes queuing delay
3. Review QoS policies — misconfig can cause priority inversion
4. Check for packet loss — retransmissions add perceived latency
5. Verify MTU settings — fragmentation adds overhead

## Common Causes
- **Interface saturation**: Upgrade link or implement traffic shaping
- **CPU overload on router**: Check routing table size, reduce OSPF areas
- **Duplex mismatch**: Verify auto-negotiation or set fixed duplex
- **DNS resolution delays**: Check DNS server response times
- **Asymmetric routing**: Verify return path matches forward path

## Resolution
- For congestion: implement QoS, upgrade bandwidth, or redistribute traffic
- For equipment: replace failing hardware, update firmware
- For configuration: correct MTU, duplex, QoS settings""",
        },
        {
            "filename": "fiber-cut-response.md",
            "title": "Fiber Cut Emergency Response Procedures",
            "category": "Connectivity",
            "content": """## Overview
Emergency procedures for responding to fiber optic cable damage.

## Detection
- Loss of light on fiber interfaces (no Rx power)
- Multiple sites affected along same fiber route
- 811 dig request alerts for nearby excavation activity

## Immediate Response
1. Confirm fiber cut via OTDR testing or field inspection
2. Check 811 database for active excavation permits nearby
3. Dispatch field technician to suspected damage location
4. Notify affected customers of outage and estimated repair time

## Repair Process
1. Locate exact break point (OTDR or visual inspection)
2. Perform emergency fusion splice for quick restoration
3. Test splice loss (should be < 0.1 dB)
4. Complete permanent repair with proper enclosure
5. Install additional protective conduit if needed

## Prevention
- Monitor 811 dig request database for permits near fiber routes
- Conduct pre-excavation site visits for high-risk areas
- Maintain accurate fiber route documentation with GPS coordinates
- Install warning markers above buried fiber""",
        },
        {
            "filename": "hvac-failure-procedures.md",
            "title": "HVAC Failure and Thermal Management",
            "category": "Environmental",
            "content": """## Overview
Procedures for managing site cooling failures and thermal events.

## Temperature Thresholds
- Normal operating: 64-75°F (18-24°C)
- Warning: 75-85°F (24-29°C) — reduce non-critical load
- Critical: 85-95°F (29-35°C) — begin controlled shutdown
- Emergency: >95°F (>35°C) — immediate shutdown to prevent damage

## Immediate Actions
1. Verify HVAC unit status (running, fault codes)
2. Check thermostat settings and sensor readings
3. Open cabinet doors to improve airflow as temporary measure
4. Reduce load by shutting down non-critical equipment

## Troubleshooting
- **Unit not running**: Check power supply, breakers, control board
- **Running but not cooling**: Check refrigerant levels, compressor
- **Uneven cooling**: Check airflow, blocked vents, hot/cold aisle containment
- **Frequent cycling**: Check thermostat, dirty filters, low refrigerant

## Escalation
- If temperature exceeds 85°F: notify site manager immediately
- If temperature exceeds 95°F: begin emergency shutdown procedures
- Contact HVAC vendor for emergency service call""",
        },
        {
            "filename": "network-congestion-management.md",
            "title": "Network Congestion Management Guide",
            "category": "Performance",
            "content": """## Overview
Guide for identifying and resolving network congestion issues.

## Indicators of Congestion
- Interface utilization consistently > 80%
- Increasing packet drops on interface counters
- Rising latency correlated with traffic volume
- QoS queue drops in monitoring

## Diagnostic Steps
1. Check interface utilization graphs for peak patterns
2. Identify top talkers using NetFlow/sFlow data
3. Review QoS policy effectiveness
4. Check for broadcast storms or routing loops

## Short-term Mitigation
- Apply rate limiting to non-critical traffic
- Adjust QoS priorities to protect critical services
- Redistribute traffic across available paths
- Enable traffic compression where supported

## Long-term Solutions
- Upgrade link capacity (10G to 100G, etc.)
- Implement ECMP for load distribution
- Deploy CDN for content-heavy traffic
- Redesign network topology for better traffic flow""",
        },
    ]

    for article in articles:
        content = f"""# {article['title']}

**Category**: {article['category']}
**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}
**Document Type**: article

{article['content']}
"""
        (articles_dir / article["filename"]).write_text(content)

    print(f"   📚 Generated {len(articles)} troubleshooting articles")

    # --- Incident Tickets ---
    issue_templates = [
        {
            "type": "POWER_ISSUE",
            "title": "Site offline during utility power outage",
            "cause": "Utility power outage caused by {cause}",
            "causes": [
                "equipment failure at local substation",
                "severe thunderstorm damaging power lines",
                "scheduled utility maintenance without prior notification",
                "vehicle collision with power pole",
                "transformer failure due to overload",
            ],
            "resolution": "Power restored by utility company. All equipment recovered automatically via UPS failover.",
            "duration_hours": (1, 4),
            "category": "Power",
        },
        {
            "type": "CONNECTIVITY_ISSUE",
            "title": "Fiber cut causing complete connectivity loss",
            "cause": "Fiber optic cable damaged by {cause}",
            "causes": [
                "excavation contractor during water main repair",
                "road construction crew",
                "storm debris falling on aerial fiber",
                "rodent damage in underground conduit",
                "accidental damage during building renovation",
            ],
            "resolution": "Emergency fiber splice performed. Permanent repair and additional conduit protection installed.",
            "duration_hours": (3, 8),
            "category": "Connectivity",
        },
        {
            "type": "HIGH_TEMPERATURE",
            "title": "HVAC failure causing thermal alarm",
            "cause": "Cooling system failure due to {cause}",
            "causes": [
                "compressor failure",
                "refrigerant leak",
                "clogged air filters reducing airflow",
                "control board malfunction",
                "power supply failure to HVAC unit",
            ],
            "resolution": "HVAC unit repaired/replaced. Temperature returned to normal operating range.",
            "duration_hours": (2, 6),
            "category": "Environmental",
        },
        {
            "type": "HARDWARE_FAULT",
            "title": "Network equipment failure requiring replacement",
            "cause": "Hardware failure: {cause}",
            "causes": [
                "switch line card failure",
                "router power supply failure",
                "SFP transceiver malfunction",
                "memory error causing repeated crashes",
                "fan failure leading to thermal shutdown",
            ],
            "resolution": "Failed component replaced with spare. Configuration restored from backup.",
            "duration_hours": (1, 5),
            "category": "Hardware",
        },
        {
            "type": "SOFTWARE_ERROR",
            "title": "Software bug causing service degradation",
            "cause": "Software issue: {cause}",
            "causes": [
                "firmware bug causing memory leak after update",
                "routing protocol flap due to timer misconfiguration",
                "ACL rule conflict blocking legitimate traffic",
                "DHCP pool exhaustion",
                "certificate expiration causing authentication failures",
            ],
            "resolution": "Configuration corrected / firmware rolled back. Services restored.",
            "duration_hours": (0.5, 3),
            "category": "Software",
        },
    ]

    ticket_num = 1
    site_ids = [s["site_id"] for s in sites]
    now = datetime.now()

    for template in issue_templates:
        # Generate 2-3 tickets per issue type
        count = random.randint(2, 3)
        for _ in range(count):
            site_id = random.choice(site_ids)
            cause = random.choice(template["causes"])
            days_ago = random.randint(7, 180)
            incident_date = now - timedelta(days=days_ago)
            dur_min, dur_max = template["duration_hours"]
            duration_h = round(random.uniform(dur_min, dur_max), 1)
            ticket_id = f"INC-{incident_date.year}-{ticket_num:03d}"
            customers = random.randint(10, 80)

            content = f"""# Incident Ticket: {ticket_id}

**Ticket ID**: {ticket_id}
**Site ID**: {site_id}
**Document Type**: ticket
**Category**: {template['category']}
**Status**: Resolved
**Resolved Date**: {incident_date.strftime('%Y-%m-%d')}

## Incident Summary
{template['title']} at {site_id}.

## Root Cause
{template['cause'].format(cause=cause)}

## Resolution
{template['resolution']}

## Resolution Time
**Total Duration**: {duration_h} hours

## Impact Assessment
- **Services Affected**: All services at {site_id}
- **Customers Impacted**: {customers}
- **Data Loss**: None

## Lessons Learned
- Detection was timely via automated monitoring
- Resolution followed standard operating procedures
- Consider preventive measures to reduce recurrence

## Related Knowledge Base Articles
- {template['category']} troubleshooting procedures
"""
            fname = f"{ticket_id.lower().replace(' ', '-')}-{template['type'].lower().replace('_', '-')}.md"
            (tickets_dir / fname).write_text(content)
            ticket_num += 1

    total_tickets = ticket_num - 1
    print(f"   🎫 Generated {total_tickets} incident tickets")


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic network operations data"
    )
    parser.add_argument(
        "--sites",
        type=int,
        default=20,
        help="Number of sites to generate (default: 20)"
    )
    parser.add_argument(
        "--profile",
        choices=["datacenter", "generic"],
        default="datacenter",
        help="Company profile for data generation (default: datacenter)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data",
        help="Output directory for CSV files (default: data)"
    )
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n🚀 Generating synthetic data...")
    print(f"   Profile: {args.profile}")
    print(f"   Sites: {args.sites}")
    print(f"   Output: {output_dir}\n")
    
    # Generate data
    sites = generate_sites(args.sites, args.profile, output_dir)
    generate_maintenance(sites, output_dir)
    generate_alarms(sites, output_dir)
    generate_kpis(sites, output_dir)
    generate_knowledge_base(sites, output_dir)
    
    print(f"\n✅ Data generation complete!\n")


if __name__ == "__main__":
    main()

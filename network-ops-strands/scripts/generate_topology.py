#!/usr/bin/env python3
"""
Generate synthetic network topology data for visualization.
Supports different profiles: QTS (data center) and Telco CSP.
"""

import json
import random
from typing import List, Dict, Any
from pathlib import Path


def generate_datacenter_topology() -> Dict[str, Any]:
    """Generate data center network topology."""
    nodes = []
    edges = []
    
    # Core switches (2 for redundancy)
    core_switches = [
        {
            'id': 'core-sw-1',
            'label': 'Core Switch\nQTS-CORE-01',
            'group': 'core',
            'x': -200,
            'y': -300,
            'details': {
                'type': 'Core Switch',
                'model': 'Cisco Nexus 9500',
                'ports': 64,
                'status': 'online',
                'uptime': '245 days',
                'cpu_utilization': random.randint(15, 35),
                'memory_utilization': random.randint(40, 60),
                'customer': 'Infrastructure',
                'location': 'Atlanta DC - Core Room'
            }
        },
        {
            'id': 'core-sw-2',
            'label': 'Core Switch\nQTS-CORE-02',
            'group': 'core',
            'x': 200,
            'y': -300,
            'details': {
                'type': 'Core Switch',
                'model': 'Cisco Nexus 9500',
                'ports': 64,
                'status': 'alarm',
                'alarm_severity': 'critical',
                'alarm_reason': 'High CPU utilization detected (92%). Multiple BGP sessions flapping. Immediate attention required.',
                'alarm_type': 'PERFORMANCE_DEGRADATION',
                'alarm_start': '2024-02-02 14:23:15',
                'uptime': '198 days',
                'cpu_utilization': 92,
                'memory_utilization': 78,
                'customer': 'Infrastructure',
                'location': 'Atlanta DC - Core Room'
            }
        }
    ]
    nodes.extend(core_switches)
    
    # Distribution switches (4)
    dist_positions = [(-400, -100), (-150, -100), (150, -100), (400, -100)]
    for i, (x, y) in enumerate(dist_positions, 1):
        # Add alarm to dist-sw-2
        if i == 2:
            dist_sw = {
                'id': f'dist-sw-{i}',
                'label': f'Distribution\nQTS-DIST-{i:02d}',
                'group': 'distribution',
                'x': x,
                'y': y,
                'details': {
                    'type': 'Distribution Switch',
                    'model': 'Arista 7280R',
                    'ports': 48,
                    'status': 'alarm',
                    'alarm_severity': 'major',
                    'alarm_reason': 'Port 24 link down. Redundant path available but capacity reduced by 40G.',
                    'alarm_type': 'LINK_DOWN',
                    'alarm_start': '2024-02-02 16:45:32',
                    'uptime': f'{random.randint(100, 300)} days',
                    'cpu_utilization': random.randint(20, 45),
                    'memory_utilization': random.randint(35, 55),
                    'customer': 'Infrastructure',
                    'location': f'Atlanta DC - Floor {(i-1)//2 + 1}'
                }
            }
        else:
            dist_sw = {
                'id': f'dist-sw-{i}',
                'label': f'Distribution\nQTS-DIST-{i:02d}',
                'group': 'distribution',
                'x': x,
                'y': y,
                'details': {
                    'type': 'Distribution Switch',
                    'model': 'Arista 7280R',
                    'ports': 48,
                    'status': 'online',
                    'uptime': f'{random.randint(100, 300)} days',
                    'cpu_utilization': random.randint(20, 45),
                    'memory_utilization': random.randint(35, 55),
                    'customer': 'Infrastructure',
                    'location': f'Atlanta DC - Floor {(i-1)//2 + 1}'
                }
            }
        nodes.append(dist_sw)
        
        # Connect to both core switches
        edges.append({'from': 'core-sw-1', 'to': f'dist-sw-{i}', 'label': '100G'})
        edges.append({'from': 'core-sw-2', 'to': f'dist-sw-{i}', 'label': '100G'})
    
    # Access switches (12, increased from 8)
    access_y = 150
    access_x_start = -550
    access_x_step = 100
    for i in range(1, 13):
        dist_parent = ((i - 1) // 3) + 1
        x = access_x_start + ((i - 1) * access_x_step)
        
        # Add different alarm states to some access switches
        if i == 5:
            access_sw = {
                'id': f'access-sw-{i}',
                'label': f'Access\nQTS-ACC-{i:02d}',
                'group': 'access',
                'x': x,
                'y': access_y,
                'details': {
                    'type': 'Access Switch',
                    'model': 'Cisco Catalyst 9300',
                    'ports': 48,
                    'status': 'alarm',
                    'alarm_severity': 'critical',
                    'alarm_reason': 'Switch offline. No response to ICMP/SNMP. Power supply failure suspected. Affecting 12 downstream servers.',
                    'alarm_type': 'DEVICE_DOWN',
                    'alarm_start': '2024-02-02 17:12:08',
                    'uptime': 'N/A',
                    'cpu_utilization': 0,
                    'memory_utilization': 0,
                    'customer': f'Rack {i}',
                    'location': f'Atlanta DC - Rack {i}'
                }
            }
        elif i == 8:
            access_sw = {
                'id': f'access-sw-{i}',
                'label': f'Access\nQTS-ACC-{i:02d}',
                'group': 'access',
                'x': x,
                'y': access_y,
                'details': {
                    'type': 'Access Switch',
                    'model': 'Cisco Catalyst 9300',
                    'ports': 48,
                    'status': 'alarm',
                    'alarm_severity': 'minor',
                    'alarm_reason': 'High temperature warning (68°C). Cooling system operating but ambient temperature elevated.',
                    'alarm_type': 'HIGH_TEMPERATURE',
                    'alarm_start': '2024-02-02 15:30:22',
                    'uptime': f'{random.randint(50, 200)} days',
                    'cpu_utilization': random.randint(25, 50),
                    'memory_utilization': random.randint(30, 50),
                    'customer': f'Rack {i}',
                    'location': f'Atlanta DC - Rack {i}'
                }
            }
        else:
            access_sw = {
                'id': f'access-sw-{i}',
                'label': f'Access\nQTS-ACC-{i:02d}',
                'group': 'access',
                'x': x,
                'y': access_y,
                'details': {
                    'type': 'Access Switch',
                    'model': 'Cisco Catalyst 9300',
                    'ports': 48,
                    'status': 'online',
                    'uptime': f'{random.randint(50, 200)} days',
                    'cpu_utilization': random.randint(25, 50),
                    'memory_utilization': random.randint(30, 50),
                    'customer': f'Rack {i}',
                    'location': f'Atlanta DC - Rack {i}'
                }
            }
        nodes.append(access_sw)
        
        # Connect to distribution switch
        edges.append({'from': f'dist-sw-{dist_parent}', 'to': f'access-sw-{i}', 'label': '40G'})
    
    # Servers and storage (25 nodes, increased from 15)
    server_y = 400
    device_types = [
        ('server', 'Compute Server', 'Dell PowerEdge R750', 'compute'),
        ('storage', 'Storage Array', 'NetApp AFF A400', 'storage'),
        ('firewall', 'Firewall', 'Palo Alto PA-5220', 'security')
    ]
    
    # Distribute devices more evenly across access switches
    devices_per_access = 2  # 2-3 devices per access switch
    for i in range(1, 26):
        access_parent = ((i - 1) % 12) + 1
        device_type, type_label, model, group = random.choice(device_types)
        
        # Calculate position with better spacing
        access_x = access_x_start + ((access_parent - 1) * access_x_step)
        device_offset = ((i - 1) // 12) * 60  # Offset for multiple devices per switch
        x = access_x + random.randint(-25, 25) + device_offset
        
        # Add alarm to some devices
        has_alarm = i in [3, 11, 18]
        
        if device_type == 'server':
            if has_alarm and i == 3:
                details = {
                    'type': type_label,
                    'model': model,
                    'ports': 4,
                    'status': 'alarm',
                    'alarm_severity': 'major',
                    'alarm_reason': 'Disk array failure detected. RAID 5 degraded. 2 of 8 drives offline. Data integrity at risk.',
                    'alarm_type': 'HARDWARE_FAULT',
                    'alarm_start': '2024-02-02 13:45:19',
                    'uptime': f'{random.randint(10, 150)} days',
                    'cpu_utilization': random.randint(30, 80),
                    'memory_utilization': random.randint(40, 85),
                    'customer': f'Customer-{random.randint(1, 10)}',
                    'location': f'Atlanta DC - Rack {access_parent}'
                }
            else:
                details = {
                    'type': type_label,
                    'model': model,
                    'ports': 4,
                    'status': 'online',
                    'uptime': f'{random.randint(10, 150)} days',
                    'cpu_utilization': random.randint(30, 80),
                    'memory_utilization': random.randint(40, 85),
                    'customer': f'Customer-{random.randint(1, 10)}',
                    'location': f'Atlanta DC - Rack {access_parent}'
                }
        elif device_type == 'storage':
            if has_alarm and i == 11:
                details = {
                    'type': type_label,
                    'model': model,
                    'capacity': f'{random.randint(50, 500)} TB',
                    'status': 'alarm',
                    'alarm_severity': 'minor',
                    'alarm_reason': 'Storage capacity at 87%. Recommend adding additional capacity or archiving old data.',
                    'alarm_type': 'CAPACITY_WARNING',
                    'alarm_start': '2024-02-02 09:15:44',
                    'uptime': f'{random.randint(10, 150)} days',
                    'iops': f'{random.randint(10000, 100000):,}',
                    'utilization': '87%',
                    'customer': f'Customer-{random.randint(1, 10)}',
                    'location': f'Atlanta DC - Rack {access_parent}'
                }
            else:
                details = {
                    'type': type_label,
                    'model': model,
                    'capacity': f'{random.randint(50, 500)} TB',
                    'status': 'online',
                    'uptime': f'{random.randint(10, 150)} days',
                    'iops': f'{random.randint(10000, 100000):,}',
                    'utilization': f'{random.randint(40, 85)}%',
                    'customer': f'Customer-{random.randint(1, 10)}',
                    'location': f'Atlanta DC - Rack {access_parent}'
                }
        else:  # firewall
            if has_alarm and i == 18:
                details = {
                    'type': type_label,
                    'model': model,
                    'throughput': f'{random.randint(10, 100)} Gbps',
                    'status': 'alarm',
                    'alarm_severity': 'major',
                    'alarm_reason': 'DDoS attack detected. Blocking 45,000 malicious IPs. Traffic spike to 85 Gbps.',
                    'alarm_type': 'SECURITY_THREAT',
                    'alarm_start': '2024-02-02 16:22:37',
                    'uptime': f'{random.randint(10, 150)} days',
                    'connections': f'{random.randint(10000, 500000):,}',
                    'cpu_utilization': 88,
                    'customer': f'Customer-{random.randint(1, 10)}',
                    'location': f'Atlanta DC - Rack {access_parent}'
                }
            else:
                details = {
                    'type': type_label,
                    'model': model,
                    'throughput': f'{random.randint(10, 100)} Gbps',
                    'status': 'online',
                    'uptime': f'{random.randint(10, 150)} days',
                    'connections': f'{random.randint(10000, 500000):,}',
                    'cpu_utilization': random.randint(20, 60),
                    'customer': f'Customer-{random.randint(1, 10)}',
                    'location': f'Atlanta DC - Rack {access_parent}'
                }
        
        device = {
            'id': f'{device_type}-{i}',
            'label': f'{type_label}\n{device_type.upper()}-{i:02d}',
            'group': group,
            'x': x,
            'y': server_y,
            'details': details
        }
        nodes.append(device)
        
        # Connect to access switch
        speed = '25G' if device_type == 'storage' else '10G'
        edges.append({'from': f'access-sw-{access_parent}', 'to': f'{device_type}-{i}', 'label': speed})
    
    return {'nodes': nodes, 'edges': edges, 'profile': 'qts'}


def generate_telco_topology() -> Dict[str, Any]:
    """Generate Telco CSP network topology."""
    nodes = []
    edges = []
    
    # Core network elements
    core_elements = [
        {
            'id': 'mme-1',
            'label': 'MME\nMME-ATL-01',
            'group': 'core',
            'x': -200,
            'y': -300,
            'details': {
                'type': 'Mobility Management Entity',
                'vendor': 'Ericsson',
                'model': 'MME 18B',
                'status': 'online',
                'uptime': '312 days',
                'subscribers': f'{random.randint(50000, 200000):,}',
                'cpu_utilization': random.randint(30, 60),
                'memory_utilization': random.randint(45, 70),
                'location': 'Atlanta Core Site'
            }
        },
        {
            'id': 'sgw-1',
            'label': 'S-GW\nSGW-ATL-01',
            'group': 'core',
            'x': 0,
            'y': -300,
            'details': {
                'type': 'Serving Gateway',
                'vendor': 'Nokia',
                'model': 'AirFrame',
                'status': 'online',
                'uptime': '287 days',
                'throughput': f'{random.randint(10, 50)} Gbps',
                'cpu_utilization': random.randint(35, 65),
                'memory_utilization': random.randint(40, 65),
                'location': 'Atlanta Core Site'
            }
        },
        {
            'id': 'pgw-1',
            'label': 'P-GW\nPGW-ATL-01',
            'group': 'core',
            'x': 200,
            'y': -300,
            'details': {
                'type': 'PDN Gateway',
                'vendor': 'Cisco',
                'model': 'ASR 5500',
                'status': 'online',
                'uptime': '245 days',
                'throughput': f'{random.randint(20, 80)} Gbps',
                'cpu_utilization': random.randint(40, 70),
                'memory_utilization': random.randint(50, 75),
                'location': 'Atlanta Core Site'
            }
        }
    ]
    nodes.extend(core_elements)
    
    # Base stations / eNodeBs (8, increased from 6)
    enodeb_positions = [(-400, 0), (-250, 0), (-100, 0), (50, 0), (200, 0), (350, 0), (-325, 120), (275, 120)]
    for i, (x, y) in enumerate(enodeb_positions, 1):
        site_id = f'site_atlanta_{i:03d}'
        
        # Add alarm to some eNodeBs
        if i == 3:
            enodeb = {
                'id': f'enodeb-{i}',
                'label': f'eNodeB\n{site_id}',
                'group': 'ran',
                'x': x,
                'y': y,
                'details': {
                    'type': 'eNodeB',
                    'site_id': site_id,
                    'vendor': random.choice(['Ericsson', 'Nokia', 'Huawei']),
                    'model': random.choice(['AIR 6488', 'AirScale', 'BBU5900']),
                    'status': 'alarm',
                    'alarm_severity': 'critical',
                    'alarm_reason': 'S1 interface down. No connectivity to core network. All UEs disconnected. Site isolated.',
                    'alarm_type': 'CONNECTIVITY_ISSUE',
                    'alarm_start': '2024-02-02 17:05:12',
                    'uptime': f'{random.randint(50, 300)} days',
                    'connected_ues': 0,
                    'throughput': '0 Gbps',
                    'location': f'Atlanta Sector {i}'
                }
            }
        elif i == 6:
            enodeb = {
                'id': f'enodeb-{i}',
                'label': f'eNodeB\n{site_id}',
                'group': 'ran',
                'x': x,
                'y': y,
                'details': {
                    'type': 'eNodeB',
                    'site_id': site_id,
                    'vendor': random.choice(['Ericsson', 'Nokia', 'Huawei']),
                    'model': random.choice(['AIR 6488', 'AirScale', 'BBU5900']),
                    'status': 'alarm',
                    'alarm_severity': 'major',
                    'alarm_reason': 'High interference detected on LTE Band 4. Call drop rate increased to 8%. Neighbor cell optimization needed.',
                    'alarm_type': 'RF_DEGRADATION',
                    'alarm_start': '2024-02-02 14:18:55',
                    'uptime': f'{random.randint(50, 300)} days',
                    'connected_ues': random.randint(100, 500),
                    'throughput': f'{random.randint(1, 10)} Gbps',
                    'location': f'Atlanta Sector {i}'
                }
            }
        else:
            enodeb = {
                'id': f'enodeb-{i}',
                'label': f'eNodeB\n{site_id}',
                'group': 'ran',
                'x': x,
                'y': y,
                'details': {
                    'type': 'eNodeB',
                    'site_id': site_id,
                    'vendor': random.choice(['Ericsson', 'Nokia', 'Huawei']),
                    'model': random.choice(['AIR 6488', 'AirScale', 'BBU5900']),
                    'status': 'online',
                    'uptime': f'{random.randint(50, 300)} days',
                    'connected_ues': random.randint(100, 500),
                    'throughput': f'{random.randint(1, 10)} Gbps',
                    'location': f'Atlanta Sector {i}'
                }
            }
        nodes.append(enodeb)
        
        # Connect to MME and S-GW
        edges.append({'from': 'mme-1', 'to': f'enodeb-{i}', 'label': 'S1-MME'})
        edges.append({'from': 'sgw-1', 'to': f'enodeb-{i}', 'label': 'S1-U'})
    
    # Connect core elements
    edges.append({'from': 'mme-1', 'to': 'sgw-1', 'label': 'S11'})
    edges.append({'from': 'sgw-1', 'to': 'pgw-1', 'label': 'S5/S8'})
    
    # Small cells (12, increased from 8)
    small_cell_y = 250
    for i in range(1, 13):
        parent_enodeb = ((i - 1) % 8) + 1
        # Better spacing for small cells
        base_x = enodeb_positions[parent_enodeb - 1][0]
        offset = ((i - 1) // 8) * 80  # Offset for multiple small cells per eNodeB
        x = base_x + random.randint(-40, 40) + offset
        
        small_cell = {
            'id': f'small-cell-{i}',
            'label': f'Small Cell\nSC-{i:02d}',
            'group': 'small_cell',
            'x': x,
            'y': small_cell_y,
            'details': {
                'type': 'Small Cell',
                'vendor': random.choice(['Ericsson', 'Nokia']),
                'model': 'Radio Dot',
                'status': 'online',
                'uptime': f'{random.randint(20, 150)} days',
                'connected_ues': random.randint(10, 50),
                'throughput': f'{random.randint(100, 1000)} Mbps',
                'location': f'Atlanta Indoor-{i}'
            }
        }
        nodes.append(small_cell)
        
        # Connect to parent eNodeB
        edges.append({'from': f'enodeb-{parent_enodeb}', 'to': f'small-cell-{i}', 'label': 'X2'})
    
    return {'nodes': nodes, 'edges': edges, 'profile': 'telco'}


def main():
    """Generate topology data for both profiles."""
    output_dir = Path(__file__).parent.parent / 'data'
    output_dir.mkdir(exist_ok=True)
    
    # Generate datacenter topology
    dc_topology = generate_datacenter_topology()
    dc_file = output_dir / 'topology_datacenter.json'
    with open(dc_file, 'w') as f:
        json.dump(dc_topology, f, indent=2)
    print(f"✅ Generated datacenter topology: {dc_file}")
    print(f"   Nodes: {len(dc_topology['nodes'])}, Edges: {len(dc_topology['edges'])}")
    
    # Generate Telco topology
    telco_topology = generate_telco_topology()
    telco_file = output_dir / 'topology_telco.json'
    with open(telco_file, 'w') as f:
        json.dump(telco_topology, f, indent=2)
    print(f"✅ Generated Telco topology: {telco_file}")
    print(f"   Nodes: {len(telco_topology['nodes'])}, Edges: {len(telco_topology['edges'])}")


if __name__ == '__main__':
    main()

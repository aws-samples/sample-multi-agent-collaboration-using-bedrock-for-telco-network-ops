# Site Down Troubleshooting Guide

**Category**: Connectivity  
**Last Updated**: 2024-01-15  
**Document Type**: article

## Overview

This guide provides step-by-step troubleshooting procedures when a network site becomes unresponsive or goes completely offline.

## Initial Assessment (First 5 Minutes)

1. **Verify the Outage**
   - Check monitoring systems for alarm status
   - Attempt to ping the site from multiple locations
   - Verify if issue is isolated to one site or multiple sites

2. **Check External Factors**
   - Query power outage databases for the site location
   - Check for 811 dig requests in the area
   - Review weather conditions for severe events

3. **Review Recent Changes**
   - Check maintenance schedule for planned work
   - Review configuration change logs
   - Verify no recent software updates

## Systematic Troubleshooting Steps

### Step 1: Power and Physical Connectivity

- **Check Power Supply**
  - Verify utility power status
  - Check UPS/backup power systems
  - Review power consumption logs
  - Test circuit breakers and power distribution

- **Physical Connections**
  - Verify fiber/cable connections are secure
  - Check for physical damage to cables
  - Inspect outdoor equipment for weather damage
  - Test backup connectivity paths if available

### Step 2: Network Layer Diagnostics

- **Layer 1/2 Issues**
  - Check interface status (up/down)
  - Review error counters (CRC, frame errors)
  - Verify link lights on equipment
  - Test with different cables if possible

- **Layer 3 Issues**
  - Verify IP addressing is correct
  - Check routing tables
  - Test gateway connectivity
  - Verify VLAN configurations

### Step 3: Device-Level Checks

- **Equipment Status**
  - Access device console if possible
  - Review system logs for errors
  - Check CPU and memory utilization
  - Verify all services are running

- **Configuration Validation**
  - Compare current config to baseline
  - Check for unauthorized changes
  - Verify firewall rules
  - Test ACLs and security policies

### Step 4: Service-Level Testing

- **Connectivity Tests**
  - Ping from multiple sources
  - Traceroute to identify failure point
  - Test DNS resolution
  - Verify application-level connectivity

## Common Root Causes

### Power-Related (40% of outages)
- Utility power outage
- UPS failure or battery depletion
- Circuit breaker trip
- Power supply failure in equipment

**Resolution**: Coordinate with utility company, replace failed components, verify backup power systems

### Physical Damage (25% of outages)
- Fiber cut from excavation
- Cable damage from weather
- Connector failure
- Equipment physical damage

**Resolution**: Emergency fiber repair, cable replacement, equipment swap

### Configuration Issues (20% of outages)
- Incorrect configuration change
- Routing protocol misconfiguration
- Firewall rule blocking traffic
- VLAN mismatch

**Resolution**: Rollback configuration, correct settings, verify with testing

### Equipment Failure (15% of outages)
- Hardware component failure
- Software crash or bug
- Memory/CPU exhaustion
- Firmware corruption

**Resolution**: Reboot equipment, replace failed hardware, upgrade firmware

## Escalation Criteria

Escalate to senior engineer if:
- Issue not resolved within 30 minutes
- Multiple sites affected simultaneously
- Root cause unclear after initial troubleshooting
- Requires vendor support or RMA
- Customer-impacting outage exceeds SLA

## Documentation Requirements

After resolution, document:
- Incident timeline
- Root cause analysis
- Resolution steps taken
- Preventive measures implemented
- Lessons learned

## Related Articles

- Power Outage Recovery Procedures
- Fiber Cut Emergency Response
- Configuration Rollback Procedures
- Equipment Replacement Guide

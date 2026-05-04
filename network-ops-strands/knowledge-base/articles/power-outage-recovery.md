# Power Outage Recovery Procedures

**Category**: Power  
**Last Updated**: 2024-01-20  
**Document Type**: article

## Overview

Standard procedures for recovering network sites after utility power restoration following an outage.

## Immediate Actions (First 15 Minutes)

1. **Verify Power Restoration**
   - Confirm utility power is stable
   - Check voltage levels are within normal range
   - Verify all phases are active (3-phase systems)
   - Monitor for power fluctuations

2. **UPS System Check**
   - Verify UPS switched back to utility power
   - Check battery charge status
   - Review UPS logs for any issues during outage
   - Test UPS alarm systems

3. **Equipment Power-On Sequence**
   - Follow proper power-on sequence (core first, then edge)
   - Wait 2-3 minutes between powering on major components
   - Monitor equipment during boot process
   - Check for any unusual sounds or smells

## Systematic Recovery Steps

### Step 1: Infrastructure Verification

- **Power Distribution**
  - Verify all PDUs are operational
  - Check circuit breakers are in correct position
  - Test redundant power supplies
  - Monitor power consumption levels

- **Cooling Systems**
  - Verify HVAC systems are running
  - Check temperature sensors
  - Monitor for proper airflow
  - Ensure cooling is adequate before full load

### Step 2: Network Equipment Recovery

- **Core Network Devices**
  - Verify routers and switches boot successfully
  - Check all interfaces come up
  - Verify routing protocols converge
  - Test inter-site connectivity

- **Access Equipment**
  - Verify customer-facing equipment is online
  - Check service provisioning
  - Test end-to-end connectivity
  - Verify QoS policies are active

### Step 3: Service Validation

- **Connectivity Tests**
  - Ping all critical endpoints
  - Verify routing tables are correct
  - Test failover mechanisms
  - Validate backup paths

- **Application Services**
  - Check all services are running
  - Verify database connectivity
  - Test application functionality
  - Monitor for any degraded performance

### Step 4: Monitoring and Documentation

- **System Monitoring**
  - Review all alarms and clear false positives
  - Monitor KPIs for 1-2 hours post-recovery
  - Watch for any anomalies
  - Verify backup systems are ready

- **Incident Documentation**
  - Record outage duration
  - Document recovery steps taken
  - Note any equipment that failed to recover
  - Identify any configuration changes needed

## Common Issues During Recovery

### Equipment Fails to Power On
- Check power connections
- Verify circuit breakers
- Test with different power source
- May require equipment replacement

### Services Don't Start Automatically
- Manually start required services
- Check for configuration corruption
- Verify dependencies are met
- Review startup logs for errors

### Performance Degradation
- May be due to battery charging load
- Check for thermal issues
- Verify all redundant paths are active
- Monitor for hardware failures

## Post-Recovery Actions (Within 24 Hours)

1. **UPS Battery Testing**
   - Perform battery load test
   - Check battery health indicators
   - Replace batteries if needed
   - Document battery status

2. **Equipment Health Check**
   - Review all system logs
   - Check for any errors during outage
   - Verify all redundant components
   - Schedule any needed maintenance

3. **Preventive Measures**
   - Review UPS runtime capacity
   - Consider generator installation if frequent outages
   - Update emergency contact lists
   - Review and update procedures

## Escalation

Contact vendor support if:
- Equipment fails to power on after 30 minutes
- Repeated power cycling required
- Unusual errors in system logs
- Performance significantly degraded

## Related Articles

- Site Down Troubleshooting Guide
- UPS Maintenance Procedures
- Emergency Generator Operations
- Equipment Replacement Guide

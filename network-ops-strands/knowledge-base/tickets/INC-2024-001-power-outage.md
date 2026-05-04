# Incident Ticket: INC-2024-001

**Ticket ID**: INC-2024-001  
**Site ID**: site_dallas_001  
**Document Type**: ticket  
**Status**: Resolved  
**Resolved Date**: 2024-01-10

## Incident Summary

Site went completely offline during utility power outage. All services were unavailable for approximately 2 hours.

## Timeline

- **14:30** - Site monitoring alarms triggered (site unreachable)
- **14:32** - On-call engineer notified
- **14:35** - Initial troubleshooting began
- **14:40** - Confirmed utility power outage via Oncor Electric website
- **14:45** - Contacted utility company for ETA
- **15:00** - Utility company confirmed substation equipment failure
- **16:15** - Power restored by utility
- **16:20** - Site equipment began automatic recovery
- **16:30** - All services verified operational
- **16:45** - Incident closed

## Root Cause

Utility power outage caused by equipment failure at Oncor Electric substation serving the area. Affected approximately 1,250 customers including our site.

## Resolution Steps

1. Identified power outage through external context check
2. Contacted utility company (Oncor Electric: 1-888-313-4747)
3. Monitored utility company outage map for updates
4. Waited for power restoration
5. Verified UPS logs showed proper failover during outage
6. Confirmed all equipment powered back on automatically
7. Validated all services operational
8. Cleared monitoring alarms

## Resolution Time

**Total Duration**: 2 hours 15 minutes  
**Active Troubleshooting**: 15 minutes  
**Waiting for Utility**: 1 hour 35 minutes  
**Recovery and Validation**: 25 minutes

## Impact Assessment

- **Services Affected**: All services at site_dallas_001
- **Customers Impacted**: 45 customers
- **Revenue Impact**: Minimal (within SLA allowance)
- **Data Loss**: None (clean shutdown via UPS)

## Lessons Learned

### What Went Well
- UPS provided clean shutdown, preventing data corruption
- Monitoring systems detected outage immediately
- External context tools quickly identified power outage
- Automatic recovery worked as designed

### Areas for Improvement
- Consider installing generator for extended outages
- Improve communication with customers during outages
- Document utility company contact procedures
- Review UPS runtime capacity (currently 30 minutes)

## Preventive Measures Implemented

1. Added site to priority restoration list with utility company
2. Documented utility company emergency contacts
3. Scheduled UPS battery health check
4. Updated runbook with power outage procedures

## Related Incidents

- INC-2023-089 - Similar power outage at same site (6 months ago)
- INC-2024-015 - Power outage at site_dallas_002 (different substation)

## Knowledge Base References

- Power Outage Recovery Procedures
- UPS Maintenance Guide
- Customer Communication Templates

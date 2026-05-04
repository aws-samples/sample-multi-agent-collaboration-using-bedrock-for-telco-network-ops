# Incident Ticket: INC-2024-002

**Ticket ID**: INC-2024-002  
**Site ID**: site_birmingham_003  
**Document Type**: ticket  
**Status**: Resolved  
**Resolved Date**: 2024-01-18

## Incident Summary

Site connectivity lost due to fiber optic cable damage caused by excavation contractor. Emergency fiber repair performed with additional cable protection implemented.

## Timeline

- **09:15** - Site monitoring alarms triggered (connectivity loss)
- **09:17** - On-call engineer notified
- **09:20** - Initial troubleshooting began
- **09:25** - Confirmed physical layer issue (no light on fiber)
- **09:30** - Checked 811 dig request database
- **09:35** - Found active excavation permit for nearby address
- **09:40** - Dispatched field technician to site
- **10:15** - Field tech confirmed fiber cut by contractor
- **10:30** - Contacted contractor (City Public Works)
- **10:45** - Emergency fiber repair crew dispatched
- **12:30** - Temporary fiber splice completed
- **13:00** - Connectivity restored and tested
- **14:30** - Permanent repair completed
- **15:15** - Additional conduit protection installed
- **15:30** - Incident closed

## Root Cause

Fiber optic cable damaged by City Public Works contractor during water main repair excavation. Contractor had valid 811 ticket but failed to properly locate and avoid telecom utilities.

## Resolution Steps

1. Identified connectivity loss through monitoring
2. Performed layer 1 diagnostics (no fiber light)
3. Checked 811 database and found active dig request
4. Dispatched field technician for physical inspection
5. Confirmed fiber cut at excavation site
6. Contacted contractor to stop work
7. Coordinated emergency fiber repair
8. Performed temporary splice for quick restoration
9. Completed permanent repair
10. Installed additional protective conduit
11. Documented incident for insurance claim

## Resolution Time

**Total Duration**: 6 hours 15 minutes  
**Detection to Diagnosis**: 20 minutes  
**Dispatch and Assessment**: 55 minutes  
**Emergency Repair**: 2 hours 15 minutes  
**Permanent Repair**: 2 hours 30 minutes  
**Additional Protection**: 45 minutes

## Impact Assessment

- **Services Affected**: All services at site_birmingham_003
- **Customers Impacted**: 38 customers
- **Revenue Impact**: Moderate (exceeded SLA, credits issued)
- **Data Loss**: None (site remained powered, only connectivity lost)

## Contractor Information

- **Company**: City of Birmingham Public Works
- **811 Ticket**: 811-AL-20240117-045
- **Work Type**: Water main repair
- **Contact**: John Smith, Project Manager (205-555-0123)
- **Insurance**: Municipal liability coverage

## Lessons Learned

### What Went Well
- 811 database check quickly identified excavation activity
- Field technician responded promptly
- Emergency repair crew available same day
- Temporary splice minimized downtime

### Areas for Improvement
- Need better coordination with contractors on active 811 tickets
- Consider proactive site visits when high-risk dig requests filed
- Improve fiber route documentation and marking
- Establish direct contact with frequent contractors

## Preventive Measures Implemented

1. **Physical Protection**
   - Installed additional protective conduit at damage location
   - Added warning markers above buried fiber
   - Documented exact fiber route with GPS coordinates

2. **Process Improvements**
   - Set up automated alerts for 811 tickets near sites
   - Created contractor communication template
   - Established pre-excavation site visit protocol
   - Added site to high-priority repair list

3. **Documentation**
   - Updated fiber route maps
   - Photographed repair location
   - Filed insurance claim documentation
   - Created case study for training

## Financial Impact

- **Repair Costs**: $4,500 (emergency repair + permanent fix)
- **SLA Credits**: $1,200 (customer credits for downtime)
- **Insurance Recovery**: $5,700 (claim filed with contractor's insurance)
- **Net Cost**: $0 (fully recovered)

## Related Incidents

- INC-2023-156 - Fiber cut at site_atlanta_002 (similar excavation damage)
- INC-2023-201 - Fiber cut at site_dallas_003 (storm damage, different cause)

## Knowledge Base References

- Fiber Cut Emergency Response Procedures
- 811 Dig Request Monitoring Guide
- Contractor Coordination Procedures
- Insurance Claim Filing Guide

## Follow-Up Actions

- [ ] Schedule follow-up inspection in 30 days
- [ ] Verify insurance claim payment received
- [ ] Update contractor contact database
- [ ] Conduct training session on 811 monitoring
- [x] Install additional protection (completed)
- [x] Update fiber route documentation (completed)

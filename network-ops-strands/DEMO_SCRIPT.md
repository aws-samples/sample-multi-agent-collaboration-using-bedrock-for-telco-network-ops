# Network Operations AI Platform — Demo Storyboard
## Challenger Sale × Freytag's 5-Act Framework
### Target: Telco Network Operations Leaders | Total Time: 15–20 minutes

---

# PRE-DEMO SETUP

```bash
cd network-ops-strands
./start-local.sh
```

Wait for both servers to start:
- Backend API: http://localhost:8000
- Frontend: http://localhost:3000

Open http://localhost:3000 in your browser. You should see the Dashboard view.

✓ Demo users created
   User 1: netopsuser@example.com / NetworkOps2026!
   User 2: operator2@netops.demo / NetworkOps2026!

---

## Act 1: The Dashboard (30 seconds)

**What to show**: The Dashboard loads automatically with live metrics pulled from the data layer.

**Talking points**:
- "This is our Network Operations Dashboard — it gives operators an at-a-glance view of their entire infrastructure."
- Point out the 4 metric cards: Active Alarms (with severity breakdown), Ongoing Maintenance, Sites Monitored (20 sites across 10 locations), and Average Latency.
- "Everything here is real data. The alarm counts, maintenance windows — all pulled from our data store in real time."

**Click**: The "Network Topology" tab in the header.

---

## Act 2: Network Topology (30 seconds)

**What to show**: The interactive topology map showing QTS data center locations.

**Talking points**:
- "Here's our network topology — 20 sites across 10 locations: Atlanta, Dallas, Chicago, Richmond, Phoenix, Ashburn, Piscataway, Sacramento, Irving, and Suwanee."
- "Each node represents a data center. Operators can see the physical layout of their infrastructure at a glance."

**Click**: The "AI Assistant" tab in the header.

---

## Act 3: AI Assistant — Simple Query (1 minute)

**What to show**: The chat interface with the welcome screen and suggested queries.

**Talking points**:
- "This is where it gets interesting. Instead of clicking through dashboards and filtering tables, operators just ask questions in natural language."

**Type this query**:
```
Show all critical alarms
```

**While it streams**:
- "Notice the response is streaming in real-time, token by token. Under the hood, our Supervisor Agent — powered by Claude Sonnet — analyzed the query, routed it to the Alarm Agent, which queried the data and returned a prioritized list."
- "Critical alarms are surfaced first with severity indicators, affected services, and incident IDs. The agent also provides an actionable recommendation."

---

## Act 4: Site-Specific Deep Dive (1 minute)

**Type this query**:
```
What's happening at site_richmond_008?
```

**Talking points**:
- "Now watch — the Supervisor recognizes this is a broad status query. It fans out to all three specialized agents simultaneously."
- "We get a unified view: active alarms (there's a critical SITE_DOWN), any maintenance windows, and performance metrics — all in one response."
- "An engineer doesn't need to check three different tools. One question, one answer."

---

## Act 5: Performance Analysis (1 minute)

**Type this query**:
```
Analyze performance for site_dallas_003
```

**Talking points**:
- "The KPI Agent pulls the last 24 hours of metrics — throughput, latency, packet loss, CPU, memory."
- "It doesn't just show numbers. It interprets them: 'throughput is excellent at 2.1 Gbps', 'latency needs attention at 22ms'."
- "It also flags anomalies — spikes that deviate from normal patterns — with timestamps so engineers know exactly when something went wrong."

---

## Act 6: Multi-Turn Conversation (1 minute)

**Type this follow-up** (don't start a new session):
```
Compare that with site_atlanta_001
```

**Talking points**:
- "The agent remembers context. I said 'compare that' — it knows I'm talking about site_dallas_003 from my previous question."
- "This is session-aware conversation. Engineers can drill down naturally without repeating themselves."

---

## Act 7: Complex Multi-Agent Query (1 minute)

**Type this query**:
```
Which sites have both critical alarms and scheduled maintenance? What's the risk?
```

**Talking points**:
- "This is where the multi-agent architecture really shines. The Supervisor coordinates the Alarm Agent and Maintenance Agent, cross-references the results, and synthesizes a risk assessment."
- "No single dashboard gives you this kind of correlated insight. The AI connects the dots across domains."

---

## Act 8: External Context & Root Cause Analysis (1 minute)

**Type this query**:
```
Site_richmond_008 has a SITE_DOWN alarm. Can you check for external factors that might explain the outage?
```

**Talking points**:
- "Now watch — the Supervisor calls the MCP external context tools. It checks power outages from the utility company, 811 dig requests for excavation activity, and weather events."
- "This is the MCP server integration. The supervisor spawns it locally via stdio, or connects to AgentCore Gateway in production."
- "It correlates the external data with the alarm and gives a root cause assessment — is this a power issue, cable damage from construction, or weather-related?"

---

## Act 8.5: Knowledge Base — Past Incidents & Troubleshooting (1 minute)

**Type this query**:
```
We're seeing a POWER_ISSUE alarm at site_dallas_003. Search the knowledge base for similar past incidents and recommended resolution steps.
```

**Talking points**:
- "The Supervisor now calls the Knowledge Base tool — powered by Bedrock Knowledge Bases with S3 Vectors."
- "It searches through our library of troubleshooting articles and past incident tickets using semantic vector search."
- "It finds relevant articles like 'Power Outage Recovery Procedures' and past tickets where similar issues were resolved — complete with timelines, root causes, and resolution steps."
- "This is institutional knowledge at the engineer's fingertips. No more digging through wikis or Slack history."

**Follow-up query**:
```
Has there been a fiber cut incident before? What was the resolution?
```

**Talking points**:
- "It pulls up the actual incident ticket with the full timeline — detection, dispatch, emergency splice, permanent repair."
- "This is RAG in action — retrieval augmented generation. The agent grounds its response in real documentation, not hallucinated procedures."

---

## Act 9: Architecture Recap (30 seconds)

**Switch back to Dashboard** (click the Dashboard tab).

**Talking points**:
- "Let me recap what's under the hood:"
  - "Supervisor Agent on Claude Sonnet — handles routing and complex reasoning"
  - "Three specialized agents on Nova Lite — cost-effective for domain-specific queries"
  - "MCP server for external context — power outages, weather, 811 dig requests"
  - "Bedrock Knowledge Base with S3 Vectors — troubleshooting articles and past incident tickets"
  - "AgentCore Memory — conversation persistence across sessions"
  - "Streaming responses via SSE for real-time feedback"
  - "React frontend with Tailwind CSS — responsive, dark mode, whitelabel-ready"
  - "All data from CSV files on S3 — easy to swap in real data sources"
- "The whole thing runs locally for development, and deploys to AWS with a single command using SAM."

---

## Bonus Queries (if time permits)

### Maintenance Focus
```
Show upcoming maintenance for site_chicago_005
```

### Trend Analysis
```
Are there any performance anomalies across the network today?
```

### Operational Planning
```
Give me a full operational report for the Atlanta sites
```

### Site Comparison
```
Compare latency between site_ashburn_011 and site_ashburn_012
```

### Root Cause Analysis (MCP)
```
Check external factors for site_phoenix_009 — is there a power outage or construction nearby?
```

### Code Interpreter Visualizations
```
Plot a bar chart comparing throughput across all Dallas and Atlanta sites
```
```
Create a line chart showing latency trends over the last 24 hours for site_chicago_005
```
```
Generate a heatmap of CPU utilization across all 20 sites
```

### Knowledge Base — Troubleshooting & Past Incidents
```
How do I recover a site after a power outage?
```
```
Has there been a fiber cut incident before? What was the resolution?
```
```
What are the troubleshooting steps for high latency issues?
```
```
Search for past incidents related to HVAC failures
```
```
What's the standard procedure for a site down event?
```

### Knowledge Base — Root Cause with KB Context
```
Site_dallas_003 has a POWER_ISSUE alarm. Search the knowledge base for similar past incidents and recommended resolution steps.
```
```
We're seeing high latency at site_chicago_005. Check the KB for troubleshooting guidance and any similar past tickets.
```

---

## Key Demo Talking Points

| Feature | What to Highlight |
|---|---|
| Multi-Agent Architecture | Supervisor routes to specialized agents automatically |
| MCP Integration | External context tools (power, weather, 811) via stdio/HTTP |
| Knowledge Base (RAG) | Bedrock KB with S3 Vectors — troubleshooting articles + past tickets |
| Streaming Responses | Token-by-token display, thinking indicators |
| Session Persistence | AgentCore Memory — conversations saved across sessions |
| Session Management | Create, switch, delete sessions — per-user isolation |
| Real Data | 20 sites, real alarm/maintenance/KPI data |
| Interactive Charts | Chart.js visualizations generated by the agent |
| Whitelabel | Branding loaded from config at runtime |
| Quick Actions | Dashboard buttons for instant and site-specific queries |
| Auth & Logout | Cognito login/logout with per-user session isolation |
| One-Command Deploy | `./deploy.sh` for full AWS deployment |
| Local Dev | `./start-local.sh` — no cloud needed for demos |

---

## Troubleshooting During Demo

| Problem | Fix |
|---|---|
| Backend won't start | Check AWS credentials: `aws sts get-caller-identity` |
| "Model not found" error | Ensure Bedrock models are enabled in us-east-1 |
| Slow first response | First query warms up the model connection — subsequent queries are faster |
| Frontend blank page | Check http://localhost:8000/health — backend must be running |
| No alarm data | Run `python scripts/generate_data.py --sites 20 --profile qts --output data` |

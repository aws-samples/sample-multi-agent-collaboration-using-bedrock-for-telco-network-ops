"""
External Context MCP Server
Built with FastMCP for network operations root cause analysis
Provides external context like power outages and 811 dig requests

Weather is handled by a separate mcp-weather-free MCP server
connected directly to the supervisor agent.

This MCP server can run in two modes:
1. Standalone (local development with FastMCP)
2. AgentCore Runtime (production deployment)
"""

import logging
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Configure logging — INFO for most, DEBUG for our code
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("mcp_server")
logger.setLevel(logging.DEBUG)

# Keep transport loggers at INFO
logging.getLogger("mcp").setLevel(logging.INFO)
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger.info("=" * 60)
logger.info("MCP SERVER STARTING")
logger.info(f"  Python: {sys.version}")
logger.info(f"  PID: {os.getpid()}")
logger.info(f"  MCP_TRANSPORT: {os.environ.get('MCP_TRANSPORT', 'not set')}")
logger.info(f"  ENVIRONMENT: {os.environ.get('ENVIRONMENT', 'not set')}")
logger.info("=" * 60)

# Use standalone fastmcp which wraps the official mcp SDK
# Keep the same package that was already working on AgentCore
from fastmcp import FastMCP

# Set host and stateless mode via env vars (fastmcp v3+ removed these from constructor)
os.environ.setdefault("FASTMCP_HOST", "0.0.0.0")
os.environ.setdefault("FASTMCP_STATELESS_HTTP", "true")

# Initialize FastMCP server for AgentCore compatibility
mcp = FastMCP("External Context")
logger.info("FastMCP instance created (FASTMCP_HOST=0.0.0.0, FASTMCP_STATELESS_HTTP=true)")

# Site location mapping (matches sites.csv)
SITE_LOCATIONS = {
    "site_atlanta_001": {"city": "Atlanta", "state": "GA", "zip": "30303", "lat": 33.7490, "lon": -84.3880},
    "site_atlanta_002": {"city": "Atlanta", "state": "GA", "zip": "30304", "lat": 33.7676, "lon": -84.3762},
    "site_dallas_003": {"city": "Dallas", "state": "TX", "zip": "75201", "lat": 32.7767, "lon": -96.7970},
    "site_dallas_004": {"city": "Dallas", "state": "TX", "zip": "75202", "lat": 32.7831, "lon": -96.8067},
    "site_chicago_005": {"city": "Chicago", "state": "IL", "zip": "60601", "lat": 41.8781, "lon": -87.6298},
    "site_chicago_006": {"city": "Chicago", "state": "IL", "zip": "60602", "lat": 41.8819, "lon": -87.6278},
    "site_richmond_007": {"city": "Richmond", "state": "VA", "zip": "23219", "lat": 37.5407, "lon": -77.4360},
    "site_richmond_008": {"city": "Richmond", "state": "VA", "zip": "23220", "lat": 37.5485, "lon": -77.4605},
    "site_phoenix_009": {"city": "Phoenix", "state": "AZ", "zip": "85001", "lat": 33.4484, "lon": -112.0740},
    "site_phoenix_010": {"city": "Phoenix", "state": "AZ", "zip": "85002", "lat": 33.4373, "lon": -112.0738},
    "site_ashburn_011": {"city": "Ashburn", "state": "VA", "zip": "20147", "lat": 39.0438, "lon": -77.4874},
    "site_ashburn_012": {"city": "Ashburn", "state": "VA", "zip": "20148", "lat": 39.0335, "lon": -77.4838},
    "site_piscataway_013": {"city": "Piscataway", "state": "NJ", "zip": "08854", "lat": 40.4862, "lon": -74.3990},
    "site_piscataway_014": {"city": "Piscataway", "state": "NJ", "zip": "08854", "lat": 40.4943, "lon": -74.3912},
    "site_sacramento_015": {"city": "Sacramento", "state": "CA", "zip": "95814", "lat": 38.5816, "lon": -121.4944},
    "site_sacramento_016": {"city": "Sacramento", "state": "CA", "zip": "95815", "lat": 38.6048, "lon": -121.4690},
    "site_irving_017": {"city": "Irving", "state": "TX", "zip": "75038", "lat": 32.8140, "lon": -96.9489},
    "site_irving_018": {"city": "Irving", "state": "TX", "zip": "75039", "lat": 32.8780, "lon": -96.9426},
    "site_suwanee_019": {"city": "Suwanee", "state": "GA", "zip": "30024", "lat": 34.0515, "lon": -84.0713},
    "site_suwanee_020": {"city": "Suwanee", "state": "GA", "zip": "30024", "lat": 34.0593, "lon": -84.0631},
}

# Simulated power outage data (in production, this would query utility APIs)
POWER_OUTAGES = [
    {
        "outage_id": "PWR-2026-001",
        "utility": "Oncor Electric Delivery",
        "city": "Dallas",
        "state": "TX",
        "zip_codes": ["75201", "75202"],
        "start_time": (datetime.now() - timedelta(hours=3)).isoformat(),
        "end_time": (datetime.now() - timedelta(hours=1)).isoformat(),
        "status": "resolved",
        "affected_customers": 1250,
        "cause": "Equipment failure at substation",
        "restoration_time": "2 hours"
    },
    {
        "outage_id": "PWR-2026-002",
        "utility": "Dominion Energy",
        "city": "Richmond",
        "state": "VA",
        "zip_codes": ["23219", "23220"],
        "start_time": (datetime.now() - timedelta(hours=6)).isoformat(),
        "end_time": None,
        "status": "ongoing",
        "affected_customers": 450,
        "cause": "Storm damage to transmission lines",
        "estimated_restoration": "4-6 hours"
    },
    {
        "outage_id": "PWR-2026-003",
        "utility": "APS (Arizona Public Service)",
        "city": "Phoenix",
        "state": "AZ",
        "zip_codes": ["85001"],
        "start_time": (datetime.now() - timedelta(hours=2)).isoformat(),
        "end_time": None,
        "status": "ongoing",
        "affected_customers": 820,
        "cause": "Transformer overload due to extreme heat",
        "estimated_restoration": "3-5 hours"
    }
]

# Simulated 811 dig requests (in production, this would query 811 databases)
DIG_REQUESTS = [
    {
        "ticket_id": "811-VA-20260210-001",
        "type": "excavation",
        "city": "Ashburn",
        "state": "VA",
        "zip": "20147",
        "address": "44060 Digital Loudoun Plaza",
        "start_date": (datetime.now() - timedelta(days=2)).isoformat(),
        "end_date": (datetime.now() + timedelta(days=5)).isoformat(),
        "status": "active",
        "contractor": "Loudoun Fiber Corp",
        "work_type": "Fiber optic installation",
        "utilities_marked": ["Electric", "Gas", "Telecom"],
        "risk_level": "medium"
    },
    {
        "ticket_id": "811-GA-20260209-045",
        "type": "excavation",
        "city": "Suwanee",
        "state": "GA",
        "zip": "30024",
        "address": "340 Peachtree Industrial Blvd",
        "start_date": (datetime.now() - timedelta(days=1)).isoformat(),
        "end_date": (datetime.now() + timedelta(days=3)).isoformat(),
        "status": "active",
        "contractor": "City Public Works",
        "work_type": "Water main repair",
        "utilities_marked": ["Water", "Electric", "Telecom"],
        "risk_level": "high"
    }
]


def _site_not_found_error(site_id: str) -> Dict:
    """Return a helpful error when a site_id is not found."""
    # Find similar sites by matching the location part of the ID
    parts = site_id.split('_')
    location_hint = parts[1] if len(parts) >= 2 else ""
    suggestions = [
        sid for sid in SITE_LOCATIONS
        if location_hint and location_hint.lower() in sid.lower()
    ]
    msg = f"Site {site_id} not found in location database."
    if suggestions:
        msg += f" Did you mean: {', '.join(suggestions)}?"
    else:
        msg += f" Valid sites: {', '.join(sorted(SITE_LOCATIONS.keys()))}"
    return {
        "success": False,
        "error": msg,
        "timestamp": datetime.now().isoformat()
    }


@mcp.tool()
def check_power_outages(site_id: str, time_window_hours: int = 24) -> Dict:
    """
    Check for power outages in the area of a network site
    
    Args:
        site_id: Site identifier (e.g., site_ashburn_011, site_dallas_003)
        time_window_hours: Hours to look back for outages (default: 24)
    
    Returns:
        Dictionary with power outage information for the site's location
    """
    logger.info(f"[TOOL CALL] check_power_outages(site_id={site_id}, "
                f"time_window_hours={time_window_hours})")
    if site_id not in SITE_LOCATIONS:
        return _site_not_found_error(site_id)
    
    location = SITE_LOCATIONS[site_id]
    cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
    
    # Find outages in the same zip code
    relevant_outages = []
    for outage in POWER_OUTAGES:
        if location["zip"] in outage["zip_codes"]:
            outage_start = datetime.fromisoformat(outage["start_time"])
            if outage_start >= cutoff_time:
                relevant_outages.append(outage)
    
    has_outages = len(relevant_outages) > 0
    
    return {
        "success": True,
        "site_id": site_id,
        "location": {
            "city": location["city"],
            "state": location["state"],
            "zip": location["zip"]
        },
        "time_window_hours": time_window_hours,
        "outages_found": len(relevant_outages),
        "outages": relevant_outages,
        "correlation_likelihood": "high" if has_outages else "none",
        "recommendation": _get_power_outage_recommendation(relevant_outages),
        "timestamp": datetime.now().isoformat()
    }


@mcp.tool()
def check_811_dig_requests(site_id: str, radius_miles: float = 0.5) -> Dict:
    """
    Check for 811 "Call Before You Dig" requests near a network site
    
    Args:
        site_id: Site identifier (e.g., site_ashburn_011, site_suwanee_019)
        radius_miles: Search radius in miles (default: 0.5)
    
    Returns:
        Dictionary with 811 dig request information near the site
    """
    logger.info(f"[TOOL CALL] check_811_dig_requests(site_id={site_id}, "
                f"radius_miles={radius_miles})")
    if site_id not in SITE_LOCATIONS:
        return _site_not_found_error(site_id)
    
    location = SITE_LOCATIONS[site_id]
    
    # Find dig requests in the same zip code (simplified proximity check)
    relevant_requests = []
    for request in DIG_REQUESTS:
        if request["zip"] == location["zip"]:
            # Check if request is currently active
            start_date = datetime.fromisoformat(request["start_date"])
            end_date = datetime.fromisoformat(request["end_date"])
            now = datetime.now()
            
            if start_date <= now <= end_date:
                relevant_requests.append(request)
    
    has_dig_activity = len(relevant_requests) > 0
    high_risk = any(r["risk_level"] == "high" for r in relevant_requests)
    
    return {
        "success": True,
        "site_id": site_id,
        "location": {
            "city": location["city"],
            "state": location["state"],
            "zip": location["zip"]
        },
        "search_radius_miles": radius_miles,
        "dig_requests_found": len(relevant_requests),
        "dig_requests": relevant_requests,
        "high_risk_activity": high_risk,
        "correlation_likelihood": "high" if high_risk else ("medium" if has_dig_activity else "none"),
        "recommendation": _get_dig_request_recommendation(relevant_requests, high_risk),
        "timestamp": datetime.now().isoformat()
    }


_WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy",
    3: "Overcast", 45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains", 80: "Slight rain showers",
    81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


@mcp.tool()
def get_real_weather(
    city: Optional[str] = None,
    site_id: Optional[str] = None,
) -> Dict:
    """
    Get real-time weather using the Open-Meteo API (free, no key required).
    Provide either a city name or a site_id.

    Args:
        city: City name (e.g., "Atlanta", "Dallas, TX", "Chicago")
        site_id: Site identifier (e.g., site_ashburn_011). Resolves to the site's city.

    Returns:
        Dictionary with current weather and 3-day forecast
    """
    logger.info(f"[TOOL CALL] get_real_weather(city={city}, site_id={site_id})")

    lat, lon, location_name = None, None, None

    # Resolve coordinates from site_id
    if site_id and site_id in SITE_LOCATIONS:
        loc = SITE_LOCATIONS[site_id]
        lat, lon = loc["lat"], loc["lon"]
        location_name = f"{loc['city']}, {loc['state']}"
    elif site_id:
        return _site_not_found_error(site_id)

    # Resolve coordinates from city name via Open-Meteo geocoding
    if city and lat is None:
        try:
            geo_url = (
                f"https://geocoding-api.open-meteo.com/v1/search?"
                f"name={urllib.parse.quote(city)}&count=1&language=en&format=json"
            )
            with urllib.request.urlopen(geo_url, timeout=5) as resp:
                geo = json.loads(resp.read().decode())
            results = geo.get("results", [])
            if results:
                lat = results[0]["latitude"]
                lon = results[0]["longitude"]
                location_name = (
                    f"{results[0].get('name', city)}, "
                    f"{results[0].get('admin1', '')}"
                )
                logger.info(f"  Geocoded '{city}' -> {lat}, {lon} ({location_name})")
            else:
                return {
                    "success": False,
                    "error": f"City '{city}' not found by geocoding API",
                    "timestamp": datetime.now().isoformat(),
                }
        except Exception as e:
            logger.error(f"  Geocoding failed: {e}")
            return {
                "success": False,
                "error": f"Geocoding failed: {e}",
                "timestamp": datetime.now().isoformat(),
            }

    if lat is None or lon is None:
        return {
            "success": False,
            "error": "Provide either 'city' or 'site_id'",
            "timestamp": datetime.now().isoformat(),
        }

    # Fetch weather
    try:
        api_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,"
            f"apparent_temperature,weather_code,wind_speed_10m,"
            f"wind_gusts_10m,precipitation"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,"
            f"precipitation_sum,wind_speed_10m_max"
            f"&temperature_unit=fahrenheit&wind_speed_unit=mph"
            f"&precipitation_unit=inch&timezone=auto&forecast_days=3"
        )
        with urllib.request.urlopen(api_url, timeout=8) as resp:
            data = json.loads(resp.read().decode())

        current = data.get("current", {})
        daily = data.get("daily", {})
        wmo = current.get("weather_code", 0)

        result = {
            "success": True,
            "location": location_name,
            "coordinates": {"lat": lat, "lon": lon},
            "source": "Open-Meteo (live)",
            "current": {
                "condition": _WMO_CODES.get(wmo, f"Unknown ({wmo})"),
                "wmo_code": wmo,
                "temperature_f": current.get("temperature_2m"),
                "feels_like_f": current.get("apparent_temperature"),
                "humidity_pct": current.get("relative_humidity_2m"),
                "wind_mph": current.get("wind_speed_10m"),
                "wind_gusts_mph": current.get("wind_gusts_10m"),
                "precipitation_inch": current.get("precipitation"),
            },
            "forecast_3day": [],
            "timestamp": datetime.now().isoformat(),
        }

        # Build 3-day forecast
        dates = daily.get("time", [])
        for i, date in enumerate(dates[:3]):
            result["forecast_3day"].append({
                "date": date,
                "condition": _WMO_CODES.get(
                    daily.get("weather_code", [0])[i], "Unknown"
                ),
                "high_f": daily.get("temperature_2m_max", [None])[i],
                "low_f": daily.get("temperature_2m_min", [None])[i],
                "precip_inch": daily.get("precipitation_sum", [None])[i],
                "max_wind_mph": daily.get("wind_speed_10m_max", [None])[i],
            })

        # Flag severity for network ops
        severe = wmo >= 95
        high_wind = (current.get("wind_gusts_10m") or 0) > 50
        if severe or high_wind:
            result["network_impact"] = "HIGH — severe weather may affect infrastructure"
        elif wmo >= 61:
            result["network_impact"] = "MODERATE — monitor outdoor equipment"
        else:
            result["network_impact"] = "LOW — no weather concerns"

        logger.info(f"  Weather: {result['current']['condition']}, "
                     f"{result['current']['temperature_f']}°F")
        return result

    except Exception as e:
        logger.error(f"  Open-Meteo API error: {e}")
        return {
            "success": False,
            "error": f"Weather API unavailable: {e}",
            "timestamp": datetime.now().isoformat(),
        }


@mcp.tool()
def get_external_context_summary(site_id: str, incident_time: Optional[str] = None) -> Dict:
    """
    Get comprehensive external context for a site incident
    Combines power outages, dig requests.
    
    Args:
        site_id: Site identifier (e.g., site_ashburn_011, site_richmond_008)
        incident_time: ISO format timestamp of incident (default: now)
    
    Returns:
        Dictionary with comprehensive external context analysis
    """
    logger.info(f"[TOOL CALL] get_external_context_summary(site_id={site_id}, "
                f"incident_time={incident_time})")
    if site_id not in SITE_LOCATIONS:
        return _site_not_found_error(site_id)
    
    # Get all external context
    power_result = check_power_outages(site_id, time_window_hours=24)
    dig_result = check_811_dig_requests(site_id, radius_miles=0.5)
    weather_result = get_real_weather(site_id)
    
    # Analyze correlations
    correlations = []
    root_cause_likelihood = {}
    
    if power_result.get("outages_found", 0) > 0:
        correlations.append("power_outage")
        root_cause_likelihood["power_outage"] = "high"
    
    if dig_result.get("high_risk_activity", False):
        correlations.append("excavation_damage")
        root_cause_likelihood["excavation_damage"] = "high"
    elif dig_result.get("dig_requests_found", 0) > 0:
        correlations.append("excavation_activity")
        root_cause_likelihood["excavation_damage"] = "medium"

    # Check weather impact
    network_impact = weather_result.get("network_impact", "")
    if "HIGH" in network_impact:
        correlations.append("severe_weather")
        root_cause_likelihood["weather_damage"] = "high"
    elif "MODERATE" in network_impact:
        correlations.append("weather_advisory")
        root_cause_likelihood["weather_damage"] = "medium"
    
    # Generate overall assessment
    if len(correlations) == 0:
        overall_assessment = "No external factors detected. Issue likely internal to network equipment."
        recommended_actions = [
            "Check device logs and configurations",
            "Verify hardware status and error counters",
            "Review recent configuration changes",
            "Test backup power systems"
        ]
    else:
        overall_assessment = f"External factors detected: {', '.join(correlations)}. High likelihood of external root cause."
        recommended_actions = [
            "Coordinate with utility companies for power restoration",
            "Contact excavation contractors if dig activity present",
            "Inspect physical infrastructure for weather damage",
            "Implement temporary workarounds if available",
            "Document incident for insurance/liability purposes"
        ]
    
    return {
        "success": True,
        "site_id": site_id,
        "location": SITE_LOCATIONS[site_id],
        "incident_time": incident_time or datetime.now().isoformat(),
        "external_factors": {
            "power_outages": power_result,
            "dig_requests": dig_result,
            "weather": weather_result,
        },
        "correlations_found": correlations,
        "root_cause_likelihood": root_cause_likelihood,
        "overall_assessment": overall_assessment,
        "recommended_actions": recommended_actions,
        "timestamp": datetime.now().isoformat()
    }


# Helper functions
def _get_power_outage_recommendation(outages: List[Dict]) -> str:
    """Generate recommendation based on power outages"""
    if not outages:
        return "No power outages detected in the area. Power supply is not likely the cause."
    
    ongoing = [o for o in outages if o["status"] == "ongoing"]
    if ongoing:
        return f"ACTIVE POWER OUTAGE detected affecting {ongoing[0]['affected_customers']} customers. Site outage highly likely due to power loss. Contact utility: {ongoing[0]['utility']}"
    else:
        return f"Recent power outage detected (now resolved). Site may have been affected. Verify backup power systems activated correctly."


def _get_dig_request_recommendation(requests: List[Dict], high_risk: bool) -> str:
    """Generate recommendation based on dig requests"""
    if not requests:
        return "No active excavation activity detected nearby. Physical damage from digging is unlikely."
    
    if high_risk:
        return f"HIGH RISK excavation activity detected: {requests[0]['work_type']}. Physical inspection recommended. Contact contractor: {requests[0]['contractor']}"
    else:
        return f"Excavation activity detected nearby: {requests[0]['work_type']}. Monitor for potential cable damage. Low to medium risk."


if __name__ == "__main__":
    # MCP_TRANSPORT env var controls the transport mode:
    # - "http" or "streamable-http": HTTP on port 8000 (AgentCore deployment)
    # - anything else or unset: stdio (local development)
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    
    logger.info(f"Transport mode: {transport}")
    logger.info(f"Registered tools: check_power_outages, check_811_dig_requests, "
                f"get_real_weather, get_external_context_summary")
    
    if transport in ("http", "streamable-http"):
        logger.info("Starting External Context MCP Server (HTTP mode, port 8000)")
        logger.info("Listening on 0.0.0.0:8000/mcp")
        mcp.run(transport="streamable-http")
    else:
        logger.info("Starting External Context MCP Server (stdio mode)")
        mcp.run()

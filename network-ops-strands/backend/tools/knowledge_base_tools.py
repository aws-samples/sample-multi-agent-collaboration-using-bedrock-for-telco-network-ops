"""
Bedrock Knowledge Base Tools
Provides access to troubleshooting articles and historical tickets
"""

import boto3
import os
from typing import Dict, List, Optional
from datetime import datetime

# Initialize Bedrock Agent Runtime client
bedrock_agent_runtime = boto3.client(
    'bedrock-agent-runtime',
    region_name=os.environ.get('AWS_REGION', 'us-east-1')
)

# Knowledge Base ID (set via environment variable or CloudFormation output)
KNOWLEDGE_BASE_ID = os.environ.get('KNOWLEDGE_BASE_ID', '')


def search_knowledge_base(
    query: str,
    max_results: int = 5,
    filter_by_type: Optional[str] = None
) -> Dict:
    """
    Search the Bedrock Knowledge Base for troubleshooting articles and tickets
    
    Args:
        query: Search query (e.g., "site down troubleshooting")
        max_results: Maximum number of results to return (default: 5)
        filter_by_type: Filter by document type: 'article', 'ticket', or None for all
    
    Returns:
        Dictionary with search results from knowledge base
    """
    if not KNOWLEDGE_BASE_ID:
        return {
            "success": False,
            "error": "Knowledge Base ID not configured",
            "results": [],
            "timestamp": datetime.now().isoformat()
        }
    
    try:
        # Build filter if specified
        retrieval_configuration = {
            "vectorSearchConfiguration": {
                "numberOfResults": max_results
            }
        }
        
        if filter_by_type:
            retrieval_configuration["vectorSearchConfiguration"]["filter"] = {
                "equals": {
                    "key": "document_type",
                    "value": filter_by_type
                }
            }
        
        # Query the knowledge base
        response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={
                "text": query
            },
            retrievalConfiguration=retrieval_configuration
        )
        
        # Process results
        results = []
        for item in response.get('retrievalResults', []):
            result = {
                "content": item.get('content', {}).get('text', ''),
                "score": item.get('score', 0.0),
                "location": item.get('location', {}),
                "metadata": item.get('metadata', {})
            }
            results.append(result)
        
        return {
            "success": True,
            "query": query,
            "results_count": len(results),
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Knowledge base search failed: {str(e)}",
            "results": [],
            "timestamp": datetime.now().isoformat()
        }


def search_troubleshooting_articles(issue_type: str, symptoms: List[str]) -> Dict:
    """
    Search for troubleshooting articles based on issue type and symptoms
    
    Args:
        issue_type: Type of issue (e.g., "connectivity", "performance", "power")
        symptoms: List of symptoms (e.g., ["site_down", "no_response", "packet_loss"])
    
    Returns:
        Dictionary with relevant troubleshooting articles
    """
    # Build search query from issue type and symptoms
    query = f"{issue_type} troubleshooting {' '.join(symptoms)}"
    
    result = search_knowledge_base(
        query=query,
        max_results=5,
        filter_by_type="article"
    )
    
    if result["success"] and result["results_count"] > 0:
        # Extract and format articles
        articles = []
        for item in result["results"]:
            article = {
                "title": item["metadata"].get("title", "Untitled Article"),
                "content": item["content"],
                "relevance_score": round(item["score"], 3),
                "category": item["metadata"].get("category", "General"),
                "last_updated": item["metadata"].get("last_updated", "Unknown")
            }
            articles.append(article)
        
        return {
            "success": True,
            "issue_type": issue_type,
            "symptoms": symptoms,
            "articles_found": len(articles),
            "articles": articles,
            "timestamp": datetime.now().isoformat()
        }
    else:
        return {
            "success": False,
            "error": result.get("error", "No articles found"),
            "articles": [],
            "timestamp": datetime.now().isoformat()
        }


def search_similar_tickets(
    issue_description: str,
    site_id: Optional[str] = None,
    max_results: int = 3
) -> Dict:
    """
    Search for similar historical tickets
    
    Args:
        issue_description: Description of the current issue
        site_id: Optional site ID to find site-specific tickets
        max_results: Maximum number of tickets to return (default: 3)
    
    Returns:
        Dictionary with similar historical tickets and their resolutions
    """
    # Build search query
    query = issue_description
    if site_id:
        query = f"{site_id} {issue_description}"
    
    result = search_knowledge_base(
        query=query,
        max_results=max_results,
        filter_by_type="ticket"
    )
    
    if result["success"] and result["results_count"] > 0:
        # Extract and format tickets
        tickets = []
        for item in result["results"]:
            ticket = {
                "ticket_id": item["metadata"].get("ticket_id", "Unknown"),
                "site_id": item["metadata"].get("site_id", "Unknown"),
                "issue_summary": item["metadata"].get("summary", ""),
                "resolution": item["content"],
                "resolution_time": item["metadata"].get("resolution_time", "Unknown"),
                "root_cause": item["metadata"].get("root_cause", "Unknown"),
                "similarity_score": round(item["score"], 3),
                "resolved_date": item["metadata"].get("resolved_date", "Unknown")
            }
            tickets.append(ticket)
        
        return {
            "success": True,
            "issue_description": issue_description,
            "site_id": site_id,
            "tickets_found": len(tickets),
            "similar_tickets": tickets,
            "recommendation": _generate_ticket_recommendation(tickets),
            "timestamp": datetime.now().isoformat()
        }
    else:
        return {
            "success": False,
            "error": result.get("error", "No similar tickets found"),
            "similar_tickets": [],
            "timestamp": datetime.now().isoformat()
        }


def get_troubleshooting_guidance(
    issue_type: str,
    symptoms: List[str],
    site_id: Optional[str] = None
) -> Dict:
    """
    Get comprehensive troubleshooting guidance combining articles and historical tickets
    
    Args:
        issue_type: Type of issue (e.g., "connectivity", "performance")
        symptoms: List of observed symptoms
        site_id: Optional site ID for context
    
    Returns:
        Dictionary with comprehensive troubleshooting guidance
    """
    # Search for articles
    articles_result = search_troubleshooting_articles(issue_type, symptoms)
    
    # Search for similar tickets
    issue_description = f"{issue_type} with symptoms: {', '.join(symptoms)}"
    tickets_result = search_similar_tickets(issue_description, site_id, max_results=3)
    
    # Combine results
    guidance = {
        "success": True,
        "issue_type": issue_type,
        "symptoms": symptoms,
        "site_id": site_id,
        "troubleshooting_articles": articles_result.get("articles", []),
        "similar_incidents": tickets_result.get("similar_tickets", []),
        "recommended_steps": _generate_recommended_steps(
            articles_result.get("articles", []),
            tickets_result.get("similar_tickets", [])
        ),
        "timestamp": datetime.now().isoformat()
    }
    
    return guidance


def _generate_ticket_recommendation(tickets: List[Dict]) -> str:
    """Generate recommendation based on similar tickets"""
    if not tickets:
        return "No similar historical tickets found."
    
    # Get most similar ticket
    top_ticket = tickets[0]
    
    recommendation = f"Similar issue resolved in ticket {top_ticket['ticket_id']}. "
    recommendation += f"Root cause was: {top_ticket['root_cause']}. "
    recommendation += f"Resolution time: {top_ticket['resolution_time']}. "
    recommendation += "Review the resolution steps for guidance."
    
    return recommendation


def _generate_recommended_steps(articles: List[Dict], tickets: List[Dict]) -> List[str]:
    """Generate recommended troubleshooting steps from articles and tickets"""
    steps = []
    
    # Add steps from top article if available
    if articles:
        steps.append(f"Review troubleshooting article: {articles[0]['title']}")
        steps.append("Follow documented procedures for this issue type")
    
    # Add insights from similar tickets
    if tickets:
        top_ticket = tickets[0]
        steps.append(f"Check for similar root cause: {top_ticket['root_cause']}")
        steps.append(f"Reference resolution from ticket {top_ticket['ticket_id']}")
    
    # Add general steps
    steps.extend([
        "Verify physical connectivity and power",
        "Check device logs for errors",
        "Test with diagnostic tools",
        "Escalate if issue persists after initial troubleshooting"
    ])
    
    return steps


# Mock data for local testing (when Knowledge Base is not available)
MOCK_ARTICLES = [
    {
        "title": "Site Down Troubleshooting Guide",
        "content": "When a site goes down, follow these steps: 1) Check power supply, 2) Verify physical connections, 3) Check for alarms, 4) Review recent changes, 5) Test with ping/traceroute",
        "category": "Connectivity",
        "last_updated": "2024-01-15"
    },
    {
        "title": "Power Outage Recovery Procedures",
        "content": "After power restoration: 1) Verify UPS status, 2) Check all equipment powered on, 3) Verify network connectivity, 4) Test services, 5) Document incident",
        "category": "Power",
        "last_updated": "2024-01-20"
    }
]

MOCK_TICKETS = [
    {
        "ticket_id": "INC-2024-001",
        "site_id": "site_dallas_001",
        "issue_summary": "Site down due to power outage",
        "resolution": "Power restored by utility company. All systems came back online automatically. Verified UPS logs showed proper failover.",
        "resolution_time": "2 hours",
        "root_cause": "Utility power outage",
        "resolved_date": "2024-01-10"
    },
    {
        "ticket_id": "INC-2024-002",
        "site_id": "site_birmingham_003",
        "issue_summary": "Site connectivity lost after excavation",
        "resolution": "Fiber cable damaged by contractor. Emergency repair performed. Implemented additional cable protection.",
        "resolution_time": "6 hours",
        "root_cause": "Physical cable damage from excavation",
        "resolved_date": "2024-01-18"
    }
]


def search_knowledge_base_mock(query: str, max_results: int = 5) -> Dict:
    """Mock version for local testing without Knowledge Base"""
    results = []
    
    # Simple keyword matching
    query_lower = query.lower()
    
    for article in MOCK_ARTICLES:
        if any(word in article["content"].lower() for word in query_lower.split()):
            results.append({
                "content": article["content"],
                "score": 0.85,
                "metadata": {
                    "title": article["title"],
                    "category": article["category"],
                    "last_updated": article["last_updated"],
                    "document_type": "article"
                }
            })
    
    for ticket in MOCK_TICKETS:
        if any(word in ticket["issue_summary"].lower() for word in query_lower.split()):
            results.append({
                "content": ticket["resolution"],
                "score": 0.80,
                "metadata": {
                    "ticket_id": ticket["ticket_id"],
                    "site_id": ticket["site_id"],
                    "summary": ticket["issue_summary"],
                    "resolution_time": ticket["resolution_time"],
                    "root_cause": ticket["root_cause"],
                    "resolved_date": ticket["resolved_date"],
                    "document_type": "ticket"
                }
            })
    
    return {
        "success": True,
        "query": query,
        "results_count": len(results[:max_results]),
        "results": results[:max_results],
        "timestamp": datetime.now().isoformat()
    }

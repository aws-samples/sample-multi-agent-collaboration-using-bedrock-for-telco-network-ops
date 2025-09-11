import json
import pandas as pd
import boto3
import os
import logging
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def populate_function_response(event, response_body):
    """Format response according to Bedrock Agent requirements"""
    logger.info(f"Formatting response for Bedrock Agent")
    
    formatted_response = {
        'response': {
            'actionGroup': event.get('actionGroup', 'KPIActionGroup'),
            'function': event.get('function', 'analyze_kpis'),
            'functionResponse': {
                'responseBody': {
                    'TEXT': {
                        'body': str(response_body)
                    }
                }
            }
        }
    }
    
    # Log the final response for easier debugging
    logger.info(f"Final response: {json.dumps(formatted_response)}")
    
    return formatted_response

def analyze_kpi_trends(kpi_data):
    """Analyze KPI metrics and return insights"""
    logger.info("Analyzing KPI trends")
    insights = []
    
    # Calculate averages
    avg_throughput = kpi_data['throughput_mbps'].astype(float).mean()
    avg_latency = kpi_data['latency_ms'].astype(float).mean()
    avg_packet_loss = kpi_data['packet_loss_pct'].astype(float).mean()
    
    logger.info(f"Average metrics - Throughput: {avg_throughput:.2f} Mbps, Latency: {avg_latency:.2f} ms, Packet Loss: {avg_packet_loss:.3f}%")
    
    # Throughput analysis
    if avg_throughput > 2000:
        insights.append("Excellent throughput performance")
    elif avg_throughput > 1000:
        insights.append("Good throughput performance")
    else:
        insights.append("Average throughput performance")
    
    # Latency analysis
    if avg_latency < 15:
        insights.append("Excellent network latency")
    elif avg_latency < 20:
        insights.append("Good network latency")
    else:
        insights.append("Network latency needs attention")
    
    # Packet loss analysis
    if avg_packet_loss < 0.1:
        insights.append("Minimal packet loss")
    elif avg_packet_loss < 0.5:
        insights.append("Acceptable packet loss")
    else:
        insights.append("High packet loss - investigate network issues")
    
    # Check for anomalies
    anomaly_count = len(kpi_data[kpi_data['is_anomaly'] == '1'])
    if anomaly_count > 0:
        insights.append(f"Detected {anomaly_count} anomalies in the recent data")
    
    # Check for resource utilization
    if 'cpu_utilization' in kpi_data.columns and 'memory_utilization' in kpi_data.columns:
        avg_cpu = kpi_data['cpu_utilization'].astype(float).mean()
        avg_memory = kpi_data['memory_utilization'].astype(float).mean()
        
        if avg_cpu > 80:
            insights.append("High CPU utilization - potential resource constraint")
        if avg_memory > 80:
            insights.append("High memory utilization - potential resource constraint")
    
    logger.info(f"KPI analysis insights: {insights}")
    return insights

def lambda_handler(event, context):
    """
    Lambda handler to process KPI analysis requests from Bedrock Agent
    
    Expected CSV columns from initial_data_load:
    - site_id
    - timestamp
    - location
    - connected_users
    - throughput_mbps
    - latency_ms
    - packet_loss_pct
    - cpu_utilization
    - memory_utilization
    - is_anomaly
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Extract site_id from parameters based on Bedrock Agent format
        site_id = None
        
        # Check if this is a direct invocation or from Bedrock Agent
        if 'site_id' in event:
            # Direct invocation
            site_id = event['site_id']
            logger.info(f"Direct invocation with site_id: {site_id}")
        elif 'parameters' in event:
            # Bedrock Agent invocation
            parameters = event.get('parameters', {})
            logger.info(f"Bedrock Agent parameters: {parameters}")
            
            # Extract site_id from parameters
            for param in parameters:
                if param.get('name') == 'site_id':
                    site_id = param.get('value')
                    break
        
        if not site_id:
            error_msg = "Error: No site_id provided in the request"
            logger.error(error_msg)
            return populate_function_response(event, error_msg)
        
        logger.info(f"Processing KPI analysis for site_id: {site_id}")
        
        # Get bucket name from environment variable
        bucket_name = os.environ.get('BUCKET_NAME')
        if not bucket_name:
            error_msg = "Error: BUCKET_NAME environment variable not set"
            logger.error(error_msg)
            return populate_function_response(event, error_msg)
        
        logger.info(f"Using S3 bucket: {bucket_name}")
        s3 = boto3.client('s3')
        
        try:
            # Get KPI data from S3
            logger.info(f"Retrieving KPI data from S3: {bucket_name}/data/kpi_metrics.csv")
            response = s3.get_object(
                Bucket=bucket_name,
                Key='data/kpi_metrics.csv'
            )
            df = pd.read_csv(response['Body'])
            logger.info(f"Successfully retrieved KPI data with {len(df)} records")
            
            # Filter recent KPIs for the site
            site_kpis = df[df['site_id'] == site_id].tail(24)  # Last 24 records
            logger.info(f"Found {len(site_kpis)} recent KPI records for site {site_id}")
            
            if len(site_kpis) == 0:
                error_msg = f"No KPI data found for site {site_id}"
                logger.warning(error_msg)
                return populate_function_response(event, error_msg)
            
            # Find anomalies
            anomalies = site_kpis[site_kpis['is_anomaly'] == '1']
            logger.info(f"Found {len(anomalies)} anomalies in KPI data")
            
            # Analyze KPI trends
            insights = analyze_kpi_trends(site_kpis)
            
            # Calculate summary metrics
            kpi_summary = {
                'throughput_mbps': float(site_kpis['throughput_mbps'].astype(float).mean()),
                'latency_ms': float(site_kpis['latency_ms'].astype(float).mean()),
                'packet_loss_pct': float(site_kpis['packet_loss_pct'].astype(float).mean()),
                'connected_users': int(site_kpis['connected_users'].astype(float).mean()),
                'cpu_utilization': float(site_kpis['cpu_utilization'].astype(float).mean()),
                'memory_utilization': float(site_kpis['memory_utilization'].astype(float).mean())
            }
            
            logger.info(f"KPI summary: {kpi_summary}")
            
            # Prepare response for Bedrock Agent
            response_text = f"KPI ANALYSIS for site {site_id}:\n\n"
            
            # Add summary metrics
            response_text += "PERFORMANCE METRICS (24-hour average):\n"
            response_text += f"Connected Users: {kpi_summary['connected_users']}\n"
            response_text += f"Throughput: {kpi_summary['throughput_mbps']:.2f} Mbps\n"
            response_text += f"Latency: {kpi_summary['latency_ms']:.2f} ms\n"
            response_text += f"Packet Loss: {kpi_summary['packet_loss_pct']:.3f}%\n"
            response_text += f"CPU Utilization: {kpi_summary['cpu_utilization']:.2f}%\n"
            response_text += f"Memory Utilization: {kpi_summary['memory_utilization']:.2f}%\n\n"
            
            # Add insights
            response_text += "ANALYSIS INSIGHTS:\n"
            for insight in insights:
                response_text += f"- {insight}\n"
            response_text += "\n"
            
            # Add anomalies if any
            if len(anomalies) > 0:
                response_text += f"DETECTED ANOMALIES ({len(anomalies)}):\n"
                
                for _, anomaly in anomalies.iterrows():
                    timestamp = anomaly['timestamp']
                    response_text += f"- Anomaly detected at {timestamp}:\n"
                    
                    # Add key metrics for the anomaly
                    response_text += f"  Connected Users: {anomaly['connected_users']}\n"
                    response_text += f"  Throughput: {float(anomaly['throughput_mbps']):.2f} Mbps\n"
                    response_text += f"  Latency: {float(anomaly['latency_ms']):.2f} ms\n"
                    response_text += f"  Packet Loss: {float(anomaly['packet_loss_pct']):.3f}%\n"
                    response_text += "\n"
            else:
                response_text += "No anomalies detected in the current time window.\n"
            
            # Add recommendation
            if len(anomalies) > 0:
                response_text += "RECOMMENDATION: Investigate detected anomalies to prevent potential service degradation.\n"
            elif any("needs attention" in insight for insight in insights):
                response_text += "RECOMMENDATION: Monitor the metrics that need attention to prevent future issues.\n"
            else:
                response_text += "RECOMMENDATION: Continue monitoring. All KPIs are within acceptable ranges.\n"
            
            logger.info(f"Sending KPI analysis response for site {site_id}")
            
            # Return formatted response for Bedrock Agent
            return populate_function_response(event, response_text)
            
        except s3.exceptions.NoSuchKey:
            error_msg = f"Error: KPI data file not found in bucket {bucket_name}"
            logger.error(error_msg)
            return populate_function_response(event, error_msg)
        except s3.exceptions.NoSuchBucket:
            error_msg = f"Error: S3 bucket {bucket_name} not found"
            logger.error(error_msg)
            return populate_function_response(event, error_msg)
        except Exception as e:
            error_msg = f"Error retrieving KPI data: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return populate_function_response(event, error_msg)
            
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return populate_function_response(event, error_msg)

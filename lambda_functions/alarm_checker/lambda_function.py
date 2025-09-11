import json
import pandas as pd
import boto3
import os
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def populate_function_response(event, response_body):
    """Format response according to Bedrock Agent requirements"""
    logger.info(f"Formatting response for Bedrock Agent")
    
    formatted_response = {
        'response': {
            'actionGroup': event.get('actionGroup', 'AlarmActionGroup'),
            'function': event.get('function', 'check_alarms'),
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

def lambda_handler(event, context):
    """
    Lambda handler to process alarm checking requests from Bedrock Agent
    
    Expected CSV columns from initial_data_load:
    - alarm_id
    - site_id
    - alarm_type
    - severity
    - start_time
    - end_time
    - status
    - description
    - affected_service
    - incident_id
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
        
        logger.info(f"Processing alarm check for site_id: {site_id}")
        
        # Get bucket name from environment variable
        bucket_name = os.environ.get('BUCKET_NAME')
        if not bucket_name:
            error_msg = "Error: BUCKET_NAME environment variable not set"
            logger.error(error_msg)
            return populate_function_response(event, error_msg)
        
        logger.info(f"Using S3 bucket: {bucket_name}")
        s3 = boto3.client('s3')
        
        try:
            # Get alarms from S3
            logger.info(f"Retrieving alarm data from S3: {bucket_name}/data/alarms.csv")
            response = s3.get_object(
                Bucket=bucket_name,
                Key='data/alarms.csv'
            )
            df = pd.read_csv(response['Body'])
            logger.info(f"Successfully retrieved alarm data with {len(df)} records")
            
            # Filter active alarms for the site
            site_alarms = df[
                (df['site_id'] == site_id) &
                (df['status'] == 'Active')
            ]
            
            logger.info(f"Found {len(site_alarms)} active alarms for site {site_id}")
            
            # Prepare response for Bedrock Agent
            if len(site_alarms) > 0:
                # Count alarms by severity
                severity_counts = {
                    'Critical': len(site_alarms[site_alarms['severity'] == 'Critical']),
                    'Major': len(site_alarms[site_alarms['severity'] == 'Major']),
                    'Minor': len(site_alarms[site_alarms['severity'] == 'Minor'])
                }
                
                response_text = f"ACTIVE ALARMS for site {site_id}:\n\n"
                response_text += f"Total: {len(site_alarms)} active alarms\n"
                response_text += f"Critical: {severity_counts['Critical']}\n"
                response_text += f"Major: {severity_counts['Major']}\n"
                response_text += f"Minor: {severity_counts['Minor']}\n\n"
                
                # Sort alarms by severity (Critical first)
                severity_order = {'Critical': 0, 'Major': 1, 'Minor': 2}
                site_alarms['severity_order'] = site_alarms['severity'].map(severity_order)
                sorted_alarms = site_alarms.sort_values('severity_order')
                
                # Add detailed alarm information
                response_text += "ALARM DETAILS:\n\n"
                
                for _, alarm in sorted_alarms.iterrows():
                    response_text += (
                        f"Alarm ID: {alarm['alarm_id']}\n"
                        f"Type: {alarm['alarm_type']}\n"
                        f"Severity: {alarm['severity']}\n"
                        f"Description: {alarm['description']}\n"
                        f"Start Time: {alarm['start_time']}\n"
                        f"Affected Service: {alarm['affected_service']}\n"
                        f"Incident ID: {alarm['incident_id']}\n\n"
                    )
                    
                # Add recommendation based on severity
                if severity_counts['Critical'] > 0:
                    response_text += "RECOMMENDATION: Immediate action required. Critical alarms detected.\n"
                elif severity_counts['Major'] > 0:
                    response_text += "RECOMMENDATION: Urgent attention needed. Major severity alarms detected.\n"
                else:
                    response_text += "RECOMMENDATION: Monitor the situation. No critical or major severity alarms detected.\n"
            else:
                response_text = f"No active alarms for site {site_id}. All systems are operating normally."
            
            logger.info(f"Sending alarm response for site {site_id}")
            
            # Return formatted response for Bedrock Agent
            return populate_function_response(event, response_text)
            
        except s3.exceptions.NoSuchKey:
            error_msg = f"Error: Alarm data file not found in bucket {bucket_name}"
            logger.error(error_msg)
            return populate_function_response(event, error_msg)
        except s3.exceptions.NoSuchBucket:
            error_msg = f"Error: S3 bucket {bucket_name} not found"
            logger.error(error_msg)
            return populate_function_response(event, error_msg)
        except Exception as e:
            error_msg = f"Error retrieving alarm data: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return populate_function_response(event, error_msg)
            
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return populate_function_response(event, error_msg)

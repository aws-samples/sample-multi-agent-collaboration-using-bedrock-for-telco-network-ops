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
            'actionGroup': event.get('actionGroup', 'MaintenanceActionGroup'),
            'function': event.get('function', 'check_maintenance'),
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
    Lambda handler to process maintenance schedule requests from Bedrock Agent
    
    Expected CSV columns from initial_data_load:
    - maintenance_id
    - site_id
    - maintenance_type
    - start_time
    - end_time
    - status
    - priority
    - description
    - team
    - requires_outage
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
        
        logger.info(f"Processing maintenance check for site_id: {site_id}")
        
        # Get bucket name from environment variable
        bucket_name = os.environ.get('BUCKET_NAME')
        if not bucket_name:
            error_msg = "Error: BUCKET_NAME environment variable not set"
            logger.error(error_msg)
            return populate_function_response(event, error_msg)
        
        logger.info(f"Using S3 bucket: {bucket_name}")
        s3 = boto3.client('s3')
        
        try:
            # Get maintenance schedule from S3
            logger.info(f"Retrieving maintenance data from S3: {bucket_name}/data/maintenance_schedule.csv")
            response = s3.get_object(
                Bucket=bucket_name,
                Key='data/maintenance_schedule.csv'
            )
            df = pd.read_csv(response['Body'])
            logger.info(f"Successfully retrieved maintenance data with {len(df)} records")
            
            # Filter maintenance for the site
            site_maintenance = df[df['site_id'] == site_id]
            logger.info(f"Found {len(site_maintenance)} maintenance records for site {site_id}")
            
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"Current time: {current_time}")
            
            # Filter for active maintenance
            active_maintenance = site_maintenance[
                (site_maintenance['start_time'] <= current_time) &
                (site_maintenance['end_time'] >= current_time)
            ]
            
            # Filter for upcoming maintenance
            upcoming_maintenance = site_maintenance[
                (site_maintenance['start_time'] > current_time)
            ]
            
            logger.info(f"Found {len(active_maintenance)} active and {len(upcoming_maintenance)} upcoming maintenance activities")
            
            # Prepare response for Bedrock Agent
            if len(active_maintenance) > 0:
                response_text = f"ACTIVE MAINTENANCE FOUND for site {site_id}:\n\n"
                
                for _, maint in active_maintenance.iterrows():
                    response_text += (
                        f"Maintenance ID: {maint['maintenance_id']}\n"
                        f"Type: {maint['maintenance_type']}\n"
                        f"Description: {maint['description']}\n"
                        f"Start Time: {maint['start_time']}\n"
                        f"End Time: {maint['end_time']}\n"
                        f"Status: {maint['status']}\n"
                        f"Priority: {maint['priority']}\n"
                        f"Team: {maint['team']}\n"
                        f"Requires Outage: {maint['requires_outage']}\n\n"
                    )
            else:
                response_text = f"No active maintenance for site {site_id}.\n\n"
            
            if len(upcoming_maintenance) > 0:
                response_text += f"UPCOMING MAINTENANCE for site {site_id}:\n\n"
                
                # Sort by start_time and take the first 3
                upcoming_sorted = upcoming_maintenance.sort_values('start_time').head(3)
                
                for _, maint in upcoming_sorted.iterrows():
                    response_text += (
                        f"Maintenance ID: {maint['maintenance_id']}\n"
                        f"Type: {maint['maintenance_type']}\n"
                        f"Description: {maint['description']}\n"
                        f"Start Time: {maint['start_time']}\n"
                        f"End Time: {maint['end_time']}\n"
                        f"Status: {maint['status']}\n"
                        f"Priority: {maint['priority']}\n"
                        f"Team: {maint['team']}\n"
                        f"Requires Outage: {maint['requires_outage']}\n\n"
                    )
            else:
                response_text += f"No upcoming maintenance scheduled for site {site_id}."
            
            logger.info(f"Sending maintenance response for site {site_id}")
            
            # Return formatted response for Bedrock Agent
            return populate_function_response(event, response_text)
            
        except s3.exceptions.NoSuchKey:
            error_msg = f"Error: Maintenance data file not found in bucket {bucket_name}"
            logger.error(error_msg)
            return populate_function_response(event, error_msg)
        except s3.exceptions.NoSuchBucket:
            error_msg = f"Error: S3 bucket {bucket_name} not found"
            logger.error(error_msg)
            return populate_function_response(event, error_msg)
        except Exception as e:
            error_msg = f"Error retrieving maintenance data: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return populate_function_response(event, error_msg)
            
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return populate_function_response(event, error_msg)

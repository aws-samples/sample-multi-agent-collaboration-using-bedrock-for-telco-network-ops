import json
import boto3
import csv
import io
import os
import uuid
from decimal import Decimal

def lambda_handler(event, context):
    s3 = boto3.client('s3')
    dynamodb = boto3.resource('dynamodb')
    
    # Get bucket and key from event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    
    print(f"Processing file: {key} from bucket: {bucket}")
    
    # Determine which table to update based on the file name
    if 'alarms.csv' in key:
        table = dynamodb.Table(os.environ['ALARMS_TABLE'])
        id_field = 'alarm_id'
        id_prefix = 'ALM'
    elif 'kpi_metrics.csv' in key:
        table = dynamodb.Table(os.environ['KPI_METRICS_TABLE'])
        id_field = 'timestamp'
        id_prefix = None  # timestamp is already unique
    elif 'maintenance_schedule.csv' in key:
        table = dynamodb.Table(os.environ['MAINTENANCE_TABLE'])
        id_field = 'maintenance_id'
        id_prefix = 'MNT'
    elif 'sites.csv' in key:
        table = dynamodb.Table(os.environ['SITES_TABLE'])
        id_field = 'site_id'
        id_prefix = None  # site_id is already unique
    else:
        print(f"Ignoring file: {key}")
        return {
            'statusCode': 200,
            'body': json.dumps(f"Ignored file: {key}")
        }
    
    # Get the file from S3
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        csv_content = response['Body'].read().decode('utf-8')
    except Exception as e:
        print(f"Error getting file from S3: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f"Error getting file from S3: {str(e)}"})
        }
    
    # Parse CSV
    try:
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        items = []
        
        for row in csv_reader:
            # Convert empty strings to None
            item = {k: (v if v != '' else None) for k, v in row.items()}
            
            # Generate ID if needed
            if id_prefix and (id_field not in item or not item[id_field]):
                item[id_field] = f"{id_prefix}-{str(uuid.uuid4())[:8]}"
            
            # Convert numeric strings to Decimal for DynamoDB
            for key, value in item.items():
                if value is not None:
                    try:
                        if '.' in value:  # Potential float
                            item[key] = Decimal(str(float(value)))
                        elif value.isdigit():  # Integer
                            item[key] = Decimal(value)
                    except (ValueError, TypeError):
                        pass  # Keep as string if not numeric
            
            items.append(item)
    except Exception as e:
        print(f"Error parsing CSV: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f"Error parsing CSV: {str(e)}"})
        }
    
    # Clear existing data (optional - depends on your update strategy)
    try:
        # This is a simple approach; for large tables, you might want to be more selective
        # For example, only delete items that match the site_ids in the new data
        
        # Get all existing items
        scan_response = table.scan(ProjectionExpression=f"site_id, {id_field}")
        existing_items = scan_response['Items']
        
        # Continue scanning if we haven't got all items
        while 'LastEvaluatedKey' in scan_response:
            scan_response = table.scan(
                ProjectionExpression=f"site_id, {id_field}",
                ExclusiveStartKey=scan_response['LastEvaluatedKey']
            )
            existing_items.extend(scan_response['Items'])
        
        # Delete in batches
        with table.batch_writer() as batch:
            for item in existing_items:
                batch.delete_item(
                    Key={
                        'site_id': item['site_id'],
                        id_field: item[id_field]
                    }
                )
        
        print(f"Cleared {len(existing_items)} existing items from {table.name}")
    except Exception as e:
        print(f"Error clearing existing data: {str(e)}")
        # Continue with insert even if clear fails
    
    # Insert new data
    try:
        with table.batch_writer() as batch:
            for item in items:
                batch.put_item(Item=item)
        
        print(f"Successfully inserted {len(items)} items into {table.name}")
    except Exception as e:
        print(f"Error inserting data: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f"Error inserting data: {str(e)}"})
        }
    
    return {
        'statusCode': 200,
        'body': json.dumps(f"Successfully updated {table.name} from {key} with {len(items)} items")
    }

import boto3
import json
import os
import time
import cfnresponse
import logging
import uuid
import io
import zipfile
import traceback

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
lambda_client = boto3.client('lambda', region_name='us-east-1')  # Lambda@Edge must be in us-east-1
cognito_client = boto3.client('cognito-idp')
cloudfront_client = boto3.client('cloudfront')

def lambda_handler(event, context):
    """
    Custom resource handler to create and configure the Lambda@Edge function for authentication
    
    This function implements robust error handling to ensure CloudFormation always receives
    a response, preventing stuck stacks.
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    # Extract properties from the event
    properties = event.get('ResourceProperties', {})
    stack_name = properties.get('StackName')
    region = properties.get('Region')
    account_id = properties.get('AccountId')
    user_pool_id = properties.get('UserPoolId')
    client_id = properties.get('ClientId')
    cloudfront_distribution_id = properties.get('CloudFrontDistributionId')
    cloudfront_domain = properties.get('CloudFrontDomain')
    
    # Get physical resource ID or generate a new one
    physical_id = event.get('PhysicalResourceId', f"auth-edge-{uuid.uuid4()}")
    
    # Ensure we always send a response to CloudFormation
    try:
        if event['RequestType'] == 'Create' or event['RequestType'] == 'Update':
            logger.info(f"Processing {event['RequestType']} request")
            
            # Step 1: Get the client secret
            try:
                logger.info("Getting client secret")
                client_secret = get_client_secret(user_pool_id, client_id)
                logger.info("Successfully retrieved client secret")
            except Exception as e:
                logger.error(f"Error getting client secret: {str(e)}")
                logger.error(traceback.format_exc())
                cfnresponse.send(event, context, cfnresponse.FAILED, 
                                {"Error": f"Failed to get client secret: {str(e)}"}, 
                                physical_id)
                return
            
            # Step 2: Update Cognito App Client
            try:
                logger.info("Updating Cognito app client")
                update_cognito_app_client(user_pool_id, client_id, cloudfront_domain)
                logger.info("Successfully updated Cognito app client")
            except Exception as e:
                logger.error(f"Error updating Cognito app client: {str(e)}")
                logger.error(traceback.format_exc())
                cfnresponse.send(event, context, cfnresponse.FAILED, 
                                {"Error": f"Failed to update Cognito app client: {str(e)}"}, 
                                physical_id)
                return
            
            # Step 3: Create or update the Lambda@Edge function
            function_name = f"{stack_name}-cf-auth"
            cognito_domain = f"{stack_name}-{account_id}.auth.{region}.amazoncognito.com"
            redirect_uri = f"https://{cloudfront_domain}/oauth2/idpresponse"
            
            try:
                logger.info(f"Creating/updating Lambda function: {function_name}")
                lambda_arn = create_or_update_lambda_function(
                    function_name=function_name,
                    cognito_domain=cognito_domain,
                    client_id=client_id,
                    client_secret=client_secret,
                    redirect_uri=redirect_uri
                )
                logger.info(f"Successfully created/updated Lambda function: {lambda_arn}")
            except Exception as e:
                logger.error(f"Error creating/updating Lambda function: {str(e)}")
                logger.error(traceback.format_exc())
                cfnresponse.send(event, context, cfnresponse.FAILED, 
                                {"Error": f"Failed to create/update Lambda function: {str(e)}"}, 
                                physical_id)
                return
            
            # Step 4: Publish a new version
            try:
                logger.info(f"Publishing new version of Lambda function: {function_name}")
                
                # Wait for the Lambda function to be active and not updating
                logger.info("Waiting for Lambda function to be active and not updating...")
                max_wait_time = 60  # Increased to 60 seconds
                wait_interval = 2   # seconds
                total_waited = 0
                
                while total_waited < max_wait_time:
                    # Check function state and update status
                    function_config = lambda_client.get_function_configuration(FunctionName=function_name)
                    state = function_config.get('State')
                    last_update_status = function_config.get('LastUpdateStatus', 'Successful')  # Default to Successful if not present
                    
                    logger.info(f"Function state: {state}, Last update status: {last_update_status}")
                    
                    if state == 'Active' and last_update_status == 'Successful':
                        logger.info(f"Lambda function is active and not updating after waiting {total_waited} seconds")
                        break
                        
                    logger.info(f"Waiting for Lambda function to be ready. Current state: {state}, Update status: {last_update_status}. Waiting {wait_interval} seconds...")
                    time.sleep(wait_interval)
                    total_waited += wait_interval
                
                if total_waited >= max_wait_time:
                    raise TimeoutError(f"Lambda function did not become ready within {max_wait_time} seconds")
                
                # Add an additional safety delay
                safety_delay = 5
                logger.info(f"Adding a safety delay of {safety_delay} seconds before publishing...")
                time.sleep(safety_delay)
                
                # Now publish the version
                version = publish_lambda_version(function_name)
                logger.info(f"Successfully published version {version}")
            except Exception as e:
                logger.error(f"Error publishing Lambda version: {str(e)}")
                logger.error(traceback.format_exc())
                cfnresponse.send(event, context, cfnresponse.FAILED, 
                                {"Error": f"Failed to publish Lambda version: {str(e)}"}, 
                                physical_id)
                return
            
            # Step 5: Associate with CloudFront
            lambda_version_arn = f"arn:aws:lambda:us-east-1:{account_id}:function:{function_name}:{version}"
            try:
                logger.info(f"Associating Lambda with CloudFront: {cloudfront_distribution_id}")
                
                # Wait for the Lambda version to be fully published and ready
                logger.info("Waiting for Lambda version to be ready...")
                max_wait_time = 15  # seconds
                wait_interval = 1   # seconds
                total_waited = 0
                
                while total_waited < max_wait_time:
                    try:
                        # Try to get the version - if it's ready, this will succeed
                        lambda_client.get_function(FunctionName=lambda_version_arn)
                        logger.info(f"Lambda version is now ready after waiting {total_waited} seconds")
                        break
                    except lambda_client.exceptions.ResourceNotFoundException:
                        logger.info(f"Lambda version not ready yet. Waiting {wait_interval} seconds...")
                        time.sleep(wait_interval)
                        total_waited += wait_interval
                
                if total_waited >= max_wait_time:
                    logger.warning(f"Lambda version might not be fully ready after {max_wait_time} seconds, but proceeding anyway")
                
                associate_lambda_with_cloudfront(
                    distribution_id=cloudfront_distribution_id,
                    lambda_arn=lambda_version_arn
                )
                logger.info("Successfully associated Lambda with CloudFront")
            except Exception as e:
                logger.error(f"Error associating Lambda with CloudFront: {str(e)}")
                logger.error(traceback.format_exc())
                cfnresponse.send(event, context, cfnresponse.FAILED, 
                                {"Error": f"Failed to associate Lambda with CloudFront: {str(e)}"}, 
                                physical_id)
                return
            
            # All steps completed successfully
            response_data = {
                'LambdaArn': lambda_arn,
                'LambdaVersionArn': lambda_version_arn,
                'Version': version
            }
            logger.info(f"All steps completed successfully. Sending SUCCESS response with data: {response_data}")
            cfnresponse.send(event, context, cfnresponse.SUCCESS, response_data, physical_id)
            
        elif event['RequestType'] == 'Delete':
            logger.info("Processing Delete request")
            try:
                # Extract necessary information
                function_name = f"{stack_name}-cf-auth"
                
                # Step 1: Remove Lambda@Edge association from CloudFront
                try:
                    logger.info(f"Removing Lambda@Edge association from CloudFront: {cloudfront_distribution_id}")
                    remove_lambda_from_cloudfront(cloudfront_distribution_id)
                    logger.info("Successfully removed Lambda@Edge association from CloudFront")
                except Exception as e:
                    logger.warning(f"Error removing Lambda@Edge association: {str(e)}")
                    logger.warning(traceback.format_exc())
                    # Continue with deletion even if this step fails
                
                # Step 2: Delete all versions of the Lambda function
                try:
                    logger.info(f"Deleting all versions of Lambda function: {function_name}")
                    delete_lambda_versions(function_name)
                    logger.info("Successfully deleted all Lambda versions")
                except Exception as e:
                    logger.warning(f"Error deleting Lambda versions: {str(e)}")
                    logger.warning(traceback.format_exc())
                    # Continue with deletion even if this step fails
                
                # Send success response to CloudFormation
                cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, physical_id)
            except Exception as e:
                logger.error(f"Error during Delete operation: {str(e)}")
                logger.error(traceback.format_exc())
                cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": str(e)}, physical_id)
            
    except Exception as e:
        # Catch-all exception handler to ensure we always send a response
        logger.error(f"Unexpected error in lambda_handler: {str(e)}")
        logger.error(traceback.format_exc())
        cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": str(e)}, physical_id)

def get_client_secret(user_pool_id, client_id):
    """
    Get the client secret for a Cognito app client
    """
    response = cognito_client.describe_user_pool_client(
        UserPoolId=user_pool_id,
        ClientId=client_id
    )
    return response['UserPoolClient']['ClientSecret']

def update_cognito_app_client(user_pool_id, client_id, cloudfront_domain):
    """
    Update the Cognito app client to use Cognito as identity provider
    """
    # Get current client configuration
    response = cognito_client.describe_user_pool_client(
        UserPoolId=user_pool_id,
        ClientId=client_id
    )
    
    client_config = response['UserPoolClient']
    
    # Update the client with Cognito as identity provider
    cognito_client.update_user_pool_client(
        UserPoolId=user_pool_id,
        ClientId=client_id,
        ClientName=client_config['ClientName'],
        RefreshTokenValidity=client_config.get('RefreshTokenValidity', 30),
        AccessTokenValidity=client_config.get('AccessTokenValidity', 1),
        IdTokenValidity=client_config.get('IdTokenValidity', 1),
        TokenValidityUnits=client_config.get('TokenValidityUnits', {
            'AccessToken': 'hours',
            'IdToken': 'hours',
            'RefreshToken': 'days'
        }),
        CallbackURLs=[f"https://{cloudfront_domain}/oauth2/idpresponse"],
        LogoutURLs=[f"https://{cloudfront_domain}"],
        AllowedOAuthFlows=client_config.get('AllowedOAuthFlows', ['code']),
        AllowedOAuthScopes=client_config.get('AllowedOAuthScopes', ['email', 'openid', 'profile']),
        SupportedIdentityProviders=['COGNITO'],
        AllowedOAuthFlowsUserPoolClient=True,
        PreventUserExistenceErrors='ENABLED',
        ExplicitAuthFlows=client_config.get('ExplicitAuthFlows', ['ALLOW_REFRESH_TOKEN_AUTH', 'ALLOW_USER_SRP_AUTH'])
        # Removed GenerateSecret=True as it's not allowed in update operations
    )

def create_or_update_lambda_function(function_name, cognito_domain, client_id, client_secret, redirect_uri):
    """
    Create or update the Lambda@Edge function with the correct configuration
    """
    # Read the Lambda function code
    try:
        with open('lambda_function.js', 'r') as f:
            code = f.read()
    except FileNotFoundError:
        # For testing in AWS Lambda console, use a relative path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(script_dir, 'lambda_function.js'), 'r') as f:
            code = f.read()
    
    # Replace placeholders with actual values
    code = code.replace('COGNITO_DOMAIN_PLACEHOLDER', cognito_domain)
    code = code.replace('CLIENT_ID_PLACEHOLDER', client_id)
    code = code.replace('CLIENT_SECRET_PLACEHOLDER', client_secret)
    code = code.replace('REDIRECT_URI_PLACEHOLDER', redirect_uri)
    
    # Check if the function already exists
    try:
        lambda_client.get_function(FunctionName=function_name)
        # Function exists, update it
        response = lambda_client.update_function_code(
            FunctionName=function_name,
            ZipFile=create_zip_file(code),
            Publish=False
        )
    except lambda_client.exceptions.ResourceNotFoundException:
        # Function doesn't exist, create it
        role_arn = os.environ.get('LAMBDA_ROLE_ARN')
        if not role_arn:
            raise ValueError("LAMBDA_ROLE_ARN environment variable is not set")
            
        response = lambda_client.create_function(
            FunctionName=function_name,
            Runtime='nodejs16.x',
            Role=role_arn,
            Handler='index.handler',
            Code={
                'ZipFile': create_zip_file(code)
            },
            Description='Authentication Lambda@Edge function',
            Timeout=5,
            MemorySize=128,
            Publish=False
        )
    
    return response['FunctionArn']

def publish_lambda_version(function_name):
    """
    Publish a new version of the Lambda function
    """
    response = lambda_client.publish_version(
        FunctionName=function_name,
        Description='Version for Lambda@Edge'
    )
    return response['Version']

def associate_lambda_with_cloudfront(distribution_id, lambda_arn):
    """
    Associate the Lambda@Edge function with CloudFront
    """
    # Get the current distribution configuration
    response = cloudfront_client.get_distribution_config(
        Id=distribution_id
    )
    
    etag = response['ETag']
    config = response['DistributionConfig']
    
    # Update the Lambda function associations
    config['DefaultCacheBehavior']['LambdaFunctionAssociations'] = {
        'Quantity': 1,
        'Items': [
            {
                'EventType': 'viewer-request',
                'LambdaFunctionARN': lambda_arn,
                'IncludeBody': False
            }
        ]
    }
    
    # Update the distribution
    cloudfront_client.update_distribution(
        Id=distribution_id,
        IfMatch=etag,
        DistributionConfig=config
    )
    
    # Create an invalidation to clear the cache
    cloudfront_client.create_invalidation(
        DistributionId=distribution_id,
        InvalidationBatch={
            'Paths': {
                'Quantity': 1,
                'Items': ['/*']
            },
            'CallerReference': str(uuid.uuid4())
        }
    )

def create_zip_file(code):
    """
    Create a ZIP file containing the Lambda function code
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr('index.js', code)
    
    zip_buffer.seek(0)
    return zip_buffer.read()

def remove_lambda_from_cloudfront(distribution_id):
    """
    Remove Lambda@Edge association from CloudFront distribution
    """
    # Get the current distribution configuration
    response = cloudfront_client.get_distribution_config(
        Id=distribution_id
    )
    
    etag = response['ETag']
    config = response['DistributionConfig']
    
    # Remove the Lambda function associations
    if 'LambdaFunctionAssociations' in config['DefaultCacheBehavior']:
        config['DefaultCacheBehavior']['LambdaFunctionAssociations'] = {
            'Quantity': 0,
            'Items': []
        }
    
    # Update the distribution
    cloudfront_client.update_distribution(
        Id=distribution_id,
        IfMatch=etag,
        DistributionConfig=config
    )
    
    # Create an invalidation to clear the cache
    cloudfront_client.create_invalidation(
        DistributionId=distribution_id,
        InvalidationBatch={
            'Paths': {
                'Quantity': 1,
                'Items': ['/*']
            },
            'CallerReference': str(uuid.uuid4())
        }
    )

def delete_lambda_versions(function_name):
    """
    Delete all versions of a Lambda function
    """
    # List all versions
    versions = []
    marker = None
    
    while True:
        if marker:
            response = lambda_client.list_versions_by_function(
                FunctionName=function_name,
                Marker=marker
            )
        else:
            response = lambda_client.list_versions_by_function(
                FunctionName=function_name
            )
        
        versions.extend([v['Version'] for v in response['Versions'] if v['Version'] != '$LATEST'])
        
        if 'NextMarker' in response:
            marker = response['NextMarker']
        else:
            break
    
    # Delete each version
    for version in versions:
        try:
            logger.info(f"Deleting version {version} of function {function_name}")
            lambda_client.delete_function(
                FunctionName=function_name,
                Qualifier=version
            )
        except Exception as e:
            logger.warning(f"Error deleting version {version}: {str(e)}")
    
    # Wait for all versions to be deleted
    time.sleep(5)
    
    # Try to delete the $LATEST version
    try:
        lambda_client.delete_function(
            FunctionName=function_name
        )
    except Exception as e:
        logger.warning(f"Error deleting $LATEST version: {str(e)}")

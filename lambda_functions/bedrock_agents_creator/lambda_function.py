import boto3
import json
import os
import time
import cfnresponse
import logging
import uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock_agent = boto3.client('bedrock-agent')
bedrock = boto3.client('bedrock')
lambda_client = boto3.client('lambda')
iam_client = boto3.client('iam')
sts_client = boto3.client('sts')

# Constants
AGENT_FOUNDATION_MODEL = 'amazon.nova-lite-v1:0'
SUPERVISOR_AGENT_FOUNDATION_MODEL = 'amazon.nova-lite-v1:0'

def create_agent(name, description, instruction, model_id, agent_role_arn, agent_collaboration=None):
    """Create a Bedrock agent"""
    try:
        logger.info(f"Creating agent: {name}")
        create_params = {
            'agentName': name,
            'description': description,
            'instruction': instruction,
            'foundationModel': model_id,
            'agentResourceRoleArn': agent_role_arn,
            'idleSessionTTLInSeconds': 300
        }
        
        if agent_collaboration:
            create_params['agentCollaboration'] = agent_collaboration
            
        response = bedrock_agent.create_agent(**create_params)
        agent_id = response['agent']['agentId']
        agent_version = 'DRAFT'
        
        logger.info(f"Successfully created agent: {name} with ID: {agent_id}")
        return agent_id, response['agent']['agentArn']
    except Exception as e:
        logger.warning(f"Error creating agent {name}: {str(e)}")
        raise

def disassociate_all_collaborators(agent_id):
    """Disassociate all collaborators from a supervisor agent"""
    try:
        logger.info(f"Disassociating all collaborators from agent {agent_id}")
        
        # List all collaborators
        response = bedrock_agent.list_agent_collaborators(
            agentId=agent_id,
            agentVersion='DRAFT'
        )
        
        # Disassociate each collaborator
        for collaborator in response.get('agentCollaborators', []):
            collaborator_name = collaborator.get('collaboratorName', 'Unknown')
            logger.info(f"Disassociating collaborator {collaborator_name} from agent {agent_id}")
            
            try:
                bedrock_agent.disassociate_agent_collaborator(
                    agentId=agent_id,
                    agentVersion='DRAFT',
                    collaboratorName=collaborator_name
                )
                logger.info(f"Successfully disassociated collaborator {collaborator_name} from agent {agent_id}")
            except Exception as e:
                logger.warning(f"Error disassociating collaborator {collaborator_name} from agent {agent_id}: {str(e)}")
        
        return True
    except Exception as e:
        logger.warning(f"Error disassociating collaborators from agent {agent_id}: {str(e)}")
        return False

def delete_agent(agent_id):
    """Delete a Bedrock agent"""
    try:
        logger.info(f"Deleting agent {agent_id}")
        
        # First, disassociate all collaborators if this is a supervisor agent
        try:
            # Check if this is a supervisor agent
            response = bedrock_agent.get_agent(agentId=agent_id)
            if response['agent'].get('agentCollaboration') == 'SUPERVISOR':
                logger.info(f"Agent {agent_id} is a supervisor agent, disassociating collaborators")
                disassociate_all_collaborators(agent_id)
        except Exception as e:
            logger.warning(f"Error checking if agent {agent_id} is a supervisor: {str(e)}")
        
        # Then, delete all aliases
        try:
            aliases_response = bedrock_agent.list_agent_aliases(agentId=agent_id)
            for alias in aliases_response.get('agentAliasSummaries', []):
                alias_id = alias['agentAliasId']
                logger.info(f"Deleting alias {alias_id} for agent {agent_id}")
                
                # Try to disassociate this alias from any supervisor agents
                try:
                    # List all agents
                    agents_response = bedrock_agent.list_agents()
                    for agent in agents_response.get('agentSummaries', []):
                        supervisor_id = agent['agentId']
                        if supervisor_id != agent_id:  # Skip the current agent
                            try:
                                # Check if this is a supervisor agent
                                agent_response = bedrock_agent.get_agent(agentId=supervisor_id)
                                if agent_response['agent'].get('agentCollaboration') == 'SUPERVISOR':
                                    # List collaborators for this supervisor
                                    collab_response = bedrock_agent.list_agent_collaborators(
                                        agentId=supervisor_id,
                                        agentVersion='DRAFT'
                                    )
                                    # Check if our alias is a collaborator
                                    for collaborator in collab_response.get('agentCollaborators', []):
                                        if alias['agentAliasArn'] in str(collaborator):
                                            collaborator_name = collaborator.get('collaboratorName', 'Unknown')
                                            logger.info(f"Disassociating alias {alias_id} as collaborator {collaborator_name} from supervisor {supervisor_id}")
                                            bedrock_agent.disassociate_agent_collaborator(
                                                agentId=supervisor_id,
                                                agentVersion='DRAFT',
                                                collaboratorName=collaborator_name
                                            )
                            except Exception as e:
                                logger.warning(f"Error checking supervisor {supervisor_id}: {str(e)}")
                except Exception as e:
                    logger.warning(f"Error listing agents: {str(e)}")
                
                # Now try to delete the alias with retry logic
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        bedrock_agent.delete_agent_alias(
                            agentId=agent_id,
                            agentAliasId=alias_id
                        )
                        logger.info(f"Successfully deleted alias {alias_id} for agent {agent_id}")
                        # Wait a bit for the alias deletion to propagate
                        time.sleep(5)
                        break
                    except Exception as e:
                        logger.warning(f"Attempt {retry+1}/{max_retries} failed to delete alias {alias_id} for agent {agent_id}: {str(e)}")
                        if retry < max_retries - 1:
                            time.sleep(10)  # Wait longer between retries
        except Exception as e:
            logger.warning(f"Error deleting aliases for agent {agent_id}: {str(e)}")
        
        # Finally, delete the agent with retry logic
        max_retries = 3
        for retry in range(max_retries):
            try:
                bedrock_agent.delete_agent(agentId=agent_id)
                logger.info(f"Successfully deleted agent {agent_id}")
                return True
            except Exception as e:
                logger.warning(f"Attempt {retry+1}/{max_retries} failed to delete agent {agent_id}: {str(e)}")
                if retry < max_retries - 1:
                    time.sleep(15)  # Wait longer between retries
        
        # If we get here, all retries failed
        logger.error(f"Failed to delete agent {agent_id} after {max_retries} attempts")
        return False
    except Exception as e:
        logger.error(f"Error deleting agent {agent_id}: {str(e)}")
        # Don't raise the exception, as we want to continue with other deletions
        return False

def wait_for_agent_not_creating(agent_id, agent_name=None):
    """Wait for agent to be in any state other than CREATING"""
    agent_display = f"{agent_name} (ID: {agent_id})" if agent_name else agent_id
    logger.info(f"Waiting for agent {agent_display} to finish creating")
    attempt = 0
    max_attempts = 15
    while attempt < max_attempts:
        response = bedrock_agent.get_agent(agentId=agent_id)
        status = response['agent']['agentStatus']
        if status != 'CREATING':
            logger.info(f"Agent {agent_display} is now in {status} state")
            return True
        elif status == 'FAILED':
            logger.error(f"Agent {agent_display} creation failed: {response['agent'].get('failureReason', 'Unknown reason')}")
            raise Exception(f"Agent {agent_display} creation failed")
        
        logger.info(f"Agent {agent_display} is still in CREATING state. Waiting... (Attempt {attempt+1}/{max_attempts})")
        time.sleep(10)
        attempt += 1
    
    raise Exception(f"Timed out waiting for agent {agent_display} to finish creating")

def wait_for_agent_prepared(agent_id, agent_name=None):
    """Wait for agent to be in PREPARED state"""
    agent_display = f"{agent_name} (ID: {agent_id})" if agent_name else agent_id
    logger.info(f"Waiting for agent {agent_display} to be in PREPARED state")
    attempt = 0
    max_attempts = 20
    while attempt < max_attempts:
        response = bedrock_agent.get_agent(agentId=agent_id)
        status = response['agent']['agentStatus']
        if status == 'PREPARED':
            logger.info(f"Agent {agent_display} is now PREPARED")
            return True
        elif status == 'FAILED':
            logger.error(f"Agent {agent_display} preparation failed: {response['agent'].get('failureReason', 'Unknown reason')}")
            raise Exception(f"Agent {agent_display} preparation failed")
        
        logger.info(f"Agent {agent_display} is in {status} state. Waiting... (Attempt {attempt+1}/{max_attempts})")
        time.sleep(10)
        attempt += 1
    
    raise Exception(f"Timed out waiting for agent {agent_display} to be PREPARED")

def wait_for_alias_active(agent_id, alias_id, agent_name=None, max_attempts=5):
    """Wait for agent alias to be in PREPARED state"""
    agent_display = f"{agent_name} (ID: {agent_id})" if agent_name else agent_id
    logger.info(f"Waiting for alias {alias_id} of agent {agent_display} to be active")
    attempt = 0
    while attempt < max_attempts:
        try:
            response = bedrock_agent.get_agent_alias(
                agentId=agent_id,
                agentAliasId=alias_id
            )
            
            # Check the status of the alias using the correct attribute name
            if 'agentAliasStatus' in response['agentAlias']:
                status = response['agentAlias']['agentAliasStatus']
                if status == 'PREPARED':
                    logger.info(f"Alias {alias_id} of agent {agent_display} is now PREPARED")
                    return True
                elif status == 'FAILED':
                    logger.error(f"Alias {alias_id} of agent {agent_display} creation failed: {response['agentAlias'].get('failureReason', 'Unknown reason')}")
                    raise Exception(f"Alias {alias_id} of agent {agent_display} creation failed")
                
                logger.info(f"Alias {alias_id} of agent {agent_display} is in {status} state. Waiting... (Attempt {attempt+1}/{max_attempts})")
            else:
                logger.info(f"Alias {alias_id} of agent {agent_display} exists but status is not available yet. Waiting... (Attempt {attempt+1}/{max_attempts})")
                logger.info(f"Available fields: {list(response['agentAlias'].keys())}")
            
            time.sleep(10)
            attempt += 1
        except Exception as e:
            logger.warning(f"Error checking alias status: {str(e)}. Retrying... (Attempt {attempt+1}/{max_attempts})")
            time.sleep(10)
            attempt += 1
    
    raise Exception(f"Timed out waiting for alias {alias_id} of agent {agent_display} to be active")

def create_action_group(agent_id, action_group_name, description, lambda_arn, functions):
    """Create an action group for an agent"""
    try:
        # Wait for agent to finish creating before adding action group
        wait_for_agent_not_creating(agent_id)
        
        bedrock_agent.create_agent_action_group(
            agentId=agent_id,
            agentVersion='DRAFT',
            actionGroupName=action_group_name,
            actionGroupExecutor={
                'lambda': lambda_arn
            },
            description=description,
            actionGroupState='ENABLED',
            functionSchema={
                'functions': functions
            }
        )
        
        # Add permission for Bedrock to invoke the Lambda
        try:
            # Extract account ID from the Lambda ARN if available, otherwise from context
            lambda_account_id = lambda_arn.split(':')[4] if ':' in lambda_arn else None
            lambda_region = lambda_arn.split(':')[3] if ':' in lambda_arn else os.environ.get('AWS_REGION', 'us-east-1')
            
            # If we couldn't extract account ID from Lambda ARN, get it from the Lambda client
            if not lambda_account_id:
                lambda_account_id = boto3.client('sts').get_caller_identity()['Account']
            
            lambda_client.add_permission(
                FunctionName=lambda_arn.split(':')[-1],
                StatementId=f'bedrock-{agent_id}',
                Action='lambda:InvokeFunction',
                Principal='bedrock.amazonaws.com',
                SourceArn=f"arn:aws:bedrock:{lambda_region}:{lambda_account_id}:agent/{agent_id}"
            )
        except lambda_client.exceptions.ResourceConflictException:
            # Permission already exists
            logger.info(f"Lambda permission already exists for agent {agent_id}")
            pass
            
        return True
    except Exception as e:
        logger.warning(f"Error creating action group {action_group_name}: {str(e)}")
        raise

def prepare_agent(agent_id, agent_name=None):
    """Prepare an agent and create an alias"""
    try:
        agent_display = f"{agent_name} (ID: {agent_id})" if agent_name else agent_id
        
        # First, wait for agent to be in NOT_PREPARED state
        wait_for_agent_not_creating(agent_id, agent_name)
        
        # Now prepare the agent
        logger.info(f"Preparing agent {agent_display}")
        bedrock_agent.prepare_agent(agentId=agent_id)
        
        # Wait for preparation to complete with a reasonable timeout
        max_attempts = 30
        attempt = 0
        while attempt < max_attempts:
            response = bedrock_agent.get_agent(agentId=agent_id)
            status = response['agent']['agentStatus']
            if status == 'PREPARED':
                break
            elif status == 'FAILED':
                raise Exception(f"Agent preparation failed for {agent_display}: {response['agent'].get('failureReason', 'Unknown reason')}")
            
            # Wait 10 seconds between checks
            logger.info(f"Agent {agent_display} is in {status} state. Waiting for PREPARED... (Attempt {attempt+1}/{max_attempts})")
            time.sleep(10)
            attempt += 1
            
        if attempt >= max_attempts:
            raise Exception(f"Timed out waiting for agent {agent_display} to be prepared")
        
        # Create alias
        logger.info(f"Creating alias for agent {agent_display}")
        alias_response = bedrock_agent.create_agent_alias(
            agentId=agent_id,
            agentAliasName='prod'
        )
        
        alias_id = alias_response['agentAlias']['agentAliasId']
        alias_arn = alias_response['agentAlias']['agentAliasArn']
        
        # Wait for alias to be active
        wait_for_alias_active(agent_id, alias_id, agent_name)
        
        logger.info(f"Successfully created alias for agent {agent_display}")
        return alias_id, alias_arn
    except Exception as e:
        logger.warning(f"Error preparing agent {agent_display}: {str(e)}")
        raise

def create_supervisor_role(stack_name, maintenance_agent_id, alarm_agent_id, kpi_agent_id, region, account_id):
    """Create a specific role for the supervisor agent with permissions to invoke sub-agents"""
    iam_client = boto3.client('iam')
    
    # Create role name
    supervisor_role_name = f"{stack_name}-supervisor-role"
    
    # Check if role already exists
    role_exists = False
    try:
        iam_client.get_role(RoleName=supervisor_role_name)
        role_exists = True
        logger.info(f"Supervisor role {supervisor_role_name} already exists")
    except iam_client.exceptions.NoSuchEntityException:
        logger.info(f"Supervisor role {supervisor_role_name} does not exist, will create")
    
    # Create trust policy
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock.amazonaws.com"
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": account_id
                    }
                }
            }
        ]
    }
    
    # Create policy for invoking sub-agents - only including sub-agent IDs, not supervisor ID
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": [
                    "lambda:InvokeFunction"
                ],
                "Resource": f"arn:aws:lambda:{region}:{account_id}:function:{stack_name}-*",
                "Effect": "Allow"
            },
            {
                "Sid": "AmazonBedrockAgentsMultiAgentsPoliciesProd",
                "Action": [
                    "bedrock:GetAgentAlias",
                    "bedrock:InvokeAgent"
                ],
                "Effect": "Allow",
                "Resource": [
                    f"arn:aws:bedrock:{region}:{account_id}:agent-alias/{maintenance_agent_id}/*",
                    f"arn:aws:bedrock:{region}:{account_id}:agent-alias/{alarm_agent_id}/*",
                    f"arn:aws:bedrock:{region}:{account_id}:agent-alias/{kpi_agent_id}/*"
                ]
            },
            {
                "Action": [
                    "bedrock:*"
                ],
                "Resource": "*",
                "Effect": "Allow"
            }
        ]
    }
    
    if role_exists:
        # Update existing role
        try:
            # Update trust policy
            iam_client.update_assume_role_policy(
                RoleName=supervisor_role_name,
                PolicyDocument=json.dumps(trust_policy)
            )
            
            # Delete and recreate the policy
            try:
                iam_client.delete_role_policy(
                    RoleName=supervisor_role_name,
                    PolicyName='SupervisorAgentPolicy'
                )
            except Exception as e:
                logger.info(f"No existing policy to delete or error: {str(e)}")
                
            # Attach updated policy
            iam_client.put_role_policy(
                RoleName=supervisor_role_name,
                PolicyName='SupervisorAgentPolicy',
                PolicyDocument=json.dumps(policy)
            )
            
            logger.info(f"Updated supervisor role {supervisor_role_name}")
            
            # Get the role ARN
            response = iam_client.get_role(RoleName=supervisor_role_name)
            supervisor_role_arn = response['Role']['Arn']
            
        except Exception as e:
            logger.warning(f"Error updating supervisor role: {str(e)}")
            raise
    else:
        # Create new role
        try:
            response = iam_client.create_role(
                RoleName=supervisor_role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description=f"Role for {stack_name} supervisor agent to invoke sub-agents"
            )
            supervisor_role_arn = response['Role']['Arn']
            
            # Wait for role to propagate
            time.sleep(10)
            
            # Attach policy to role
            iam_client.put_role_policy(
                RoleName=supervisor_role_name,
                PolicyName='SupervisorAgentPolicy',
                PolicyDocument=json.dumps(policy)
            )
            
            logger.info(f"Created supervisor role {supervisor_role_name}")
            
        except Exception as e:
            logger.warning(f"Error creating supervisor role: {str(e)}")
            raise
    
    return supervisor_role_arn

def associate_agent_collaborator(supervisor_id, sub_agent_alias_arn, name, instruction, supervisor_name=None, relay_history='TO_COLLABORATOR'):
    """Associate a sub-agent with a supervisor agent"""
    try:
        supervisor_display = f"{supervisor_name} (ID: {supervisor_id})" if supervisor_name else supervisor_id
        
        # Make sure supervisor agent is in NOT_PREPARED state (not CREATING)
        wait_for_agent_not_creating(supervisor_id, supervisor_name)
        
        logger.info(f"Associating collaborator {name} with supervisor {supervisor_display} using alias ARN: {sub_agent_alias_arn}")
        logger.info(f"Alias ARN format: {sub_agent_alias_arn}")
        
        # Add retry logic for association
        max_retries = 5
        retry_count = 0
        last_exception = None
        
        while retry_count < max_retries:
            try:
                logger.info(f"Attempting to associate collaborator {name} with supervisor {supervisor_display}, attempt {retry_count + 1}/{max_retries}")
                response = bedrock_agent.associate_agent_collaborator(
                    agentId=supervisor_id,
                    agentVersion='DRAFT',
                    agentDescriptor={"aliasArn": sub_agent_alias_arn},
                    collaboratorName=name,
                    collaborationInstruction=instruction,
                    relayConversationHistory=relay_history
                )
                logger.info(f"Successfully associated collaborator {name} with supervisor {supervisor_display}")
                return True
            except Exception as e:
                last_exception = e
                logger.warning(f"Attempt {retry_count + 1} failed to associate collaborator {name} with supervisor {supervisor_display}: {str(e)}")
                retry_count += 1
                time.sleep(20)  # Longer delay between retries
        
        # If we get here, all retries failed
        raise last_exception
    except Exception as e:
        logger.error(f"Error associating collaborator {name} with supervisor {supervisor_display}: {str(e)}")
        return False

def lambda_handler(event, context):
    """Main handler for CloudFormation custom resource"""
    try:
        # Generate a unique request ID for logging
        request_id = str(uuid.uuid4())
        logger.info(f"Request ID: {request_id} - Starting handler with event: {json.dumps(event)}")
        
        if event['RequestType'] == 'Create' or event['RequestType'] == 'Update':
            resource_suffix = os.environ['RESOURCE_SUFFIX']
            agent_role_arn = os.environ['AGENT_ROLE_ARN']
            maintenance_lambda_arn = os.environ['MAINTENANCE_CHECKER_ARN']
            alarm_lambda_arn = os.environ['ALARM_CHECKER_ARN']
            kpi_lambda_arn = os.environ['KPI_ANALYZER_ARN']
            
            # Extract stack name from resource suffix
            stack_name = resource_suffix.split('-')[0]
            region = os.environ.get('AWS_REGION', 'us-east-1')
            
            # Get account ID using STS instead of relying on environment variables
            try:
                account_id = sts_client.get_caller_identity()['Account']
                logger.info(f"Retrieved account ID: {account_id}")
            except Exception as e:
                logger.error(f"Error getting account ID from STS: {str(e)}")
                # Fallback to extracting from context if STS fails
                account_id = context.invoked_function_arn.split(":")[4]
                logger.info(f"Extracted account ID from context: {account_id}")
            
            logger.info(f"Request ID: {request_id} - Creating maintenance agent")
            # Create maintenance agent
            maintenance_agent_name = f"{resource_suffix}-maintenance"
            maintenance_instruction = """You are responsible for checking network maintenance schedules.
            When asked about a site:
            1. Check if there is any ongoing maintenance using the check_maintenance function
            2. Check if there is upcoming maintenance
            3. Provide details about any scheduled work
            4. Format the information clearly for the supervisor agent"""
            
            maintenance_agent_id, maintenance_agent_arn = create_agent(
                maintenance_agent_name,
                "Network Maintenance Agent",
                maintenance_instruction,
                AGENT_FOUNDATION_MODEL,
                agent_role_arn
            )
            
            logger.info(f"Request ID: {request_id} - Creating alarm agent")
            # Create alarm agent
            alarm_agent_name = f"{resource_suffix}-alarms"
            alarm_instruction = """You are responsible for monitoring network alarms.
            When asked about a site:
            1. Use the check_alarms function to get active alarms
            2. Analyze alarm severity and impact
            3. Determine if immediate action is needed
            4. Report findings clearly to the supervisor agent"""
            
            alarm_agent_id, alarm_agent_arn = create_agent(
                alarm_agent_name,
                "Network Alarm Agent",
                alarm_instruction,
                AGENT_FOUNDATION_MODEL,
                agent_role_arn
            )
            
            logger.info(f"Request ID: {request_id} - Creating KPI agent")
            # Create KPI agent
            kpi_agent_name = f"{resource_suffix}-kpi"
            kpi_instruction = """You are responsible for analyzing network KPIs.
            When asked about a site:
            1. Use the analyze_kpis function to check performance metrics
            2. Identify any anomalies or concerning trends
            3. Analyze the impact of any issues found
            4. Provide clear analysis to the supervisor agent"""
            
            kpi_agent_id, kpi_agent_arn = create_agent(
                kpi_agent_name,
                "Network KPI Agent",
                kpi_instruction,
                AGENT_FOUNDATION_MODEL,
                agent_role_arn
            )
            
            # Create a specific role for the supervisor agent with permissions to invoke sub-agents
            supervisor_role_arn = create_supervisor_role(
                stack_name, 
                maintenance_agent_id, 
                alarm_agent_id, 
                kpi_agent_id,
                region,
                account_id
            )
            
            logger.info(f"Request ID: {request_id} - Creating supervisor agent")
            # Create supervisor agent with the specific supervisor role
            supervisor_agent_name = f"{resource_suffix}-ops-supervisor"
            supervisor_instruction = """You are an intelligent Network Operations Supervisor with access to specialized sub-agents that can help you provide comprehensive network operations support.

AVAILABLE SUB-AGENTS:
- MaintenanceAgent: Specializes in checking maintenance schedules, planned work, and service windows
- AlarmAgent: Monitors and analyzes network alarms, outages, and critical alerts  
- KPIAgent: Analyzes performance metrics, identifies anomalies, and assesses network health

CORE RESPONSIBILITIES:
You intelligently route user queries to the appropriate sub-agents based on the nature of their request. Analyze each user query to determine which sub-agents can provide relevant information, then coordinate their responses to deliver comprehensive answers.

DECISION FRAMEWORK:
- For site status queries: Consider all three agents (maintenance, alarms, KPIs) for complete picture
- For maintenance questions: Primarily use MaintenanceAgent, but consider AlarmAgent if maintenance might affect services
- For performance issues: Use KPIAgent first, then AlarmAgent to correlate with alerts
- For troubleshooting: Start with AlarmAgent, then use KPIAgent for performance correlation
- For complex scenarios: Orchestrate multiple agents and synthesize their findings

INTERACTION PRINCIPLES:
1. Understand the user's intent and information needs
2. Determine which sub-agents have relevant capabilities
3. Invoke appropriate sub-agents in logical sequence
4. Synthesize responses into coherent, actionable insights
5. Provide clear next steps and recommendations
6. Never ask users for information your sub-agents can retrieve

RESPONSE STYLE:
- Lead with key findings and immediate concerns
- Provide context from multiple data sources when relevant
- Highlight correlations between maintenance, alarms, and performance
- Offer specific recommendations based on combined analysis
- Escalate critical issues with clear severity assessment

Remember: You are the orchestrator, not just a router. Use your judgment to determine the best combination of sub-agents for each unique situation."""
            
            supervisor_agent_id, supervisor_agent_arn = create_agent(
                supervisor_agent_name,
                "Network Operations Supervisor Agent",
                supervisor_instruction,
                SUPERVISOR_AGENT_FOUNDATION_MODEL,
                supervisor_role_arn,  # Use the supervisor-specific role
                agent_collaboration='SUPERVISOR'
            )
            
            logger.info(f"Request ID: {request_id} - Creating maintenance action group")
            # Create maintenance action group
            maintenance_functions = [{
                'name': 'check_maintenance',
                'description': 'Check maintenance schedule for a network site',
                'parameters': {
                    'site_id': {
                        'type': 'string',
                        'description': 'The ID of the network site to check (format: site_location_number, e.g., site_dallas_001)'
                    }
                }
            }]
            
            create_action_group(
                maintenance_agent_id,
                'MaintenanceActionGroup',
                'Check maintenance schedules and planned work',
                maintenance_lambda_arn,
                maintenance_functions
            )
            
            logger.info(f"Request ID: {request_id} - Creating alarm action group")
            # Create alarm action group
            alarm_functions = [{
                'name': 'check_alarms',
                'description': 'Check active alarms for a network site',
                'parameters': {
                    'site_id': {
                        'type': 'string',
                        'description': 'The ID of the network site to check (format: site_location_number, e.g., site_dallas_001)'
                    }
                }
            }]
            
            create_action_group(
                alarm_agent_id,
                'AlarmActionGroup',
                'Check and analyze network alarms',
                alarm_lambda_arn,
                alarm_functions
            )
            
            logger.info(f"Request ID: {request_id} - Creating KPI action group")
            # Create KPI action group
            kpi_functions = [{
                'name': 'analyze_kpis',
                'description': 'Analyze KPI metrics for a network site',
                'parameters': {
                    'site_id': {
                        'type': 'string',
                        'description': 'The ID of the network site to analyze (format: site_location_number, e.g., site_dallas_001)'
                    }
                }
            }]
            
            create_action_group(
                kpi_agent_id,
                'KPIActionGroup',
                'Analyze network KPIs and metrics',
                kpi_lambda_arn,
                kpi_functions
            )
            
            logger.info(f"Request ID: {request_id} - Preparing sub-agents and creating aliases")
            # Prepare sub-agents and create aliases
            maintenance_alias_id, maintenance_alias_arn = prepare_agent(maintenance_agent_id, maintenance_agent_name)
            alarm_alias_id, alarm_alias_arn = prepare_agent(alarm_agent_id, alarm_agent_name)
            kpi_alias_id, kpi_alias_arn = prepare_agent(kpi_agent_id, kpi_agent_name)
            
            logger.info(f"Request ID: {request_id} - Associating sub-agents with supervisor")
            # Associate sub-agents with supervisor using the exact approach from bedrock_agent_helper.py
            collaborator_success = False
            
            try:
                success = associate_agent_collaborator(
                    supervisor_id=supervisor_agent_id,
                    sub_agent_alias_arn=maintenance_alias_arn,
                    name='MaintenanceAgent',
                    instruction='Delegate maintenance schedule checks and planned work verification to the Maintenance Agent.',
                    supervisor_name=supervisor_agent_name
                )
                if success:
                    collaborator_success = True
            except Exception as e:
                logger.error(f"Failed to associate MaintenanceAgent: {str(e)}")
            
            try:
                success = associate_agent_collaborator(
                    supervisor_id=supervisor_agent_id,
                    sub_agent_alias_arn=alarm_alias_arn,
                    name='AlarmAgent',
                    instruction='Direct alarm monitoring and analysis tasks to the Alarm Agent.',
                    supervisor_name=supervisor_agent_name
                )
                if success:
                    collaborator_success = True
            except Exception as e:
                logger.error(f"Failed to associate AlarmAgent: {str(e)}")
            
            try:
                success = associate_agent_collaborator(
                    supervisor_id=supervisor_agent_id,
                    sub_agent_alias_arn=kpi_alias_arn,
                    name='KPIAgent',
                    instruction='Assign KPI analysis and performance monitoring tasks to the KPI Agent.',
                    supervisor_name=supervisor_agent_name
                )
                if success:
                    collaborator_success = True
            except Exception as e:
                logger.error(f"Failed to associate KPIAgent: {str(e)}")
            
            # Only prepare supervisor if at least one collaborator was successfully associated
            if collaborator_success:
                logger.info(f"Request ID: {request_id} - Preparing supervisor agent")
                supervisor_alias_id, supervisor_alias_arn = prepare_agent(supervisor_agent_id, supervisor_agent_name)
            else:
                logger.error(f"Request ID: {request_id} - Cannot prepare supervisor agent because no collaborators were successfully associated")
                raise Exception("Failed to associate any collaborators with supervisor agent")
            
            # Return success with agent IDs
            response_data = {
                'SupervisorAgentId': supervisor_agent_id,
                'SupervisorAliasId': supervisor_alias_id,
                'MaintenanceAgentId': maintenance_agent_id,
                'AlarmAgentId': alarm_agent_id,
                'KpiAgentId': kpi_agent_id
            }
            
            # Store agent IDs in the physical resource ID for deletion
            physical_resource_id = json.dumps(response_data)
            logger.info(f"Setting physical resource ID to: {physical_resource_id}")
            
            logger.info(f"Request ID: {request_id} - Successfully created all agents")
            cfnresponse.send(event, context, cfnresponse.SUCCESS, response_data, physical_resource_id)
            
        elif event['RequestType'] == 'Delete':
            try:
                logger.info(f"Request ID: {request_id} - Processing Delete request")
                
                # Get the agent IDs from the PhysicalResourceId or from the event data
                agent_ids = {}
                if 'PhysicalResourceId' in event and event['PhysicalResourceId'] != event['LogicalResourceId']:
                    try:
                        # Try to parse the physical resource ID as JSON
                        agent_ids = json.loads(event['PhysicalResourceId'])
                        logger.info(f"Retrieved agent IDs from PhysicalResourceId: {agent_ids}")
                    except:
                        logger.warning("Could not parse PhysicalResourceId as JSON")
                
                # If we couldn't get agent IDs from PhysicalResourceId, check Data
                if not agent_ids and 'Data' in event:
                    agent_ids = {k: v for k, v in event.get('Data', {}).items() if k.endswith('AgentId')}
                    logger.info(f"Retrieved agent IDs from Data: {agent_ids}")
                
                # If we still don't have agent IDs, check OldResourceProperties
                if not agent_ids and 'OldResourceProperties' in event:
                    try:
                        old_props = event.get('OldResourceProperties', {})
                        if 'ServiceToken' in old_props:
                            # This was our custom resource, try to find agent IDs in ResourceProperties
                            logger.info("Checking for agent IDs in previous invocations")
                    except:
                        logger.warning("Could not retrieve agent IDs from OldResourceProperties")
                
                # If we still don't have agent IDs, nothing to delete
                if not agent_ids:
                    logger.info("No agent IDs found to delete")
                    cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
                    return
                
                # Delete each agent
                for name, agent_id in agent_ids.items():
                    if name.endswith('AgentId'):
                        logger.info(f"Attempting to delete agent {name}: {agent_id}")
                        try:
                            success = delete_agent(agent_id)
                            if success:
                                logger.info(f"Successfully deleted agent {name}: {agent_id}")
                            else:
                                logger.warning(f"Failed to delete agent {name}: {agent_id}")
                        except Exception as e:
                            logger.error(f"Error deleting agent {name}: {agent_id} - {str(e)}")
                
                # Clean up IAM roles created for supervisor agents
                try:
                    stack_name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', '').replace('-bedrock-agents-creator', '')
                    supervisor_role_name = f"{stack_name}-supervisor-agent-role"
                    
                    logger.info(f"Attempting to clean up IAM role: {supervisor_role_name}")
                    
                    # Delete the inline policy first
                    try:
                        iam_client.delete_role_policy(
                            RoleName=supervisor_role_name,
                            PolicyName='SupervisorAgentPolicy'
                        )
                        logger.info(f"Deleted SupervisorAgentPolicy from role {supervisor_role_name}")
                    except Exception as e:
                        logger.info(f"No SupervisorAgentPolicy to delete or error: {str(e)}")
                    
                    # Delete the role
                    try:
                        iam_client.delete_role(RoleName=supervisor_role_name)
                        logger.info(f"Deleted IAM role: {supervisor_role_name}")
                    except Exception as e:
                        logger.info(f"No IAM role to delete or error: {str(e)}")
                        
                except Exception as e:
                    logger.warning(f"Error during IAM cleanup: {str(e)}")
                
                logger.info("Agent deletion process completed")
                cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
            except Exception as e:
                logger.error(f"Error during deletion: {str(e)}")
                # Still return SUCCESS to allow stack deletion to proceed
                cfnresponse.send(event, context, cfnresponse.SUCCESS, {'Error': str(e)})
            
    except Exception as e:
        logger.error(f"Request ID: {request_id} - Error: {str(e)}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {'Error': str(e)})

import datetime
import os

# Get stack name from environment variable or use default
stack_name = os.environ.get('STACK_NAME', 'netops')
region = os.environ.get('AWS_REGION', 'us-east-1')

# Dynamically construct agent name based on stack name and region
# Format must match: f"{stack_name}-ops-supervisor-{resource_suffix}" where resource_suffix is "{stack_name}-{region}"
agent_name = f"{stack_name}-{region}-ops-supervisor"

# Bot configurations
bot_configs = [    
    {
        "bot_name": os.environ.get('BOT_NAME', "Network Operations Assistant"),
        "agent_name": agent_name,
        "start_prompt": "Can you tell me the status of the SITE001?"
    }
]

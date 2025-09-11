#!/bin/sh

# Function to check if running in ECS
is_running_in_ecs() {
  # Try to access the ECS metadata endpoint with a 1 second timeout
  if curl -s --connect-timeout 1 http://169.254.170.2 > /dev/null 2>&1; then
    echo "Running in ECS environment"
    return 0
  else
    echo "Not running in ECS environment"
    return 1
  fi
}

# Function to get initial credentials and set environment variables
setup_initial_credentials() {
  if is_running_in_ecs; then
    echo "Setting up initial ECS credentials..."
    
    # Get credentials from ECS container metadata endpoint
    CREDS=$(curl -s 169.254.170.2$AWS_CONTAINER_CREDENTIALS_RELATIVE_URI)
    
    if [ -z "$CREDS" ] || [ "$CREDS" = "null" ]; then
      echo "Failed to retrieve credentials from ECS metadata endpoint"
      return 1
    fi

    # Extract credentials
    ACCESS_KEY=$(echo $CREDS | jq -r '.AccessKeyId')
    SECRET_KEY=$(echo $CREDS | jq -r '.SecretAccessKey')
    TOKEN=$(echo $CREDS | jq -r '.Token')
    REGION=$(curl -s 169.254.169.254/latest/meta-data/placement/region 2>/dev/null || echo "us-east-1")
    
    # Set as environment variables for immediate use
    export AWS_ACCESS_KEY_ID=$ACCESS_KEY
    export AWS_SECRET_ACCESS_KEY=$SECRET_KEY
    export AWS_SESSION_TOKEN=$TOKEN
    export AWS_REGION=$REGION
    export AWS_DEFAULT_REGION=$REGION
    
    echo "Initial AWS credentials set at $(date)"
    return 0
  else
    echo "Not in ECS environment, skipping credential setup"
    return 0
  fi
}

# Print environment variables for debugging (excluding sensitive data)
echo "Environment variables:"
env | grep -v "AWS_ACCESS_KEY_ID\|AWS_SECRET_ACCESS_KEY\|AWS_SESSION_TOKEN"

# Setup initial credentials
setup_initial_credentials

# Create a wrapper script for Streamlit
cat > /app/streamlit_wrapper.sh << 'EOF'
#!/bin/sh
# Run the Streamlit application
exec streamlit run chat_assistant.py --server.port=8501 --server.address=0.0.0.0 --server.enableWebsocketCompression=false --server.headless=true
EOF

chmod +x /app/streamlit_wrapper.sh

# Run the Streamlit application
echo "Starting Streamlit application..."
echo "The application will use the new credential manager for automatic credential refresh."
exec /app/streamlit_wrapper.sh

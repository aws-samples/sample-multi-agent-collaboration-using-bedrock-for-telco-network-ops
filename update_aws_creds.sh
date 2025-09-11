#!/bin/bash

# Script to automate AWS credential management with isengardcli
# Usage: ./update_aws_creds.sh [role-name]

# Handle virtualenv issue with isengardcli
# Save current VIRTUAL_ENV value
ORIGINAL_VIRTUAL_ENV=$VIRTUAL_ENV

# Temporarily unset VIRTUAL_ENV to avoid the warning
unset VIRTUAL_ENV

# Check if role name is provided as argument
ROLE_NAME=$1

echo "==================================================================="
echo "IMPORTANT: This script will launch an interactive isengardcli shell."
echo "After authentication completes, you MUST type 'exit' to continue."
echo "==================================================================="
echo ""

# Get credentials and save to temporary file
echo "Getting credentials..."
isengardcli creds > temp_creds.txt

# Restore original VIRTUAL_ENV if it was set
if [ ! -z "$ORIGINAL_VIRTUAL_ENV" ]; then
  export VIRTUAL_ENV=$ORIGINAL_VIRTUAL_ENV
  echo "Restored virtual environment: $VIRTUAL_ENV"
fi

# Extract credentials from the output
ACCESS_KEY=$(grep AWS_ACCESS_KEY_ID temp_creds.txt | cut -d '=' -f2)
SECRET_KEY=$(grep AWS_SECRET_ACCESS_KEY temp_creds.txt | cut -d '=' -f2)
SESSION_TOKEN=$(grep AWS_SESSION_TOKEN temp_creds.txt | cut -d '=' -f2)

# Check if credentials were successfully extracted
if [ -z "$ACCESS_KEY" ] || [ -z "$SECRET_KEY" ] || [ -z "$SESSION_TOKEN" ]; then
  echo "ERROR: Failed to extract AWS credentials from isengardcli output."
  echo "Please check if isengardcli creds command worked correctly."
  rm temp_creds.txt
  exit 1
fi

# Update AWS default profile
echo "Updating AWS default profile..."
aws configure set aws_access_key_id "$ACCESS_KEY" --profile default
aws configure set aws_secret_access_key "$SECRET_KEY" --profile default
aws configure set aws_session_token "$SESSION_TOKEN" --profile default

# Clean up
rm temp_creds.txt

echo "AWS default profile updated successfully!"
echo "You can now use AWS CLI commands with your new credentials."

# Note about shell helper function
echo ""
echo "NOTE: For optimal use with virtualenv, consider using the isengardcli shell helper function"
echo "instead of the binary directly. Add the following to your shell profile:"
echo ""
echo "  source \$(isengardcli shell-init)"
echo ""

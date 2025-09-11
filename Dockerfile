FROM --platform=linux/amd64 public.ecr.aws/docker/library/python:3.13-slim

WORKDIR /app

# Install dependencies for entrypoint script
RUN apt-get update && apt-get install -y curl jq && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY streamlit-docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Streamlit config
COPY .streamlit/ ./.streamlit/

# Copy only necessary application files (excluding myenv and .ipynb files)
COPY streamlit-docker/chat_assistant.py .
COPY streamlit-docker/ui_utils.py .
COPY streamlit-docker/config.py .
COPY streamlit-docker/credential_manager.py .
COPY streamlit-docker/src/ ./src/

# Copy the entrypoint script
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# Create necessary directories if they don't exist
RUN mkdir -p /app/src/utils

# Set environment variables
ENV BOT_NAME="Network Operations Assistant"
ENV AWS_REGION="us-east-1"
ENV AWS_DEFAULT_REGION="us-east-1"
ENV STACK_NAME="netops"

# Streamlit specific settings for WebSocket support
ENV STREAMLIT_SERVER_ENABLE_WEBSOCKET_COMPRESSION="false"
ENV STREAMLIT_SERVER_PORT="8501"
ENV STREAMLIT_SERVER_ADDRESS="0.0.0.0"
ENV STREAMLIT_SERVER_HEADLESS="true"

# Expose the port Streamlit runs on
EXPOSE 8501

# Create a non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

# Add a health check endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Use the entrypoint script instead of CMD
ENTRYPOINT ["/app/entrypoint.sh"]

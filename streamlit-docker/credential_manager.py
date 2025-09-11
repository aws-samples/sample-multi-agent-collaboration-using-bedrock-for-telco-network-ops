"""
Enhanced credential management for Streamlit application.
This module provides robust credential refresh and caching mechanisms.
"""
import boto3
import os
import time
import threading
import logging
from botocore.credentials import RefreshableCredentials
from botocore.session import get_session
import requests
from datetime import datetime, timedelta

# Configure detailed logging for credential operations
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('credential_manager')

class ECSCredentialManager:
    """Manages AWS credentials in ECS environment with automatic refresh."""
    
    def __init__(self, refresh_interval=300):  # 5 minutes
        self.refresh_interval = refresh_interval
        self.credentials = None
        self.last_refresh = None
        self.lock = threading.Lock()
        self._refresh_thread = None
        self._stop_refresh = threading.Event()
        self.credential_usage_count = 0
        self.last_access_key_suffix = None
        
        logger.info(f"ECSCredentialManager initialized with refresh_interval={refresh_interval} seconds")
        
    def _get_ecs_credentials(self):
        """Fetch credentials from ECS metadata endpoint."""
        logger.info("Attempting to fetch credentials from ECS metadata endpoint")
        try:
            # Get the credentials URI from environment
            creds_uri = os.environ.get('AWS_CONTAINER_CREDENTIALS_RELATIVE_URI')
            if not creds_uri:
                logger.warning("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI not found in environment")
                return None
                
            logger.info(f"Using credentials URI: {creds_uri}")
            
            # Fetch credentials from ECS metadata endpoint
            # ECS metadata endpoint uses HTTP (not HTTPS) - this is AWS standard
            metadata_url = f"http://169.254.170.2{creds_uri}"
            logger.info(f"Fetching credentials from: {metadata_url}")
            
            response = requests.get(metadata_url, timeout=5)
            response.raise_for_status()
            
            creds_data = response.json()
            logger.info("Successfully retrieved credentials from ECS metadata endpoint")
            
            # Parse expiration time
            expiration = datetime.fromisoformat(creds_data['Expiration'].replace('Z', '+00:00'))
            
            # Log credential details (safely)
            access_key = creds_data['AccessKeyId']
            access_key_suffix = access_key[-4:] if len(access_key) >= 4 else "****"
            logger.info(f"Retrieved credentials - Access Key ending in: ...{access_key_suffix}")
            logger.info(f"Credential expiration: {expiration}")
            
            time_until_expiry = expiration - datetime.now(expiration.tzinfo)
            logger.info(f"Time until credential expiry: {time_until_expiry}")
            
            return {
                'access_key': creds_data['AccessKeyId'],
                'secret_key': creds_data['SecretAccessKey'],
                'token': creds_data['Token'],
                'expiration': expiration
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching ECS credentials: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch ECS credentials: {e}", exc_info=True)
            return None
    
    def _refresh_credentials(self):
        """Refresh credentials from ECS metadata."""
        logger.info("Starting credential refresh process")
        with self.lock:
            new_creds = self._get_ecs_credentials()
            if new_creds:
                # Compare with previous credentials
                old_suffix = self.last_access_key_suffix
                new_suffix = new_creds['access_key'][-4:] if len(new_creds['access_key']) >= 4 else "****"
                
                if old_suffix != new_suffix:
                    logger.info(f"Credentials changed: ...{old_suffix} -> ...{new_suffix}")
                else:
                    logger.info(f"Credentials refreshed (same key): ...{new_suffix}")
                
                self.credentials = new_creds
                self.last_refresh = datetime.now()
                self.last_access_key_suffix = new_suffix
                
                # Update environment variables
                os.environ['AWS_ACCESS_KEY_ID'] = new_creds['access_key']
                os.environ['AWS_SECRET_ACCESS_KEY'] = new_creds['secret_key']
                os.environ['AWS_SESSION_TOKEN'] = new_creds['token']
                
                logger.info(f"Environment variables updated at {self.last_refresh}")
                logger.info(f"Next refresh scheduled in {self.refresh_interval} seconds")
                return True
            else:
                logger.error("Failed to retrieve new credentials during refresh")
                return False
    
    def _background_refresh(self):
        """Background thread to refresh credentials periodically."""
        logger.info("Background credential refresh thread started")
        while not self._stop_refresh.wait(self.refresh_interval):
            try:
                logger.info("Background refresh triggered")
                if self._refresh_credentials():
                    logger.info("Background credential refresh successful")
                else:
                    logger.error("Background credential refresh failed")
            except Exception as e:
                logger.error(f"Background credential refresh failed with exception: {e}", exc_info=True)
        logger.info("Background credential refresh thread stopped")
    
    def start_refresh_thread(self):
        """Start the background credential refresh thread."""
        if self._refresh_thread is None or not self._refresh_thread.is_alive():
            self._stop_refresh.clear()
            self._refresh_thread = threading.Thread(target=self._background_refresh, daemon=True)
            self._refresh_thread.start()
            logger.info(f"Started background credential refresh thread (PID: {self._refresh_thread.ident})")
        else:
            logger.info("Background refresh thread already running")
    
    def stop_refresh_thread(self):
        """Stop the background credential refresh thread."""
        logger.info("Stopping background credential refresh thread")
        self._stop_refresh.set()
        if self._refresh_thread:
            self._refresh_thread.join(timeout=5)
            logger.info("Background credential refresh thread stopped")
    
    def get_fresh_credentials(self):
        """Get fresh credentials, refreshing if necessary."""
        logger.info("get_fresh_credentials() called")
        
        # Check if we need to refresh
        needs_refresh = False
        if self.credentials is None:
            logger.info("No cached credentials available, refresh needed")
            needs_refresh = True
        elif self.last_refresh is None:
            logger.info("No previous refresh timestamp, refresh needed")
            needs_refresh = True
        else:
            time_since_refresh = datetime.now() - self.last_refresh
            if time_since_refresh > timedelta(seconds=self.refresh_interval):
                logger.info(f"Credentials are stale (age: {time_since_refresh}), refresh needed")
                needs_refresh = True
            else:
                logger.info(f"Credentials are fresh (age: {time_since_refresh}), no refresh needed")
        
        if needs_refresh:
            logger.info("Performing credential refresh")
            if not self._refresh_credentials():
                logger.error("Failed to refresh credentials")
                return None
        
        if self.credentials:
            access_key_suffix = self.credentials['access_key'][-4:] if len(self.credentials['access_key']) >= 4 else "****"
            logger.info(f"Returning credentials ending in: ...{access_key_suffix}")
        
        return self.credentials
    
    def create_boto3_session(self):
        """Create a new boto3 session with fresh credentials."""
        logger.info("create_boto3_session() called")
        self.credential_usage_count += 1
        
        creds = self.get_fresh_credentials()
        if not creds:
            logger.error("No valid credentials available for boto3 session creation")
            return None
        
        # Force boto3 to use fresh credentials by clearing any cached sessions
        logger.info("Clearing boto3 default session cache")
        boto3.DEFAULT_SESSION = None
        
        # Create session with explicit credentials
        access_key_suffix = creds['access_key'][-4:] if len(creds['access_key']) >= 4 else "****"
        logger.info(f"Creating boto3 session with credentials ending in: ...{access_key_suffix}")
        logger.info(f"This is credential usage #{self.credential_usage_count}")
        
        session = boto3.Session(
            aws_access_key_id=creds['access_key'],
            aws_secret_access_key=creds['secret_key'],
            aws_session_token=creds['token'],
            region_name=os.environ.get('AWS_REGION', 'us-east-1')
        )
        
        logger.info(f"Successfully created boto3 session for region: {os.environ.get('AWS_REGION', 'us-east-1')}")
        return session

# Global credential manager instance
_credential_manager = None

def get_credential_manager():
    """Get the global credential manager instance."""
    global _credential_manager
    if _credential_manager is None:
        logger.info("Creating global credential manager instance")
        _credential_manager = ECSCredentialManager()
        # Start background refresh if in ECS environment
        if os.environ.get('AWS_CONTAINER_CREDENTIALS_RELATIVE_URI'):
            logger.info("ECS environment detected, starting background credential refresh")
            _credential_manager.start_refresh_thread()
        else:
            logger.info("Not in ECS environment, background refresh not started")
    else:
        logger.info("Using existing global credential manager instance")
    return _credential_manager

def create_fresh_boto3_session():
    """Create a fresh boto3 session with the latest credentials."""
    logger.info("create_fresh_boto3_session() called")
    
    # Check if we're in ECS environment
    if os.environ.get('AWS_CONTAINER_CREDENTIALS_RELATIVE_URI'):
        logger.info("ECS environment detected, using credential manager")
        manager = get_credential_manager()
        session = manager.create_boto3_session()
        if session:
            logger.info("Successfully created fresh boto3 session via credential manager")
        else:
            logger.error("Failed to create boto3 session via credential manager")
        return session
    else:
        # For local development, use default session
        logger.info("Local development environment detected, using default boto3 session")
        boto3.DEFAULT_SESSION = None  # Clear cached session
        session = boto3.Session()
        logger.info("Created default boto3 session for local development")
        return session

def invalidate_boto3_cache():
    """Invalidate boto3 credential cache."""
    logger.info("invalidate_boto3_cache() called")
    
    # Clear the default session
    boto3.DEFAULT_SESSION = None
    logger.info("Cleared boto3 DEFAULT_SESSION")
    
    # Clear botocore credential cache
    try:
        from botocore.credentials import CredentialResolver
        if hasattr(CredentialResolver, '_cache'):
            CredentialResolver._cache.clear()
            logger.info("Cleared botocore CredentialResolver cache")
    except Exception as e:
        logger.debug(f"Could not clear botocore cache: {e}")
    
    logger.info("Boto3 cache invalidation completed")

def log_credential_status():
    """Log current credential status for debugging."""
    logger.info("=== CREDENTIAL STATUS ===")
    
    # Check environment variables
    access_key = os.environ.get('AWS_ACCESS_KEY_ID', 'Not set')
    if access_key != 'Not set' and len(access_key) >= 4:
        access_key = f"...{access_key[-4:]}"
    logger.info(f"Environment AWS_ACCESS_KEY_ID: {access_key}")
    
    session_token = os.environ.get('AWS_SESSION_TOKEN', 'Not set')
    if session_token != 'Not set':
        session_token = f"...{session_token[-8:]}" if len(session_token) >= 8 else "Set"
    logger.info(f"Environment AWS_SESSION_TOKEN: {session_token}")
    
    logger.info(f"Environment AWS_REGION: {os.environ.get('AWS_REGION', 'Not set')}")
    logger.info(f"Environment AWS_CONTAINER_CREDENTIALS_RELATIVE_URI: {os.environ.get('AWS_CONTAINER_CREDENTIALS_RELATIVE_URI', 'Not set')}")
    
    # Check credential manager status
    global _credential_manager
    if _credential_manager:
        logger.info(f"Credential manager usage count: {_credential_manager.credential_usage_count}")
        logger.info(f"Last refresh: {_credential_manager.last_refresh}")
        logger.info(f"Last access key suffix: ...{_credential_manager.last_access_key_suffix}")
    else:
        logger.info("Credential manager not initialized")
    
    logger.info("=== END CREDENTIAL STATUS ===")

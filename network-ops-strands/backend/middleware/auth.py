"""
JWT authentication middleware for FastAPI.

This middleware validates JWT tokens from AWS Cognito and extracts user information.
"""

import os
import json
from typing import Optional, Dict, Any
from functools import wraps

import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


class CognitoJWTValidator:
    """Validates JWT tokens from AWS Cognito."""
    
    def __init__(
        self,
        region: str,
        user_pool_id: str,
        app_client_id: str,
    ):
        """
        Initialize the JWT validator.
        
        Args:
            region: AWS region (e.g., 'us-east-1')
            user_pool_id: Cognito User Pool ID
            app_client_id: Cognito App Client ID
        """
        self.region = region
        self.user_pool_id = user_pool_id
        self.app_client_id = app_client_id
        
        # Construct JWKS URL
        self.jwks_url = (
            f"https://cognito-idp.{region}.amazonaws.com/"
            f"{user_pool_id}/.well-known/jwks.json"
        )
        
        # Initialize JWKS client for fetching public keys
        self.jwks_client = PyJWKClient(self.jwks_url)
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a JWT token and return the decoded claims.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token claims
            
        Raises:
            HTTPException: If token is invalid
        """
        try:
            # Get the signing key from JWKS
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            
            # Decode and validate the token
            decoded_token = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.app_client_id,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": True,
                }
            )
            
            # Verify token_use claim
            token_use = decoded_token.get("token_use")
            if token_use not in ["id", "access"]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token_use claim",
                )
            
            return decoded_token
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )
        except jwt.InvalidAudienceError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token audience",
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token validation failed: {str(e)}",
            )


# Global JWT validator instance
_jwt_validator: Optional[CognitoJWTValidator] = None


def get_jwt_validator() -> CognitoJWTValidator:
    """
    Get or create the JWT validator instance.
    
    Returns:
        CognitoJWTValidator instance
    """
    global _jwt_validator
    
    if _jwt_validator is None:
        # Get configuration from environment
        region = os.getenv("AWS_REGION", "us-east-1")
        user_pool_id = os.getenv("COGNITO_USER_POOL_ID")
        app_client_id = os.getenv("COGNITO_APP_CLIENT_ID")
        
        if not user_pool_id or not app_client_id:
            raise ValueError(
                "COGNITO_USER_POOL_ID and COGNITO_APP_CLIENT_ID "
                "environment variables must be set"
            )
        
        _jwt_validator = CognitoJWTValidator(
            region=region,
            user_pool_id=user_pool_id,
            app_client_id=app_client_id,
        )
    
    return _jwt_validator


# HTTP Bearer security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = None,
) -> Dict[str, Any]:
    """
    Dependency to get the current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Authorization credentials
        
    Returns:
        User information from token claims
        
    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
        )
    
    token = credentials.credentials
    validator = get_jwt_validator()
    claims = validator.validate_token(token)
    
    # Extract user information from claims
    user_info = {
        "user_id": claims.get("sub"),
        "username": claims.get("cognito:username"),
        "email": claims.get("email"),
        "name": claims.get("name"),
        "groups": claims.get("cognito:groups", []),
        "token_use": claims.get("token_use"),
    }
    
    return user_info


def require_auth(func):
    """
    Decorator to require authentication for a route.
    
    Usage:
        @app.get("/protected")
        @require_auth
        async def protected_route(request: Request):
            user = request.state.user
            return {"message": f"Hello {user['username']}"}
    """
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        # Get Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Authorization header",
            )
        
        # Extract token
        token = auth_header.split(" ")[1]
        
        # Validate token and get user
        validator = get_jwt_validator()
        claims = validator.validate_token(token)
        
        # Store user in request state
        request.state.user = {
            "user_id": claims.get("sub"),
            "username": claims.get("cognito:username"),
            "email": claims.get("email"),
            "name": claims.get("name"),
            "groups": claims.get("cognito:groups", []),
        }
        
        # Call the original function
        return await func(request, *args, **kwargs)
    
    return wrapper


def require_group(group_name: str):
    """
    Decorator to require a specific Cognito group membership.
    
    Usage:
        @app.get("/admin")
        @require_group("Admins")
        async def admin_route(request: Request):
            return {"message": "Admin access granted"}
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # First check authentication
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing or invalid Authorization header",
                )
            
            token = auth_header.split(" ")[1]
            validator = get_jwt_validator()
            claims = validator.validate_token(token)
            
            # Check group membership
            groups = claims.get("cognito:groups", [])
            if group_name not in groups:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Required group: {group_name}",
                )
            
            # Store user in request state
            request.state.user = {
                "user_id": claims.get("sub"),
                "username": claims.get("cognito:username"),
                "email": claims.get("email"),
                "name": claims.get("name"),
                "groups": groups,
            }
            
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator

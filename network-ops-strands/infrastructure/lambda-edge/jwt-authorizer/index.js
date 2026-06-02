/**
 * Lambda@Edge JWT Authorizer for CloudFront
 * 
 * This function validates JWT tokens from AWS Cognito at the CloudFront edge.
 * It runs on viewer requests before they reach the origin (backend).
 * 
 * Features:
 * - JWT signature validation using JWKS
 * - Token expiration checking
 * - Audience and issuer validation
 * - User info extraction and forwarding to backend
 * - Public path exemptions (login, signup, etc.)
 */

const jwt = require('jsonwebtoken');
const jwksClient = require('jwks-rsa');

// Configuration from environment variables
const REGION = process.env.CUSTOM_REGION || process.env.AWS_REGION || 'us-east-1';
const USER_POOL_ID = process.env.COGNITO_USER_POOL_ID;
const APP_CLIENT_ID = process.env.COGNITO_APP_CLIENT_ID;

// JWKS client for fetching public keys
const jwksUri = `https://cognito-idp.${REGION}.amazonaws.com/${USER_POOL_ID}/.well-known/jwks.json`;
const client = jwksClient({
  jwksUri,
  cache: true,
  cacheMaxAge: 600000, // 10 minutes
  rateLimit: true,
  jwksRequestsPerMinute: 10,
});

// Public paths that don't require authentication
const PUBLIC_PATHS = [
  '/login',
  '/signup',
  '/verify',
  '/forgot-password',
  '/reset-password',
  '/callback',
  '/logout',
  '/health',
  '/api/config',
  '/favicon.ico',
  '/logo.svg',
  '/assets/',
  '/_next/',
  '/static/',
];

/**
 * Check if path is public (doesn't require authentication)
 */
function isPublicPath(path) {
  return PUBLIC_PATHS.some(publicPath => {
    if (publicPath.endsWith('/')) {
      return path.startsWith(publicPath);
    }
    return path === publicPath;
  });
}

/**
 * Get signing key from JWKS
 */
function getKey(header, callback) {
  client.getSigningKey(header.kid, (err, key) => {
    if (err) {
      callback(err);
      return;
    }
    const signingKey = key.publicKey || key.rsaPublicKey;
    callback(null, signingKey);
  });
}

/**
 * Verify JWT token
 */
async function verifyToken(token) {
  return new Promise((resolve, reject) => {
    jwt.verify(
      token,
      getKey,
      {
        algorithms: ['RS256'],
        audience: APP_CLIENT_ID,
        issuer: `https://cognito-idp.${REGION}.amazonaws.com/${USER_POOL_ID}`,
      },
      (err, decoded) => {
        if (err) {
          reject(err);
        } else {
          resolve(decoded);
        }
      }
    );
  });
}

/**
 * Extract token from Authorization header or cookies
 */
function extractToken(request) {
  // Try Authorization header first
  const authHeader = request.headers.authorization?.[0]?.value;
  if (authHeader && authHeader.startsWith('Bearer ')) {
    return authHeader.substring(7);
  }

  // Try cookies
  const cookieHeader = request.headers.cookie?.[0]?.value;
  if (cookieHeader) {
    const cookies = cookieHeader.split(';').reduce((acc, cookie) => {
      const [key, value] = cookie.trim().split('=');
      acc[key] = value;
      return acc;
    }, {});

    // Check for common token cookie names
    return cookies.idToken || cookies.accessToken || cookies.token;
  }

  return null;
}

/**
 * Create unauthorized response
 */
function createUnauthorizedResponse(message = 'Unauthorized') {
  return {
    status: '401',
    statusDescription: 'Unauthorized',
    headers: {
      'content-type': [{
        key: 'Content-Type',
        value: 'application/json',
      }],
      'cache-control': [{
        key: 'Cache-Control',
        value: 'no-store',
      }],
    },
    body: JSON.stringify({
      error: 'Unauthorized',
      message,
    }),
  };
}

/**
 * Create redirect response to login
 */
function createLoginRedirect(originalUri) {
  return {
    status: '302',
    statusDescription: 'Found',
    headers: {
      location: [{
        key: 'Location',
        value: `/login?redirect=${encodeURIComponent(originalUri)}`,
      }],
      'cache-control': [{
        key: 'Cache-Control',
        value: 'no-store',
      }],
    },
  };
}

/**
 * Main Lambda@Edge handler
 */
exports.handler = async (event) => {
  const request = event.Records[0].cf.request;
  const uri = request.uri;

  console.log('JWT Authorizer - Request URI:', uri);

  // Allow public paths without authentication
  if (isPublicPath(uri)) {
    console.log('Public path, allowing request');
    return request;
  }

  // Extract JWT token
  const token = extractToken(request);
  if (!token) {
    console.log('No token found');
    // For API requests, return 401
    if (uri.startsWith('/api/')) {
      return createUnauthorizedResponse('Missing authentication token');
    }
    // For page requests, redirect to login
    return createLoginRedirect(uri);
  }

  try {
    // Verify token
    const decoded = await verifyToken(token);
    console.log('Token verified for user:', decoded.sub);

    // Add user information to request headers for backend
    request.headers['x-user-id'] = [{
      key: 'X-User-Id',
      value: decoded.sub,
    }];

    request.headers['x-user-email'] = [{
      key: 'X-User-Email',
      value: decoded.email || '',
    }];

    request.headers['x-user-name'] = [{
      key: 'X-User-Name',
      value: decoded.name || '',
    }];

    // Add user groups if present
    if (decoded['cognito:groups']) {
      request.headers['x-user-groups'] = [{
        key: 'X-User-Groups',
        value: decoded['cognito:groups'].join(','),
      }];
    }

    // Add token use type
    request.headers['x-token-use'] = [{
      key: 'X-Token-Use',
      value: decoded.token_use || 'id',
    }];

    console.log('Request authorized, forwarding to origin');
    return request;

  } catch (error) {
    console.error('Token verification failed:', error.message);

    // For API requests, return 401
    if (uri.startsWith('/api/')) {
      return createUnauthorizedResponse(
        error.name === 'TokenExpiredError' 
          ? 'Token has expired' 
          : 'Invalid token'
      );
    }

    // For page requests, redirect to login
    return createLoginRedirect(uri);
  }
};

'use strict';

const https = require('https');
const querystring = require('querystring');

// Configuration - these will be set via environment variables during deployment
let cognitoDomain;
let clientId;
let clientSecret;
let redirectUri;

// Security headers to include in all responses
const SECURITY_HEADERS = {
    'server': [{
        key: 'Server',
        value: 'Enterprise-Network-Operations-Platform'
    }],
    'x-powered-by': [{
        key: 'X-Powered-By',
        value: 'Network-Operations-Dashboard'
    }],
    'x-application-type': [{
        key: 'X-Application-Type',
        value: 'Enterprise-Network-Management'
    }],
    'strict-transport-security': [{
        key: 'Strict-Transport-Security',
        value: 'max-age=31536000; includeSubDomains'
    }],
    'x-frame-options': [{
        key: 'X-Frame-Options',
        value: 'DENY'
    }],
    'x-content-type-options': [{
        key: 'X-Content-Type-Options',
        value: 'nosniff'
    }],
    'referrer-policy': [{
        key: 'Referrer-Policy',
        value: 'strict-origin-when-cross-origin'
    }],
    'x-xss-protection': [{
        key: 'X-XSS-Protection',
        value: '1; mode=block'
    }]
};

// Helper function to add security headers to response
function addSecurityHeaders(headers) {
    const result = { ...headers };
    Object.keys(SECURITY_HEADERS).forEach(key => {
        result[key] = SECURITY_HEADERS[key];
    });
    return result;
}

// Initialize configuration from environment variables or CloudFormation parameters
function initConfig(event) {
    // For local testing, use environment variables
    if (process.env.COGNITO_DOMAIN && process.env.CLIENT_ID && process.env.CLIENT_SECRET && process.env.REDIRECT_URI) {
        cognitoDomain = process.env.COGNITO_DOMAIN;
        clientId = process.env.CLIENT_ID;
        clientSecret = process.env.CLIENT_SECRET;
        redirectUri = process.env.REDIRECT_URI;
        return;
    }
    
    // For Lambda@Edge, these values will be hardcoded during deployment
    cognitoDomain = 'COGNITO_DOMAIN_PLACEHOLDER';
    clientId = 'CLIENT_ID_PLACEHOLDER';
    clientSecret = 'CLIENT_SECRET_PLACEHOLDER';
    redirectUri = 'REDIRECT_URI_PLACEHOLDER';
}

// Helper function to get cookie value
function getCookie(cookies, name) {
    if (!cookies) return null;
    
    console.log('Parsing cookies:', cookies);
    const cookieArray = cookies.split(';');
    for (let i = 0; i < cookieArray.length; i++) {
        const cookiePair = cookieArray[i].trim().split('=');
        if (cookiePair[0] === name) {
            console.log('Found cookie:', name, cookiePair[1]);
            return decodeURIComponent(cookiePair[1]);
        }
    }
    console.log('Cookie not found:', name);
    return null;
}

// Helper function to exchange authorization code for tokens
async function exchangeCodeForTokens(code) {
    console.log('Exchanging code for tokens');
    console.log('Code:', code);
    console.log('Redirect URI:', redirectUri);
    
    return new Promise((resolve, reject) => {
        const authString = Buffer.from(`${clientId}:${clientSecret}`).toString('base64');
        
        const requestBody = querystring.stringify({
            grant_type: 'authorization_code',
            client_id: clientId,
            code: code,
            redirect_uri: redirectUri
        });
        
        console.log('Request body:', requestBody);
        
        const options = {
            hostname: cognitoDomain,
            port: 443,
            path: '/oauth2/token',
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': `Basic ${authString}`,
                'Content-Length': requestBody.length
            }
        };
        
        console.log('Request options:', JSON.stringify(options));
        
        const req = https.request(options, (res) => {
            let data = '';
            
            res.on('data', (chunk) => {
                data += chunk;
            });
            
            res.on('end', () => {
                console.log('Response status:', res.statusCode);
                console.log('Response headers:', JSON.stringify(res.headers));
                console.log('Response data:', data);
                
                if (res.statusCode === 200) {
                    try {
                        const tokens = JSON.parse(data);
                        console.log('Successfully parsed tokens');
                        resolve(tokens);
                    } catch (err) {
                        console.log('Error parsing token response:', err);
                        reject(new Error('Failed to parse token response'));
                    }
                } else {
                    reject(new Error(`Token exchange failed with status ${res.statusCode}: ${data}`));
                }
            });
        });
        
        req.on('error', (err) => {
            console.log('Request error:', err);
            reject(err);
        });
        
        req.write(requestBody);
        req.end();
    });
}

exports.handler = async (event) => {
    console.log('Lambda@Edge function invoked');
    
    // Initialize configuration
    initConfig(event);
    
    try {
        const request = event.Records[0].cf.request;
        const headers = request.headers;
        const uri = request.uri;
        const queryString = request.querystring || '';
        const queryParams = queryString ? querystring.parse(queryString) : {};
        
        console.log('Request URI:', uri);
        console.log('Query string:', queryString);
        
        // Skip authentication for static assets
        if (uri.startsWith('/static/') || 
            uri.startsWith('/_stcore/') || 
            uri.startsWith('/favicon.ico') || 
            uri.includes('.css') ||
            uri.includes('.js') ||
            uri.includes('.woff') ||
            uri.includes('.woff2') ||
            uri.includes('.ttf') ||
            uri.includes('.png') ||
            uri.includes('.jpg') ||
            uri.includes('.jpeg') ||
            uri.includes('.svg') ||
            uri.includes('.ico') ||
            uri.startsWith('/oauth2/static/')) {
            
            console.log('Skipping auth check for static resource:', uri);
            return request;
        }
        
        // Handle the callback from Cognito
        if (uri === '/oauth2/idpresponse' && queryParams.code) {
            console.log('Processing OAuth callback with code');
            
            try {
                // Exchange code for tokens
                const tokens = await exchangeCodeForTokens(queryParams.code);
                console.log('Successfully exchanged code for tokens');
                console.log('ID token length:', tokens.id_token ? tokens.id_token.length : 'N/A');
                console.log('Access token length:', tokens.access_token ? tokens.access_token.length : 'N/A');
                console.log('Refresh token length:', tokens.refresh_token ? tokens.refresh_token.length : 'N/A');
                
                // Redirect to home page with cookies and security headers
                const response = {
                    status: '302',
                    statusDescription: 'Found',
                    headers: addSecurityHeaders({
                        'location': [{
                            key: 'Location',
                            value: '/'
                        }],
                        'set-cookie': [
                            {
                                key: 'Set-Cookie',
                                value: `idToken=${tokens.id_token}; Path=/; Secure; SameSite=None`
                            },
                            {
                                key: 'Set-Cookie',
                                value: `accessToken=${tokens.access_token}; Path=/; Secure; SameSite=None`
                            },
                            {
                                key: 'Set-Cookie',
                                value: `refreshToken=${tokens.refresh_token}; Path=/; Secure; SameSite=None`
                            }
                        ]
                    })
                };
                
                console.log('Returning redirect response with cookies and security headers');
                return response;
            } catch (err) {
                console.log('Error exchanging code for tokens:', err.message);
                
                // For debugging, return the error details with security headers
                return {
                    status: '200',
                    statusDescription: 'OK',
                    headers: addSecurityHeaders({
                        'content-type': [{
                            key: 'Content-Type',
                            value: 'text/html'
                        }]
                    }),
                    body: `
                        <html>
                            <head><title>Authentication Error</title></head>
                            <body>
                                <h1>Authentication Error</h1>
                                <p>Error: ${err.message}</p>
                                <h2>Debug Information:</h2>
                                <pre>
                                    Code: ${queryParams.code}
                                    Redirect URI: ${redirectUri}
                                    Client ID: ${clientId}
                                    Domain: ${cognitoDomain}
                                </pre>
                                <p><a href="/">Return to home page</a></p>
                            </body>
                        </html>
                    `
                };
            }
        }
        
        // Check if user is authenticated via cookies
        const cookies = headers.cookie ? headers.cookie[0].value : '';
        const idToken = getCookie(cookies, 'idToken');
        
        console.log('Checking authentication for path:', uri);
        console.log('Cookies present:', !!cookies);
        console.log('ID token present:', !!idToken);
        
        if (idToken) {
            // User is authenticated, proceed with the request
            console.log('User is authenticated, proceeding with request');
            return request;
        } else {
            // User is not authenticated, redirect to login with security headers
            console.log('User is not authenticated, redirecting to login');
            return {
                status: '302',
                statusDescription: 'Found',
                headers: addSecurityHeaders({
                    'location': [{
                        key: 'Location',
                        value: `https://${cognitoDomain}/login?client_id=${clientId}&response_type=code&redirect_uri=${encodeURIComponent(redirectUri)}&state=login`
                    }]
                })
            };
        }
    } catch (error) {
        console.log('Unexpected error in Lambda function:', error.message);
        console.log(error.stack);
        
        // Return a helpful error page with security headers
        return {
            status: '500',
            statusDescription: 'Internal Server Error',
            headers: addSecurityHeaders({
                'content-type': [{
                    key: 'Content-Type',
                    value: 'text/html'
                }]
            }),
            body: `
                <html>
                    <head><title>Server Error</title></head>
                    <body>
                        <h1>Server Error</h1>
                        <p>An unexpected error occurred: ${error.message}</p>
                        <p><a href="/">Return to home page</a></p>
                    </body>
                </html>
            `
        };
    }
};

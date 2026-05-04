#!/bin/bash
# Build and deploy frontend to S3 + CloudFront

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
FRONTEND_BUCKET=""
CLOUDFRONT_DIST_ID=""
CONFIG_BUCKET=""
REGION="us-east-1"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --bucket|-b)
            FRONTEND_BUCKET="$2"
            shift 2
            ;;
        --distribution|-d)
            CLOUDFRONT_DIST_ID="$2"
            shift 2
            ;;
        --config-bucket|-c)
            CONFIG_BUCKET="$2"
            shift 2
            ;;
        --region|-r)
            REGION="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --bucket, -b         Frontend S3 bucket name (required)"
            echo "  --distribution, -d   CloudFront distribution ID (required)"
            echo "  --config-bucket, -c  Config S3 bucket name (optional)"
            echo "  --region, -r         AWS region [default: us-east-1]"
            echo "  --help, -h           Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Validate required parameters
if [ -z "$FRONTEND_BUCKET" ]; then
    echo -e "${RED}Error: --bucket is required${NC}"
    exit 1
fi

if [ -z "$CLOUDFRONT_DIST_ID" ]; then
    echo -e "${RED}Error: --distribution is required${NC}"
    exit 1
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Frontend Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Bucket:        $FRONTEND_BUCKET"
echo "Distribution:  $CLOUDFRONT_DIST_ID"
[ -n "$CONFIG_BUCKET" ] && echo "Config Bucket: $CONFIG_BUCKET"
echo "Region:        $REGION"
echo ""

# Check if frontend directory exists
if [ ! -d "frontend" ]; then
    echo -e "${RED}Error: frontend directory not found${NC}"
    exit 1
fi

cd frontend

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
if [ ! -d "node_modules" ]; then
    npm install
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Dependencies installed${NC}"
    else
        echo -e "${RED}✗ Dependency installation failed${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Dependencies already installed${NC}"
fi

# Build frontend
echo ""
echo -e "${YELLOW}Building frontend...${NC}"
npm run build

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Frontend built successfully${NC}"
else
    echo -e "${RED}✗ Frontend build failed${NC}"
    exit 1
fi

# Verify build directory
if [ ! -d "dist" ]; then
    echo -e "${RED}Error: Build directory 'dist' not found${NC}"
    exit 1
fi

# Upload to S3
echo ""
echo -e "${YELLOW}Uploading to S3...${NC}"
aws s3 sync dist/ "s3://$FRONTEND_BUCKET/" \
    --region "$REGION" \
    --delete \
    --cache-control "public, max-age=31536000, immutable" \
    --exclude "*.html" \
    --exclude "config.json"

# Upload HTML files with no-cache
aws s3 sync dist/ "s3://$FRONTEND_BUCKET/" \
    --region "$REGION" \
    --exclude "*" \
    --include "*.html" \
    --cache-control "no-cache, no-store, must-revalidate"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Files uploaded to S3${NC}"
else
    echo -e "${RED}✗ S3 upload failed${NC}"
    exit 1
fi

# Upload config if config bucket provided
if [ -n "$CONFIG_BUCKET" ]; then
    echo ""
    echo -e "${YELLOW}Uploading configuration...${NC}"
    
    # Upload branding config
    if [ -f "../config/default-branding.json" ]; then
        aws s3 cp ../config/default-branding.json "s3://$CONFIG_BUCKET/config.json" \
            --region "$REGION" \
            --cache-control "no-cache, no-store, must-revalidate" \
            --content-type "application/json"
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Configuration uploaded${NC}"
        else
            echo -e "${YELLOW}⚠ Configuration upload failed (non-critical)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Branding config not found, skipping${NC}"
    fi
fi

# Invalidate CloudFront cache
echo ""
echo -e "${YELLOW}Invalidating CloudFront cache...${NC}"
INVALIDATION_ID=$(aws cloudfront create-invalidation \
    --distribution-id "$CLOUDFRONT_DIST_ID" \
    --paths "/*" \
    --query "Invalidation.Id" \
    --output text)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ CloudFront invalidation created: $INVALIDATION_ID${NC}"
    echo "  Waiting for invalidation to complete (this may take a few minutes)..."
    
    aws cloudfront wait invalidation-completed \
        --distribution-id "$CLOUDFRONT_DIST_ID" \
        --id "$INVALIDATION_ID"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ CloudFront cache invalidated${NC}"
    else
        echo -e "${YELLOW}⚠ Invalidation in progress (check AWS console for status)${NC}"
    fi
else
    echo -e "${RED}✗ CloudFront invalidation failed${NC}"
    exit 1
fi

cd ..

# Get CloudFront URL
CLOUDFRONT_URL=$(aws cloudfront get-distribution \
    --id "$CLOUDFRONT_DIST_ID" \
    --query "Distribution.DomainName" \
    --output text)

# Print summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Frontend Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Frontend URL:  https://$CLOUDFRONT_URL"
echo "S3 Bucket:     s3://$FRONTEND_BUCKET"
echo "Distribution:  $CLOUDFRONT_DIST_ID"
echo ""
echo "The application is now live and accessible!"

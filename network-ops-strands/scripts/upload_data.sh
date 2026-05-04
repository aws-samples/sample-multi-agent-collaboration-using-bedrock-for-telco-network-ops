#!/bin/bash
# Upload synthetic data to S3 for Network Operations Platform

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
DATA_BUCKET=""
SITES=20
PROFILE="datacenter"
REGION="us-east-1"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --bucket|-b)
            DATA_BUCKET="$2"
            shift 2
            ;;
        --sites|-s)
            SITES="$2"
            shift 2
            ;;
        --profile|-p)
            PROFILE="$2"
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
            echo "  --bucket, -b     S3 bucket name (required)"
            echo "  --sites, -s      Number of sites to generate [default: 20]"
            echo "  --profile, -p    Data profile (datacenter|generic) [default: datacenter]"
            echo "  --region, -r     AWS region [default: us-east-1]"
            echo "  --help, -h       Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Validate required parameters
if [ -z "$DATA_BUCKET" ]; then
    echo -e "${RED}Error: --bucket is required${NC}"
    echo "Use --help for usage information"
    exit 1
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Data Upload to S3${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Bucket:   $DATA_BUCKET"
echo "Sites:    $SITES"
echo "Profile:  $PROFILE"
echo "Region:   $REGION"
echo ""

# Check if bucket exists
echo -e "${YELLOW}Checking S3 bucket...${NC}"
if ! aws s3 ls "s3://$DATA_BUCKET" --region "$REGION" > /dev/null 2>&1; then
    echo -e "${RED}Error: Bucket $DATA_BUCKET does not exist or is not accessible${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Bucket exists and is accessible${NC}"

# Generate synthetic data
echo ""
echo -e "${YELLOW}Generating synthetic data...${NC}"
python3 scripts/generate_data.py \
    --sites "$SITES" \
    --profile "$PROFILE" \
    --output data

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Data generated successfully${NC}"
else
    echo -e "${RED}✗ Data generation failed${NC}"
    exit 1
fi

# Verify data files exist
echo ""
echo -e "${YELLOW}Verifying data files...${NC}"
REQUIRED_FILES=("sites.csv" "maintenance_schedule.csv" "alarms.csv" "kpi_metrics.csv")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "data/$file" ]; then
        echo -e "${RED}Error: Required file data/$file not found${NC}"
        exit 1
    fi
    echo "  ✓ $file"
done

# Upload CSV data to S3
echo ""
echo -e "${YELLOW}Uploading CSV data to S3...${NC}"
aws s3 sync data/ "s3://$DATA_BUCKET/" \
    --region "$REGION" \
    --exclude "*" \
    --include "*.csv" \
    --delete

# Upload topology JSON files
echo -e "${YELLOW}Uploading topology data to S3...${NC}"
for topo_file in data/topology_*.json; do
    if [ -f "$topo_file" ]; then
        aws s3 cp "$topo_file" "s3://$DATA_BUCKET/$(basename $topo_file)" \
            --region "$REGION" \
            --content-type "application/json"
        echo "  ✓ $(basename $topo_file)"
    fi
done

# Upload branding config
if [ -f "config/default-branding.json" ]; then
    echo -e "${YELLOW}Uploading branding config to S3...${NC}"
    aws s3 cp "config/default-branding.json" "s3://$DATA_BUCKET/config.json" \
        --region "$REGION" \
        --content-type "application/json"
    echo "  ✓ config.json"
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Data uploaded successfully${NC}"
else
    echo -e "${RED}✗ Data upload failed${NC}"
    exit 1
fi

# Verify upload
echo ""
echo -e "${YELLOW}Verifying uploaded files...${NC}"
for file in "${REQUIRED_FILES[@]}"; do
    if aws s3 ls "s3://$DATA_BUCKET/$file" --region "$REGION" > /dev/null 2>&1; then
        SIZE=$(aws s3 ls "s3://$DATA_BUCKET/$file" --region "$REGION" | awk '{print $3}')
        echo "  ✓ $file ($SIZE bytes)"
    else
        echo -e "${RED}  ✗ $file not found in S3${NC}"
        exit 1
    fi
done

# Print summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Data Upload Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Bucket:     s3://$DATA_BUCKET"
echo "Files:      ${#REQUIRED_FILES[@]} CSV files"
echo "Sites:      $SITES"
echo "Profile:    $PROFILE"
echo ""
echo "Data is now available for AgentCore agents to access."

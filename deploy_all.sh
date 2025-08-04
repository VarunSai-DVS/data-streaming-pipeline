#!/bin/bash
# Complete deployment script for data streaming pipeline

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Complete Data Streaming Pipeline Deployment${NC}"

# Step 0: Clean destroy first
echo -e "${YELLOW}🧹 Step 0: Cleaning up previous deployment...${NC}"
cdk destroy --all --force --require-approval never

# Step 1: Deploy Infrastructure Stack
echo -e "${YELLOW}📦 Step 1: Deploying Infrastructure Stack...${NC}"
cdk deploy InfrastructureStack --require-approval never

# Step 2: Get the new EC2 IP
echo -e "${YELLOW}📡 Step 2: Getting new EC2 IP...${NC}"
EC2_IP=$(aws cloudformation describe-stacks \
    --stack-name InfrastructureStack \
    --query 'Stacks[0].Outputs[?OutputKey==`EC2PublicIP`].OutputValue' \
    --output text)

echo -e "${GREEN}✅ New EC2 IP: $EC2_IP${NC}"

# Step 3: Update Lambda stack with new IP
echo -e "${YELLOW}🔧 Step 3: Updating Lambda stack with new IP...${NC}"

# Detect OS and use appropriate sed syntax
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}/$EC2_IP/g" stacks/clickstream_lambda_stack.py
else
    # Linux
    sed -i "s/[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}/$EC2_IP/g" stacks/clickstream_lambda_stack.py
fi

# Step 4: Deploy Lambda Stack
echo -e "${YELLOW}⚡ Step 4: Deploying Lambda Stack...${NC}"
cdk deploy ClickstreamLambdaStack --require-approval never

# Step 5: Run post-deployment setup script
echo -e "${YELLOW}🔧 Step 5: Running post-deployment setup script...${NC}"
./scripts/setup_services.sh

# Step 6: Wait for services to be ready
echo -e "${YELLOW}⏳ Step 6: Waiting for services to be ready...${NC}"
sleep 60

echo -e "${GREEN}🎉 Complete deployment finished!${NC}"
echo -e "${GREEN}📊 Check Spark UI at: http://$EC2_IP:8080${NC}"
echo -e "${GREEN}📈 Check Grafana at: http://$EC2_IP:3000${NC}"
echo -e "${GREEN}📊 Check Prometheus at: http://$EC2_IP:9090${NC}"
echo -e "${GREEN}🗄️ Check PostgreSQL data: docker exec kafka psql -h localhost -U streamingadmin -d clickstream_db -c 'SELECT COUNT(*) FROM session_metrics;'${NC}"
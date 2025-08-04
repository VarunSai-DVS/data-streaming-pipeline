#!/bin/bash
# Clean post-deployment setup script for streaming pipeline infrastructure only

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Post-Deployment Infrastructure Setup${NC}"

# Get infrastructure details
EC2_INSTANCE_ID=$(aws cloudformation describe-stacks \
    --stack-name InfrastructureStack \
    --query 'Stacks[0].Outputs[?OutputKey==`EC2InstanceId`].OutputValue' \
    --output text)

PUBLIC_IP=$(aws cloudformation describe-stacks \
    --stack-name InfrastructureStack \
    --query 'Stacks[0].Outputs[?OutputKey==`EC2PublicIP`].OutputValue' \
    --output text)

DB_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name InfrastructureStack \
    --query 'Stacks[0].Outputs[?OutputKey==`DatabaseEndpoint`].OutputValue' \
    --output text)

if [ -z "$EC2_INSTANCE_ID" ] || [ -z "$PUBLIC_IP" ]; then
    echo -e "${RED}❌ Could not get EC2 details${NC}"
    exit 1
fi

echo -e "${GREEN}✅ EC2 Instance ID: $EC2_INSTANCE_ID${NC}"
echo -e "${GREEN}✅ EC2 Public IP: $PUBLIC_IP${NC}"

# Get database password
DB_PASSWORD=$(aws secretsmanager get-secret-value \
    --secret-id streaming-pipeline-db-secret \
    --query SecretString \
    --output text | jq -r '.password')

# Create setup script with infrastructure only
cat > /tmp/setup_services.sh << SCRIPT_END
#!/bin/bash
set -e

echo "Starting infrastructure setup on EC2..."

# Ensure Docker and Docker Compose are installed and running
sudo systemctl start docker
sudo systemctl enable docker

# Create working directory
cd /opt/streaming-pipeline

# Create docker-compose.yml with proper IP substitution
cat > docker-compose.yml << 'COMPOSE_END'
version: '3.8'

services:
  kafka:
    image: confluentinc/cp-kafka:7.6.6
    hostname: kafka
    container_name: kafka
    ports:
      - "9092:9092"
    environment:
      KAFKA_NODE_ID: 1
      CLUSTER_ID: "4L6g3nShT-eMCtK--X86sw"
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT,CONTROLLER:PLAINTEXT
      KAFKA_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://0.0.0.0:9092,CONTROLLER://kafka:29093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://${PUBLIC_IP}:9092
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:29093
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_PROCESS_ROLES: 'broker,controller'
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      KAFKA_HEAP_OPTS: "-Xmx512m -Xms512m"
      KAFKA_LOG_DIRS: '/var/lib/kafka/data'
    volumes:
      - kafka-data:/var/lib/kafka/data

  spark-master:
    image: apache/spark:3.5.0
    hostname: spark-master
    container_name: spark-master
    ports:
      - "8080:8080"
      - "7077:7077"
      - "4040:4040"
    environment:
      SPARK_MODE: master
      SPARK_MASTER_HOST: spark-master
    command: /opt/spark/bin/spark-class org.apache.spark.deploy.master.Master
    volumes:
      - spark-data:/opt/spark/work

  spark-worker:
    image: apache/spark:3.5.0
    hostname: spark-worker
    container_name: spark-worker
    depends_on:
      - spark-master
    environment:
      SPARK_MODE: worker
      SPARK_MASTER: spark://spark-master:7077
      SPARK_WORKER_MEMORY: 512M
      SPARK_WORKER_CORES: 1
    command: /opt/spark/bin/spark-class org.apache.spark.deploy.worker.Worker spark://spark-master:7077
    volumes:
      - spark-data:/opt/spark/work

  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
      - GF_SECURITY_ADMIN_USER=admin
    volumes:
      - grafana-data:/var/lib/grafana

volumes:
  kafka-data:
  spark-data:
  prometheus-data:
  grafana-data:
COMPOSE_END

# Replace placeholders in docker-compose.yml
sed -i "s/\${PUBLIC_IP}/$PUBLIC_IP/g" docker-compose.yml

# Create prometheus.yml
cat > prometheus.yml << 'PROM_END'
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
PROM_END

# Create environment file with proper values
cat > .env << ENV_END
DB_HOST=$DB_ENDPOINT
DB_PASSWORD=$DB_PASSWORD
PUBLIC_IP=$PUBLIC_IP
KAFKA_BOOTSTRAP_SERVERS=$PUBLIC_IP:9092
ENV_END

# Ensure environment variables are properly set
if [ -z "$DB_ENDPOINT" ] || [ -z "$DB_PASSWORD" ]; then
    echo "Getting database credentials..."
    DB_ENDPOINT=$(aws cloudformation describe-stacks --stack-name InfrastructureStack --query 'Stacks[0].Outputs[?OutputKey==`DatabaseEndpoint`].OutputValue' --output text)
    DB_PASSWORD=$(aws secretsmanager get-secret-value --secret-id streaming-pipeline-db-secret --query SecretString --output text | jq -r '.password')
    
    # Update .env file with actual values
    echo "DB_HOST=$DB_ENDPOINT" > .env
    echo "DB_PASSWORD=$DB_PASSWORD" >> .env
    echo "PUBLIC_IP=$PUBLIC_IP" >> .env
    echo "KAFKA_BOOTSTRAP_SERVERS=$PUBLIC_IP:9092" >> .env
fi

# Start services
echo "Starting Docker Compose services..."
docker-compose down || true
docker-compose pull
docker-compose --env-file .env up -d

# Wait for services
echo "Waiting for services to start..."
sleep 30

# Create Kafka topic
echo "Creating Kafka topic..."
docker exec kafka kafka-topics --create \
    --topic clickstream-events \
    --bootstrap-server localhost:9092 \
    --partitions 3 \
    --replication-factor 1 || true

# Verify services
echo "Verifying services..."
docker ps

echo "Infrastructure setup completed!"
SCRIPT_END

# Set variables in the script
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/\$PUBLIC_IP/$PUBLIC_IP/g" /tmp/setup_services.sh
    sed -i '' "s/\$DB_ENDPOINT/$DB_ENDPOINT/g" /tmp/setup_services.sh
    sed -i '' "s/\$DB_PASSWORD/$DB_PASSWORD/g" /tmp/setup_services.sh
else
    # Linux
    sed -i "s/\$PUBLIC_IP/$PUBLIC_IP/g" /tmp/setup_services.sh
    sed -i "s/\$DB_ENDPOINT/$DB_ENDPOINT/g" /tmp/setup_services.sh
    sed -i "s/\$DB_PASSWORD/$DB_PASSWORD/g" /tmp/setup_services.sh
fi

# Upload setup script to S3
TEMP_BUCKET="setup-$(date +%s)"
aws s3 mb s3://$TEMP_BUCKET
aws s3 cp /tmp/setup_services.sh s3://$TEMP_BUCKET/setup_services.sh

# Execute setup script on EC2
echo -e "${YELLOW}📤 Executing infrastructure setup on EC2...${NC}"

COMMAND_ID=$(aws ssm send-command \
    --instance-ids $EC2_INSTANCE_ID \
    --document-name "AWS-RunShellScript" \
    --parameters "{\"commands\":[
        \"aws s3 cp s3://$TEMP_BUCKET/setup_services.sh /tmp/setup_services.sh\",
        \"chmod +x /tmp/setup_services.sh\",
        \"sudo /tmp/setup_services.sh 2>&1 | tee /var/log/setup_services.log\"
    ]}" \
    --query 'Command.CommandId' \
    --output text)

echo -e "${YELLOW}⏳ Waiting for setup to complete (Command ID: $COMMAND_ID)...${NC}"

# Wait for command completion
aws ssm wait command-executed \
    --command-id $COMMAND_ID \
    --instance-id $EC2_INSTANCE_ID || true

# Get command output
STATUS=$(aws ssm get-command-invocation \
    --command-id $COMMAND_ID \
    --instance-id $EC2_INSTANCE_ID \
    --query 'Status' \
    --output text)

if [ "$STATUS" = "Success" ]; then
    echo -e "${GREEN}✅ Infrastructure setup completed successfully!${NC}"
else
    echo -e "${RED}❌ Setup failed with status: $STATUS${NC}"
    echo "Getting error output..."
    aws ssm get-command-invocation \
        --command-id $COMMAND_ID \
        --instance-id $EC2_INSTANCE_ID \
        --query 'StandardErrorContent' \
        --output text
fi

# Cleanup temporary S3 bucket
aws s3 rb s3://$TEMP_BUCKET --force

# Create monitoring script
cat > monitor_services.sh << 'MONITOR_END'
#!/bin/bash
# Monitor streaming pipeline services

EC2_ID=$(aws cloudformation describe-stacks --stack-name InfrastructureStack --query "Stacks[0].Outputs[?OutputKey=='EC2InstanceId'].OutputValue" --output text)

echo "=== Service Status ==="
aws ssm send-command \
    --instance-ids "$EC2_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters '{"commands":["docker ps","echo","docker logs kafka --tail 10","echo","docker logs spark-master --tail 10"]}' \
    --output text
MONITOR_END

chmod +x monitor_services.sh

echo -e "${GREEN}🎉 Infrastructure setup complete!${NC}"
echo -e "${GREEN}📊 Spark UI: http://$PUBLIC_IP:8080${NC}"
echo -e "${GREEN}📈 Grafana: http://$PUBLIC_IP:3000 (admin/admin123)${NC}"
echo -e "${GREEN}📊 Prometheus: http://$PUBLIC_IP:9090${NC}"
echo -e "${GREEN}📡 Kafka: $PUBLIC_IP:9092${NC}"
echo ""
echo -e "${YELLOW}📝 Next steps:${NC}"
echo "1. Lambda is publishing to Kafka every minute"
echo "2. Connect to Spark from Colab: spark://$PUBLIC_IP:7077"
echo "3. Monitor services: ./monitor_services.sh"
echo "4. View logs: aws ssm start-session --target $EC2_INSTANCE_ID"
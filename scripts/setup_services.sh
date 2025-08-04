#!/bin/bash
# Clean infrastructure setup script - Just the services, no Spark job deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Infrastructure Setup${NC}"

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

if [ -z "$EC2_INSTANCE_ID" ] || [ -z "$PUBLIC_IP" ] || [ -z "$DB_ENDPOINT" ]; then
    echo -e "${RED}❌ Could not get required infrastructure details${NC}"
    exit 1
fi

echo -e "${GREEN}✅ EC2 Instance ID: $EC2_INSTANCE_ID${NC}"
echo -e "${GREEN}✅ EC2 Public IP: $PUBLIC_IP${NC}"
echo -e "${GREEN}✅ DB Endpoint: $DB_ENDPOINT${NC}"

# Get database password
DB_PASSWORD=$(aws secretsmanager get-secret-value \
    --secret-id streaming-pipeline-db-secret \
    --query SecretString \
    --output text | jq -r '.password')

if [ -z "$DB_PASSWORD" ]; then
    echo -e "${RED}❌ Could not get database password${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Retrieved database password${NC}"

# Create setup script
cat > /tmp/setup_infrastructure.sh << SCRIPT_END
#!/bin/bash
set -e
set -x  # Enable debugging

echo "Starting infrastructure setup on EC2..."

# Ensure Docker is running
sudo systemctl start docker
sudo systemctl enable docker

# Install docker-compose if not present
if ! command -v docker-compose &> /dev/null; then
    echo "Installing docker-compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    sudo ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose
fi

# Create working directory
mkdir -p /opt/streaming-pipeline
cd /opt/streaming-pipeline

# Create docker-compose.yml
cat > docker-compose.yml << EOF
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
      # Environment variables available for Colab to use
      KAFKA_BOOTSTRAP_SERVERS: ${PUBLIC_IP}:9092
      POSTGRES_HOST: ${DB_ENDPOINT}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
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
      SPARK_WORKER_DIR: /tmp/spark-work
      SPARK_LOCAL_DIRS: /tmp/spark-local
      # Environment variables available for jobs
      KAFKA_BOOTSTRAP_SERVERS: ${PUBLIC_IP}:9092
      POSTGRES_HOST: ${DB_ENDPOINT}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    command: /opt/spark/bin/spark-class org.apache.spark.deploy.worker.Worker spark://spark-master:7077
    volumes:
      - spark-data:/opt/spark/work
      - /tmp:/tmp

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
EOF

# Create prometheus.yml
cat > prometheus.yml << 'PROM_END'
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
PROM_END

# Create connection info file for reference
cat > connection_info.txt << EOF
=== Connection Information ===
Spark Master: spark://${PUBLIC_IP}:7077
Kafka Bootstrap: ${PUBLIC_IP}:9092
PostgreSQL Host: ${DB_ENDPOINT}
PostgreSQL Database: clickstream_db
PostgreSQL User: streamingadmin

=== Web UIs ===
Spark UI: http://${PUBLIC_IP}:8080
Grafana: http://${PUBLIC_IP}:3000 (admin/admin123)
Prometheus: http://${PUBLIC_IP}:9090
EOF

# Start services
echo "Starting Docker Compose services..."
docker-compose down || true
docker-compose pull || { echo "Failed to pull images"; exit 1; }
docker-compose up -d || { echo "Failed to start services"; exit 1; }

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

# Download Spark dependencies for Kafka
echo "Downloading Kafka connector for Spark..."
docker exec spark-master bash -c "cd /opt/spark/jars && wget -q https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.0/spark-sql-kafka-0-10_2.12-3.5.0.jar || true"
docker exec spark-worker bash -c "cd /opt/spark/jars && wget -q https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.0/spark-sql-kafka-0-10_2.12-3.5.0.jar || true"

# Verify services
echo "Verifying services..."
docker ps
RUNNING_CONTAINERS=\$(docker ps -q | wc -l)
if [ "\$RUNNING_CONTAINERS" -lt 4 ]; then
    echo "ERROR: Expected 5 containers, but only \$RUNNING_CONTAINERS running!"
    docker ps -a
    exit 1
fi

echo "Infrastructure setup completed successfully!"
echo ""
cat connection_info.txt
SCRIPT_END

# Upload and execute setup script
TEMP_BUCKET="setup-$(date +%s)"
aws s3 mb s3://$TEMP_BUCKET
aws s3 cp /tmp/setup_infrastructure.sh s3://$TEMP_BUCKET/setup_infrastructure.sh

echo -e "${YELLOW}📤 Executing infrastructure setup on EC2...${NC}"

COMMAND_ID=$(aws ssm send-command \
    --instance-ids $EC2_INSTANCE_ID \
    --document-name "AWS-RunShellScript" \
    --parameters "{\"commands\":[
        \"aws s3 cp s3://$TEMP_BUCKET/setup_infrastructure.sh /tmp/setup_infrastructure.sh\",
        \"chmod +x /tmp/setup_infrastructure.sh\",
        \"sudo /tmp/setup_infrastructure.sh 2>&1 | tee /var/log/setup_infrastructure.log\"
    ]}" \
    --query 'Command.CommandId' \
    --output text)

echo -e "${YELLOW}⏳ Waiting for setup to complete...${NC}"

aws ssm wait command-executed \
    --command-id $COMMAND_ID \
    --instance-id $EC2_INSTANCE_ID || true

STATUS=$(aws ssm get-command-invocation \
    --command-id $COMMAND_ID \
    --instance-id $EC2_INSTANCE_ID \
    --query 'Status' \
    --output text 2>/dev/null || echo "Unknown")

if [ "$STATUS" = "Success" ]; then
    echo -e "${GREEN}✅ Infrastructure setup completed successfully!${NC}"
else
    echo -e "${RED}❌ Setup failed with status: $STATUS${NC}"
    echo "Check logs with: aws ssm start-session --target $EC2_INSTANCE_ID"
    echo "Then run: sudo cat /var/log/setup_infrastructure.log"
fi

# Cleanup
aws s3 rb s3://$TEMP_BUCKET --force

# Create monitoring script
cat > monitor_services.sh << 'MONITOR_END'
#!/bin/bash
EC2_ID=$(aws cloudformation describe-stacks --stack-name InfrastructureStack --query "Stacks[0].Outputs[?OutputKey=='EC2InstanceId'].OutputValue" --output text)

echo "=== Service Status ==="
aws ssm send-command \
    --instance-ids "$EC2_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters '{"commands":["cd /opt/streaming-pipeline && docker ps"]}' \
    --output text
MONITOR_END
chmod +x monitor_services.sh

# Output connection information
echo -e "${GREEN}🎉 Infrastructure Ready!${NC}"
echo ""
echo -e "${YELLOW}=== Connection Information for Google Colab ===${NC}"
echo -e "${GREEN}Spark Master URL:${NC} spark://$PUBLIC_IP:7077"
echo -e "${GREEN}Kafka Bootstrap:${NC} $PUBLIC_IP:9092"
echo -e "${GREEN}PostgreSQL:${NC}"
echo "  Host: $DB_ENDPOINT"
echo "  Database: clickstream_db"
echo "  User: streamingadmin"
echo "  Password: (from AWS Secrets Manager)"
echo ""
echo -e "${YELLOW}=== Web UIs ===${NC}"
echo -e "${GREEN}Spark UI:${NC} http://$PUBLIC_IP:8080"
echo -e "${GREEN}Grafana:${NC} http://$PUBLIC_IP:3000 (admin/admin123)"
echo -e "${GREEN}Prometheus:${NC} http://$PUBLIC_IP:9090"
echo ""
echo -e "${YELLOW}=== Google Colab Connection Example ===${NC}"
echo "spark = SparkSession.builder \\"
echo "    .appName('ClickstreamAnalysis') \\"
echo "    .master('spark://$PUBLIC_IP:7077') \\"
echo "    .config('spark.executor.memory', '512m') \\"
echo "    .getOrCreate()"
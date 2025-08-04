#!/bin/bash
# Fixed deployment script using /tmp for work directory

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 Deploying Spark Streaming Job${NC}"

# Check if spark_streaming_job.py exists
if [ ! -f "spark_streaming_job.py" ]; then
    echo -e "${RED}❌ Error: spark_streaming_job.py not found!${NC}"
    echo "Please save the Spark streaming job artifact as 'spark_streaming_job.py' first."
    exit 1
fi

# Get EC2 instance ID
EC2_ID=$(aws cloudformation describe-stacks \
    --stack-name InfrastructureStack \
    --query "Stacks[0].Outputs[?OutputKey=='EC2InstanceId'].OutputValue" \
    --output text)

if [ -z "$EC2_ID" ]; then
    echo -e "${RED}❌ Could not find EC2 instance. Is infrastructure deployed?${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Found EC2 Instance: $EC2_ID${NC}"

# Get PostgreSQL password from Secrets Manager
echo -e "${YELLOW}🔐 Retrieving database password...${NC}"
DB_PASSWORD=$(aws secretsmanager get-secret-value \
    --secret-id streaming-pipeline-db-secret \
    --query 'SecretString' \
    --output text | jq -r '.password')

if [ -z "$DB_PASSWORD" ]; then
    echo -e "${RED}❌ Could not retrieve database password!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Database password retrieved${NC}"

# Create deployment script
cat > /tmp/deploy_spark_job.sh << 'DEPLOY_SCRIPT'
#!/bin/bash
set -e

echo "📦 Setting up Spark streaming job on EC2..."

cd /opt/streaming-pipeline

# Create spark-jobs directory
mkdir -p spark-jobs

# Download the job from S3
echo "📥 Downloading Spark job from S3..."
aws s3 cp s3://TEMP_BUCKET/spark_streaming_job.py spark-jobs/clickstream_processor.py

# Download correct Spark 3.5.0 Kafka connector JARs
echo "🔍 Downloading Spark 3.5.0 Kafka connector JARs..."
KAFKA_JARS=(
    "spark-sql-kafka-0-10_2.12-3.5.0.jar"
    "spark-token-provider-kafka-0-10_2.12-3.5.0.jar"
)

for jar in "${KAFKA_JARS[@]}"; do
    echo "📥 Downloading $jar..."
    case $jar in
        "spark-sql-kafka-0-10_2.12-3.5.0.jar")
            URL="https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.0/spark-sql-kafka-0-10_2.12-3.5.0.jar"
            ;;
        "spark-token-provider-kafka-0-10_2.12-3.5.0.jar")
            URL="https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.0/spark-token-provider-kafka-0-10_2.12-3.5.0.jar"
            ;;
    esac
    
    # Remove existing file and download fresh
    docker exec spark-master rm -f /opt/spark/jars/$jar
    docker exec spark-worker rm -f /opt/spark/jars/$jar
    
    # Download to both master and worker
    docker exec spark-master wget -q -P /opt/spark/jars/ "$URL"
    docker exec spark-worker wget -q -P /opt/spark/jars/ "$URL"
    
    # Verify download
    if docker exec spark-master test -f /opt/spark/jars/$jar; then
        echo "✅ $jar downloaded successfully"
    else
        echo "❌ Failed to download $jar"
        exit 1
    fi
done

# Download PostgreSQL driver
echo "📥 Downloading PostgreSQL driver..."
docker exec spark-master rm -f /opt/spark/jars/postgresql-42.7.1.jar
docker exec spark-worker rm -f /opt/spark/jars/postgresql-42.7.1.jar
docker exec spark-master wget -q -P /opt/spark/jars/ "https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.1/postgresql-42.7.1.jar"
docker exec spark-worker wget -q -P /opt/spark/jars/ "https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.1/postgresql-42.7.1.jar"

# Create directory in Spark container and copy job
echo "📁 Setting up job in Spark container..."
docker exec spark-master mkdir -p /tmp/spark-jobs  || echo "Using existing directory"
docker cp spark-jobs/clickstream_processor.py spark-master:/tmp/spark-jobs/

# Verify the file was copied
if docker exec spark-master test -f /tmp/spark-jobs/clickstream_processor.py; then
    echo "✅ Job file copied successfully"
else
    echo "❌ Failed to copy job file!"
    exit 1
fi

# Test Python environment with proper PYTHONPATH
echo "🐍 Testing Python environment..."
docker exec -e PYTHONPATH=/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.7-src.zip spark-master python3 -c "
import sys
print('Python version:', sys.version)
try:
    from pyspark.sql import SparkSession
    print('✅ PySpark is available')
except ImportError as e:
    print('❌ PySpark is NOT available:', e)
"

# Kill any existing streaming job
echo "🛑 Stopping any existing job..."
docker exec spark-master pkill -f clickstream_processor || true
sleep 5

# Submit the job with password as environment variable
echo "🚀 Submitting Spark streaming job..."
docker exec -e PYTHONPATH=/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.7-src.zip -e POSTGRES_PASSWORD="$DB_PASSWORD" spark-master \
    /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --driver-memory 512m \
    --executor-memory 512m \
    --conf spark.driver.host=spark-master \
    --conf spark.driver.bindAddress=0.0.0.0 \
    --conf spark.sql.streaming.checkpointLocation=/tmp/checkpoint \
    --conf spark.sql.streaming.forceDeleteTempCheckpointLocation=true \
    --conf spark.worker.workDir=/tmp/spark-work \
    --conf spark.local.dir=/tmp/spark-local \
    --conf spark.executor.extraJavaOptions="-Djava.io.tmpdir=/tmp" \
    --conf spark.driver.extraJavaOptions="-Djava.io.tmpdir=/tmp" \
    --conf spark.jars.ivy=/tmp/.ivy2 \
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
    --conf spark.driver.extraClassPath=/opt/spark/jars/postgresql-42.7.1.jar \
    --conf spark.executor.extraClassPath=/opt/spark/jars/postgresql-42.7.1.jar \
    /tmp/spark-jobs/clickstream_processor.py

echo "✅ Job submitted!"

# Wait and verify
sleep 10

if docker exec spark-master pgrep -f clickstream_processor > /dev/null; then
    echo "✅ Streaming job is running!"
    echo ""
    echo "📊 Looking for application logs..."
    # Better way to find logs
    APP_ID=$(docker exec spark-master ls /tmp/spark-work 2>/dev/null | grep app- | tail -1)
    if [ ! -z "$APP_ID" ]; then
        echo "Found application: $APP_ID"
        docker exec spark-master tail -20 /tmp/spark-work/$APP_ID/*/stderr 2>/dev/null || echo "Logs not ready yet"
    fi
else
    echo "⚠️  Job may not be running. Checking for errors..."
    docker exec spark-master ls -la /tmp/spark-work/ 2>/dev/null || echo "No work directory yet"
fi

echo ""
echo "📝 Commands to monitor the job:"
echo "  Status: docker exec spark-master ps aux | grep clickstream"
echo "  Find logs: docker exec spark-master find /tmp -name stderr -type f"
echo "  Spark UI: Check port 8080"
DEPLOY_SCRIPT

# Replace bucket name in the script
TEMP_BUCKET="spark-job-$(date +%s)"

if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s|TEMP_BUCKET|$TEMP_BUCKET|g" /tmp/deploy_spark_job.sh
else
    sed -i "s|TEMP_BUCKET|$TEMP_BUCKET|g" /tmp/deploy_spark_job.sh
fi

# Upload BOTH files to S3 (fixing the mismatch issue)
echo -e "${YELLOW}📤 Uploading files to S3 bucket: $TEMP_BUCKET${NC}"

aws s3 mb s3://$TEMP_BUCKET
aws s3 cp spark_streaming_job.py s3://$TEMP_BUCKET/spark_streaming_job.py
aws s3 cp /tmp/deploy_spark_job.sh s3://$TEMP_BUCKET/deploy_spark_job.sh

# Verify uploads
echo -e "${YELLOW}🔍 Verifying S3 uploads...${NC}"
aws s3 ls s3://$TEMP_BUCKET/

# Execute deployment on EC2
echo -e "${YELLOW}🔧 Executing deployment on EC2...${NC}"

COMMAND_ID=$(aws ssm send-command \
    --instance-ids "$EC2_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters "{\"commands\":[
        \"echo 'Downloading deployment script from S3...' \",
        \"aws s3 cp s3://$TEMP_BUCKET/deploy_spark_job.sh /tmp/deploy_spark_job.sh\",
        \"chmod +x /tmp/deploy_spark_job.sh\",
        \"echo 'Executing deployment script...' \",
        \"export DB_PASSWORD='$DB_PASSWORD'\",
        \"cd /opt/streaming-pipeline && /tmp/deploy_spark_job.sh 2>&1 | tee /tmp/spark_deploy.log\"
    ]}" \
    --query 'Command.CommandId' \
    --output text)

echo -e "${YELLOW}⏳ Waiting for deployment (Command ID: $COMMAND_ID)...${NC}"

# Wait with timeout and progress
TIMEOUT=60
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
    STATUS=$(aws ssm get-command-invocation \
        --command-id "$COMMAND_ID" \
        --instance-id "$EC2_ID" \
        --query 'Status' \
        --output text 2>/dev/null || echo "Pending")
    
    if [ "$STATUS" = "Success" ]; then
        echo -e "\n${GREEN}✅ Deployment completed successfully!${NC}"
        # Show last part of output
        OUTPUT=$(aws ssm get-command-invocation \
            --command-id "$COMMAND_ID" \
            --instance-id "$EC2_ID" \
            --query 'StandardOutputContent' \
            --output text 2>/dev/null | tail -30)
        echo -e "${GREEN}=== Deployment Output ===${NC}"
        echo "$OUTPUT"
        break
    elif [ "$STATUS" = "Failed" ]; then
        echo -e "\n${RED}❌ Deployment failed!${NC}"
        ERROR=$(aws ssm get-command-invocation \
            --command-id "$COMMAND_ID" \
            --instance-id "$EC2_ID" \
            --query 'StandardErrorContent' \
            --output text 2>/dev/null)
        echo -e "${RED}=== Error Output ===${NC}"
        echo "$ERROR"
        echo -e "${YELLOW}Check deployment log on EC2: /tmp/spark_deploy.log${NC}"
        break
    else
        echo -n "."
        sleep 2
        ELAPSED=$((ELAPSED + 2))
    fi
done

if [ $ELAPSED -ge $TIMEOUT ]; then
    echo -e "\n${YELLOW}⚠️  Deployment timed out. Check status manually.${NC}"
fi

# Cleanup
echo -e "${YELLOW}🧹 Cleaning up S3 bucket...${NC}"
aws s3 rb s3://$TEMP_BUCKET --force

echo ""
echo -e "${GREEN}🎉 Deployment process complete!${NC}"
echo ""
echo -e "${YELLOW}📊 Next steps to verify:${NC}"
echo "1. Check Spark UI: http://<EC2_IP>:8080"
echo "2. Connect to EC2: aws ssm start-session --target $EC2_ID"
echo "3. Check job: docker exec spark-master ps aux | grep clickstream"
echo "4. View logs: docker exec spark-master find /tmp -name stderr -type f -exec tail -f {} +"
echo "5. Check data in PostgreSQL:"
echo "   SELECT COUNT(*) FROM clickstream_events;"
echo "   SELECT * FROM realtime_metrics ORDER BY metric_timestamp DESC LIMIT 5;"

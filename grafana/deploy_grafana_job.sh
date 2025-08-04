#!/bin/bash
# Setup Grafana dashboards and monitoring

set -e

echo "🎨 Setting up Grafana dashboards..."

# Get infrastructure details
EC2_ID=$(aws cloudformation describe-stacks \
    --stack-name InfrastructureStack \
    --query "Stacks[0].Outputs[?OutputKey=='EC2InstanceId'].OutputValue" \
    --output text)

DB_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name InfrastructureStack \
    --query 'Stacks[0].Outputs[?OutputKey==`DatabaseEndpoint`].OutputValue' \
    --output text)

DB_PASSWORD=$(aws secretsmanager get-secret-value \
    --secret-id streaming-pipeline-db-secret \
    --query SecretString \
    --output text | jq -r '.password')

# Create Grafana setup script
cat > /tmp/setup_grafana.sh << GRAFANA_SCRIPT
#!/bin/bash
set -e

cd /opt/streaming-pipeline

# Wait for Grafana to be ready
until curl -s http://localhost:3000/api/health > /dev/null; do
    echo "Waiting for Grafana..."
    sleep 5
done

# Configure PostgreSQL data source
curl -X POST http://admin:admin123@localhost:3000/api/datasources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "PostgreSQL",
    "type": "postgres",
    "url": "${DB_ENDPOINT}:5432",
    "database": "clickstream_db",
    "user": "streamingadmin",
    "secureJsonData": {
      "password": "${DB_PASSWORD}"
    },
    "jsonData": {
      "sslmode": "require",
      "postgresVersion": 1600,
      "timescaledb": false
    }
  }'

# Create Clickstream Dashboard
curl -X POST http://admin:admin123@localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d '{
    "dashboard": {
      "title": "Clickstream Analytics",
      "panels": [
        {
          "datasource": "PostgreSQL",
          "targets": [{
            "rawSql": "SELECT metric_timestamp as time, total_events, unique_users, unique_sessions FROM realtime_metrics WHERE metric_timestamp > NOW() - INTERVAL '"'"'1 hour'"'"' ORDER BY time",
            "format": "time_series"
          }],
          "title": "Real-Time Metrics",
          "type": "graph",
          "gridPos": {"h": 9, "w": 12, "x": 0, "y": 0}
        },
        {
          "datasource": "PostgreSQL",
          "targets": [{
            "rawSql": "SELECT page_url, view_count, unique_visitors FROM page_metrics ORDER BY view_count DESC LIMIT 10",
            "format": "table"
          }],
          "title": "Top Pages",
          "type": "table",
          "gridPos": {"h": 9, "w": 12, "x": 12, "y": 0}
        },
        {
          "datasource": "PostgreSQL",
          "targets": [{
            "rawSql": "SELECT SUM(total_events) FROM realtime_metrics WHERE metric_timestamp > NOW() - INTERVAL '"'"'5 minutes'"'"'",
            "format": "table"
          }],
          "title": "Events (Last 5 min)",
          "type": "stat",
          "gridPos": {"h": 4, "w": 6, "x": 0, "y": 9}
        },
        {
          "datasource": "PostgreSQL",
          "targets": [{
            "rawSql": "SELECT COUNT(DISTINCT user_id) FROM clickstream_events WHERE timestamp > NOW() - INTERVAL '"'"'5 minutes'"'"'",
            "format": "table"
          }],
          "title": "Active Users",
          "type": "stat",
          "gridPos": {"h": 4, "w": 6, "x": 6, "y": 9}
        }
      ],
      "refresh": "5s",
      "schemaVersion": 16,
      "version": 0
    }
  }'

echo "✅ Grafana dashboards configured!"
GRAFANA_SCRIPT

# Execute on EC2
aws ssm send-command \
    --instance-ids "$EC2_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters "{\"commands\":[
        \"chmod +x /tmp/setup_grafana.sh\",
        \"/tmp/setup_grafana.sh\"
    ]}" \
    --output text

echo "✅ Monitoring setup complete!"
echo "📊 Access Grafana at: http://<EC2_IP>:3000 (admin/admin123)"
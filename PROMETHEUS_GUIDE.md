# Prometheus Monitoring Guide

## Current Status: ✅ **FUNCTIONAL**

Prometheus is currently running and operational in your data streaming pipeline.

### **Infrastructure Details**
- **EC2 Instance**: `i-06164aca0d7eeaf01`
- **Public IP**: `3.148.233.121`
- **Prometheus URL**: http://3.148.233.121:9090
- **Status**: Running for 4+ hours
- **Health**: ✅ UP

## How to Access Prometheus

### 1. Web Interface
Open your browser and navigate to: **http://3.148.233.121:9090**

### 2. API Access
You can also access Prometheus via its REST API:
- **Targets**: `http://3.148.233.121:9090/api/v1/targets`
- **Metrics**: `http://3.148.233.121:9090/api/v1/label/__name__/values`

## Current Configuration

### Prometheus Configuration
The current `prometheus.yml` configuration is minimal and only scrapes itself:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
```

### Available Metrics
Prometheus is currently collecting its own internal metrics, including:
- **Go Runtime Metrics**: `go_gc_*`, `go_memstats_*`
- **Process Metrics**: `process_*`
- **Prometheus Internal Metrics**: `prometheus_*`

## How to Use Prometheus

### 1. **Basic Querying**
In the Prometheus web interface, you can query metrics using PromQL:

**Example Queries:**
```promql
# Memory usage
process_resident_memory_bytes

# CPU usage
rate(process_cpu_seconds_total[5m])

# Prometheus uptime
prometheus_build_info

# Number of scrapes
prometheus_target_scrape_pool_targets
```

### 2. **Adding Custom Metrics**
To collect metrics from your applications, you need to:

#### A. **Add Exporters** (Recommended)
Install and configure exporters for your services:

**For Kafka:**
```yaml
# Add to prometheus.yml
- job_name: 'kafka'
  static_configs:
    - targets: ['kafka:9308']  # Kafka JMX Exporter
```

**For PostgreSQL:**
```yaml
# Add to prometheus.yml
- job_name: 'postgresql'
  static_configs:
    - targets: ['postgresql:9187']  # PostgreSQL Exporter
```

#### B. **Instrument Your Applications**
Add Prometheus client libraries to your applications:

**Python Example:**
```python
from prometheus_client import Counter, Histogram, start_http_server

# Define metrics
events_processed = Counter('events_processed_total', 'Total events processed')
processing_time = Histogram('event_processing_seconds', 'Time spent processing events')

# Start metrics server
start_http_server(8000)

# Use in your code
@processing_time.time()
def process_event(event):
    # Process event
    events_processed.inc()
```

### 3. **Integration with Grafana**
Prometheus is already integrated with Grafana:
- **Grafana URL**: http://3.148.233.121:3000
- **Credentials**: admin/admin123
- **Prometheus Data Source**: Already configured

## Advanced Usage

### 1. **Custom Metrics for Your Pipeline**
To monitor your data streaming pipeline, consider adding these metrics:

```python
# In your Lambda function or Spark job
from prometheus_client import Counter, Gauge, Histogram

# Kafka metrics
messages_produced = Counter('kafka_messages_produced_total', 'Total messages produced')
messages_consumed = Counter('kafka_messages_consumed_total', 'Total messages consumed')

# Processing metrics
processing_duration = Histogram('event_processing_duration_seconds', 'Event processing time')
active_sessions = Gauge('active_sessions', 'Number of active user sessions')

# Database metrics
db_connections = Gauge('database_connections', 'Active database connections')
query_duration = Histogram('database_query_duration_seconds', 'Database query time')
```

### 2. **Alerting Rules**
Create alerting rules in Prometheus:

```yaml
# prometheus.yml
rule_files:
  - "alerts.yml"

# alerts.yml
groups:
  - name: streaming_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(events_processing_errors_total[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High error rate in event processing"
```

### 3. **Service Discovery**
For dynamic environments, use service discovery:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
```

## Monitoring Your Current Pipeline

### 1. **Lambda Function Metrics**
Monitor your clickstream generator Lambda:

```bash
# Check Lambda metrics via CloudWatch
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=ClickstreamLambdaStack-ClickstreamLambda21AB321F-mrzd3dySqG7A \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum
```

### 2. **Kafka Metrics**
Monitor Kafka performance:

```bash
# Check Kafka consumer lag
docker exec kafka kafka-consumer-groups --bootstrap-server localhost:9092 --describe --group your-consumer-group
```

### 3. **Database Metrics**
Monitor PostgreSQL performance:

```sql
-- Check active connections
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- Check query performance
SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;
```

## Troubleshooting

### 1. **Check Prometheus Status**
```bash
# Check if Prometheus is running
aws ssm send-command \
  --instance-ids i-06164aca0d7eeaf01 \
  --document-name "AWS-RunShellScript" \
  --parameters '{"commands":["cd /opt/streaming-pipeline && docker ps | grep prometheus"]}'
```

### 2. **Check Prometheus Logs**
```bash
# View Prometheus logs
aws ssm send-command \
  --instance-ids i-06164aca0d7eeaf01 \
  --document-name "AWS-RunShellScript" \
  --parameters '{"commands":["cd /opt/streaming-pipeline && docker logs prometheus"]}'
```

### 3. **Restart Prometheus**
```bash
# Restart Prometheus container
aws ssm send-command \
  --instance-ids i-06164aca0d7eeaf01 \
  --document-name "AWS-RunShellScript" \
  --parameters '{"commands":["cd /opt/streaming-pipeline && docker restart prometheus"]}'
```

## Next Steps

### 1. **Add Application Metrics**
- Instrument your Lambda function with Prometheus metrics
- Add Kafka JMX exporter for detailed Kafka metrics
- Add PostgreSQL exporter for database metrics

### 2. **Create Dashboards**
- Build Grafana dashboards for your pipeline metrics
- Set up alerts for critical thresholds
- Monitor end-to-end data flow

### 3. **Scale Monitoring**
- Add more exporters as you add services
- Implement service discovery for dynamic environments
- Set up alerting and notification systems

## Quick Commands

```bash
# Check Prometheus status
curl -s http://3.148.233.121:9090/api/v1/targets

# Get available metrics
curl -s "http://3.148.233.121:9090/api/v1/label/__name__/values" | jq '.data[]'

# Query a specific metric
curl -s "http://3.148.233.121:9090/api/v1/query?query=process_resident_memory_bytes"

# Check Prometheus health
curl -s http://3.148.233.121:9090/-/healthy
```

## Summary

✅ **Prometheus is functional and ready to use**
- Web UI accessible at http://3.148.233.121:9090
- Currently collecting self-monitoring metrics
- Integrated with Grafana for visualization
- Ready for custom metrics and alerting

The monitoring infrastructure is in place and operational. You can start using it immediately for basic monitoring and expand it as your pipeline grows. 
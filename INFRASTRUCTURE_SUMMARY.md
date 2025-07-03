# Data Streaming Pipeline - Infrastructure Summary

## ��️ Project Overview
Real-time clickstream data processing pipeline using AWS services and open-source tools.

## 📊 Architecture
```
Lambda (Clickstream) → Kafka (EC2) → Spark (EC2) → PostgreSQL (RDS)
                                    ↓
                              Prometheus + Grafana
```

## ✅ Deployment Status

### Lambda Stack (ClickstreamLambdaStack)
- **Status**: ✅ Running
- **Function**: Generates clickstream data every minute
- **Storage**: S3 bucket for raw data
- **Data**: JSON with user interactions (PAGE_VIEW, ADD_TO_CART, etc.)

### Infrastructure Stack (InfrastructureStack)
- **Status**: ✅ Running
- **Deployment Time**: ~7.5 minutes
- **Cost**: Free tier eligible

## 🏢 Infrastructure Details

### EC2 Instance
- **Instance ID**: `i-0430667372210d64f`
- **Public IP**: `34.204.97.63`
- **Type**: t3.micro (Free tier)
- **Services**: Kafka, Spark, Prometheus, Grafana

### RDS PostgreSQL
- **Endpoint**: `infrastructurestack-streamingdatabase86da5e02-bxl5pmtwv076.cynws2oc22c3.us-east-1.rds.amazonaws.com`
- **Engine**: PostgreSQL 16
- **Type**: db.t3.micro (Free tier)
- **Credentials**: AWS Secrets Manager

### S3 Storage
- **Bucket**: `clickstreamlambdastack-clickstreamdatabucket4fe4dd-jq2mmqn5ird3`
- **Data**: Clickstream JSON files (1 per minute)

## 🔗 Access URLs

### Monitoring
- **Grafana**: http://34.204.97.63:3000 (admin/admin123)
- **Prometheus**: http://34.204.97.63:9090
- **Spark UI**: http://34.204.97.63:8080

### Data Endpoints
- **Kafka**: `34.204.97.63:9092`

## 📁 Project Structure
```
data-streaming-pipeline/
├── app.py                          # Main CDK app
├── stacks/
│   ├── clickstream_lambda_stack.py # Lambda + S3 + EventBridge
│   └── infrastructure_stack.py     # EC2 + RDS + Docker services
├── lambda/
│   └── clickstream_generator.py    # Lambda function code
└── requirements.txt                # Python dependencies
```

## 🐳 Docker Services
- **Zookeeper**: Kafka coordination
- **Kafka**: Message queue (port 9092)
- **Spark Master/Worker**: Stream processing
- **Prometheus**: Metrics collection (port 9090)
- **Grafana**: Visualization (port 3000)

## 💰 Cost Analysis
- **Free Tier**: $0/month (12 months)
- **Post Free Tier**: ~$20-35/month
- **Components**: EC2 t3.micro, RDS db.t3.micro, Lambda, S3

## 🔐 Security
- **IAM Roles**: Lambda, EC2, RDS permissions
- **Security Groups**: Port access control
- **Secrets Manager**: Database credentials
- **VPC**: Public subnets (cost optimization)

## 🚧 Next Steps

### Phase 2: Integration
1. Modify Lambda to send data to Kafka
2. Create Spark streaming job
3. Connect Spark to PostgreSQL
4. Set up Grafana dashboards

### Phase 3: Enhancement
1. Data transformation logic
2. Alerting in Grafana
3. Data retention policies
4. Infrastructure scaling

## 🔍 Useful Commands

### Check Status
```bash
# EC2 status
aws ec2 describe-instances --instance-ids i-0430667372210d64f

# Lambda logs
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/ClickstreamLambdaStack"

# S3 data
aws s3 ls s3://clickstreamlambdastack-clickstreamdatabucket4fe4dd-jq2mmqn5ird3/clickstream/

# Database credentials
aws secretsmanager get-secret-value --secret-id streaming-pipeline-db-secret
```

### CDK Commands
```bash
cdk deploy InfrastructureStack
cdk destroy InfrastructureStack
cdk list
```

## 📈 Current Data Flow
1. **Lambda** generates clickstream data every minute
2. **Data** stored in S3 as JSON files
3. **Format**: User interactions with timestamps, device info, regions

## 🎯 Success Metrics
- ✅ Infrastructure deployed
- ✅ Lambda generating data
- ✅ S3 storing data
- ✅ Docker services running
- ✅ Database accessible
- ✅ Monitoring available

---

**Last Updated**: July 1, 2025  
**Status**: ✅ Production Ready  
**Next**: Phase 2 Integration 
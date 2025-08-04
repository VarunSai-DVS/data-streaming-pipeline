# Clickstream Data Streaming Pipeline 🚀

A fully open-source real-time data streaming platform built on AWS infrastructure using Kafka, Apache Spark, PostgreSQL, Prometheus, and Grafana. This project simulates clickstream data and processes it through a scalable, fault-tolerant pipeline for storage, analysis, and visualization.

## 🌐 Project Overview

This project demonstrates how to build a real-time clickstream data pipeline using open-source tools on AWS EC2 infrastructure with local Spark processing. Key objectives:

- Ingest clickstream data using AWS Lambda
- Process data in real-time using Apache Spark (EC2 Local Cluster)
- Store processed data in PostgreSQL with proper schema management
- Monitor system performance using Prometheus and Grafana
- Use AWS CDK (Python) for infrastructure as code

---

## 🏗️ Architecture

```
Clickstream Generator (AWS Lambda)
       ↓
   Kafka (EC2)
       ↓
Spark Processor (EC2 Local Cluster)
       ↓
PostgreSQL (Processed Data)
       ↓
 Monitoring
  (Prometheus + Grafana)
```

---

## 📦 Tech Stack

| Component      | Tech                      |
|----------------|---------------------------|
| Clickstream Sim| AWS Lambda (Python)       |
| Message Queue  | Apache Kafka (on EC2)     |
| Processing     | Apache Spark (EC2 Local)  |
| Storage        | AWS RDS (PostgreSQL)      |
| Monitoring     | Prometheus, Grafana       |
| IaC            | AWS CDK (Python)          |

---

## 🧹 Features

- ⚡ Real-time data ingestion with Kafka
- 🔥 Stream processing using Spark (EC2 Local Cluster)
- 📂 PostgreSQL storage with proper schema management
- 📈 Live system metrics using Prometheus and Grafana
- 🛠️ Reproducible infra setup using AWS CDK
- 🐳 Docker-based Spark cluster deployment
- 📊 Comprehensive analytics dashboards
- 🔄 Automated data pipeline with error handling

---

## 🚀 Deployment Guide

### Prerequisites
- AWS CLI configured
- Python 3.9+ and pip
- AWS CDK installed (`npm install -g aws-cdk`)

### Initial Setup
1. **Create virtual environment:**
   ```bash
   conda create -n streaming-pipeline python=3.9
   conda activate streaming-pipeline
   pip install -r requirements.txt
   ```

2. **Create Lambda Layer (REQUIRED):**
   ```bash
   # Create the kafka-python layer for Lambda
   mkdir python
   cd python
   pip install kafka-python==2.0.2 -t .
   cd ..
   zip -r lambda-layer.zip python/
   rm -rf python/
   ```

3. **Bootstrap CDK (first time only):**
   ```bash
   cdk bootstrap
   ```

### Deployment Process

1. **Deploy Infrastructure:**
   ```bash
   ./deploy_all.sh
   ```
   
   This script:
   - Deploys InfrastructureStack (EC2, RDS, Security Groups)
   - Updates Lambda stack with correct EC2 IP
   - Deploys ClickstreamLambdaStack
   - Runs post-deployment service setup

2. **Set Up Database Schema:**
   ```bash
   # Create database tables with proper schema
   # Run the SQL commands in database_schema.sql via DBeaver or psql
   ```

3. **Deploy Spark Job:**
   ```bash
   ./spark-job/deploy_streaming_job.sh
   ```

4. **Set Up Monitoring:**
   ```bash
   # Manual import (recommended)
   # Access Grafana: http://<EC2_IP>:3000 (admin/admin123)
   # Import grafana/grafana_job.json for comprehensive dashboards
   
   # Or automated setup
   ./grafana/deploy_grafana_job.sh
   ```

### Verification Steps

1. **Check Lambda → Kafka Connection:**
   ```bash
   # Check Lambda logs
   aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/ClickstreamLambdaStack"
   
   # Verify messages in Kafka
   aws ssm send-command --instance-ids <EC2_INSTANCE_ID> --document-name "AWS-RunShellScript" --parameters '{"commands":["docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic clickstream-events --from-beginning --max-messages 5"]}'
   ```

2. **Check Spark Job Status:**
   ```bash
   # Check deployment logs
   sudo cat /tmp/spark_deploy.log
   
   # Check if job is running
   docker exec spark-master ps aux | grep python
   
   # Access Spark UI
   # http://<EC2_PUBLIC_IP>:8080
   ```

3. **Verify Data Pipeline:**
   ```bash
   # Check if data is flowing to PostgreSQL
   # Connect to database and verify tables have data
   ```

4. **Access Monitoring Dashboards:**
   - Grafana: `http://<EC2_PUBLIC_IP>:3000` (admin/admin123)
   - Prometheus: `http://<EC2_PUBLIC_IP>:9090`
   - Spark UI: `http://<EC2_PUBLIC_IP>:8080`

### Database Schema Management

The project uses a **separated database schema approach**:

1. **Manual Table Creation:**
   ```sql
   -- Run database_schema.sql in DBeaver or psql
   -- Creates all necessary tables with proper schema
   ```

2. **Spark Job Verification:**
   - Spark job only verifies tables exist
   - No table creation in Spark job
   - Clean separation of concerns

### Monitoring Setup

**Comprehensive Dashboards Available:**

1. **Clickstream Analytics Dashboard:**
   - Real-time event stream visualization
   - Active users and conversion rates
   - Top pages with bounce rates
   - Device distribution analysis
   - User activity heatmaps

2. **User Behavior Analytics Dashboard:**
   - User engagement funnels
   - Top users by activity
   - User retention cohorts

3. **System Monitoring Dashboard:**
   - Pipeline status monitoring
   - Database health checks
   - Recent events tracking

### Known Issues & Fixes

1. **Schema Mismatch Issue:**
   - Problem: Spark job expecting different field names than Kafka messages
   - Fix: Updated Spark job schema to match Kafka message format
   - Status: ✅ **RESOLVED**

2. **Database Table Creation:**
   - Problem: Spark job creating tables with "dummy" columns
   - Fix: Separated database schema management
   - Status: ✅ **RESOLVED**

3. **Spark Job Timeout:**
   - Problem: Spark job timing out due to database connection issues
   - Fix: Added proper error handling and connection testing
   - Status: ✅ **RESOLVED**

4. **Data Pipeline Performance:**
   - Problem: Slow processing causing batch delays
   - Fix: Optimized processing intervals and error handling
   - Status: ✅ **RESOLVED**

### Cleanup
```bash
cdk destroy --all
```

---

## 🚧 Project Milestones

- [x] Architecture finalized
- [x] CDK project setup
- [x] Kafka EC2 instance
- [x] Spark EC2 instance
- [x] Lambda clickstream simulator
- [x] PostgreSQL schema + RDS
- [x] Prometheus + Grafana monitoring
- [x] Lambda → Kafka integration
- [x] Spark → PostgreSQL integration
- [x] Database schema management
- [x] Comprehensive monitoring dashboards
- [x] Real-time data processing pipeline
- [x] Error handling and debugging
- [x] Infrastructure cleanup and optimization
- [x] **FINAL INTEGRATION + DEMO** ✅

---

## 📁 Folder Structure

```
data-streaming-pipeline/
│
├── stacks/               # AWS CDK stacks
│   ├── infrastructure_stack.py
│   └── clickstream_lambda_stack.py
├── lambda/               # Clickstream simulation code
│   └── clickstream_generator.py
├── spark-job/            # Spark processing reference
│   └── clickstream_processor.py
├── spark-job/            # Spark processing code
│   ├── spark_streaming_job.py
│   └── deploy_streaming_job.sh
├── grafana/              # Monitoring dashboards
│   ├── grafana_job.json
│   └── deploy_grafana_job.sh
├── scripts/              # Deployment and setup scripts
│   ├── setup_services.sh
│   ├── deploy_all.sh
│   └── monitor_services.sh
├── database_schema.sql   # Database schema definition
├── lambda-layer.zip      # Kafka client libraries
├── requirements.txt      # Python dependencies
├── cdk.json             # CDK configuration
├── app.py               # CDK app entry point
├── DEBUGGING_GUIDE.md   # Debugging history and solutions
├── README.md
└── .gitignore
```

---

## 🧪 Demo Use Case

Simulate clickstream data from e-commerce website users and process this data to:
- Track user behavior patterns (page views, add to cart, purchases)
- Analyze session data and conversion funnels
- Monitor real-time user engagement metrics
- Generate insights for business intelligence

---

## 🔄 Recent Updates (August 2025)

### **✅ Working Data Pipeline**
- **Status**: Fully operational real-time data processing
- **Flow**: Lambda → Kafka → Spark → PostgreSQL
- **Performance**: Processing batches with 1+ records every 10-30 seconds
- **Monitoring**: Comprehensive Grafana dashboards

### **✅ Database Schema Management**
- **Problem**: Spark job creating tables with "dummy" columns
- **Solution**: Separated database schema management
- **Implementation**: 
  - Manual table creation via `database_schema.sql`
  - Spark job only verifies tables exist
  - Clean separation of concerns

### **✅ Schema Mismatch Resolution**
- **Problem**: Spark job expecting different field names than Kafka messages
- **Solution**: Updated Spark job schema to match Kafka message format
- **Changes**:
  - `userId` instead of `user_id`
  - `eventType` instead of `event_type`
  - `page` instead of `page_url`
  - Added `device` and `region` fields

### **✅ Comprehensive Monitoring**
- **Grafana Dashboards**: Professional-grade analytics dashboards
- **Real-time Metrics**: Live data visualization
- **User Behavior Analytics**: Conversion funnels and retention analysis
- **System Monitoring**: Pipeline health and performance tracking

### **✅ Error Handling & Debugging**
- **Spark Job Logs**: Comprehensive logging and error handling
- **Database Connection**: Proper connection testing and verification
- **Performance Optimization**: Optimized processing intervals
- **Debugging Guide**: Complete troubleshooting documentation

### **Current Architecture**
```
Lambda → Kafka → Spark (EC2 Local) → PostgreSQL → Grafana Dashboards
```

### **Key Achievements**
- ✅ **Real-time Processing**: Data flowing from Lambda to PostgreSQL
- ✅ **Schema Management**: Proper database schema with separated concerns
- ✅ **Comprehensive Monitoring**: Professional dashboards with analytics
- ✅ **Error Handling**: Robust error handling and debugging
- ✅ **Performance**: Optimized processing with proper timeouts
- ✅ **Documentation**: Complete debugging guide and setup instructions

---

## 🧑‍💻 Authors

**Sai Kiran Anumalla**       
**Varun Sai Danduri**       
MSCS @ Northeastern University        
GitHub: [@saikirananumalla](https://github.com/saikirananumalla)       
[@VarunSai-DVS](https://github.com/VarunSai-DVS)

---

## 📜 License

MIT License – see `LICENSE` file for details.

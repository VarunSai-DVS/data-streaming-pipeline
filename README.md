# Clickstream Data Streaming Pipeline 🚀

A fully open-source real-time data streaming platform built on AWS infrastructure using Kafka, Apache Spark, PostgreSQL, Prometheus, and Grafana. This project simulates clickstream data and processes it through a scalable, fault-tolerant pipeline for storage, analysis, and visualization.

## 🌐 Project Overview

This project demonstrates how to build a real-time clickstream data pipeline using open-source tools on AWS EC2 infrastructure with Google Colab for remote Spark processing. Key objectives:

- Ingest clickstream data using Kafka
- Process data in near real-time using Apache Spark (Google Colab)
- Store processed data in PostgreSQL
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
- 📂 PostgreSQL storage for processed data
- 📈 Live system metrics using Prometheus and Grafana
- 🛠️ Reproducible infra setup using AWS CDK
- 🐳 Docker-based Spark cluster deployment

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

2. **Verify Services:**
   ```bash
   # Check if Docker services are running
   ./monitor_services.sh
   
   # Or connect to EC2 and check manually
   aws ssm start-session --target <EC2_INSTANCE_ID>
   docker ps
   ```

### Verification Steps

1. **Check Lambda → Kafka Connection:**
   ```bash
   # Check Lambda logs
   aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/ClickstreamLambdaStack"
   
   # Verify messages in Kafka
   aws ssm send-command --instance-ids <EC2_INSTANCE_ID> --document-name "AWS-RunShellScript" --parameters '{"commands":["docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic clickstream-events --from-beginning --max-messages 5"]}'
   ```

2. **Access Monitoring Dashboards:**
   - Grafana: `http://<EC2_PUBLIC_IP>:3000` (admin/admin123)
   - Prometheus: `http://<EC2_PUBLIC_IP>:9090`
   - Spark UI: `http://<EC2_PUBLIC_IP>:8080`

### Google Colab Processing

The Spark processing is now done remotely using Google Colab:

1. **Connect to AWS Spark Cluster:**
   ```
   spark://<EC2_PUBLIC_IP>:7077
   ```

2. **Connect to AWS Kafka:**
   ```
   <EC2_PUBLIC_IP>:9092
   ```

3. **Connect to AWS PostgreSQL:**
   - Host: RDS endpoint
   - Port: 5432
   - Database: clickstream_db
   - User: streamingadmin

### Known Issues & Fixes

1. **Lambda IP Update Issue:**
   - Problem: Lambda uses hardcoded IP from previous deployment
   - Fix: `deploy_all.sh` automatically updates IP using regex pattern

2. **Docker Services Not Running:**
   - Problem: Services stop after deployment
   - Fix: Run `./scripts/setup_services.sh` to restart services

3. **RDS Security Group:**
   - Problem: Colab can't connect to PostgreSQL
   - Fix: Security group allows connections from anywhere (`0.0.0.0/0:5432`)

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
- [x] Google Colab remote processing
- [x] Infrastructure cleanup and optimization
- [ ] Final integration + demo

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
├── scripts/              # Deployment and setup scripts
│   ├── setup_services.sh
│   ├── deploy_all.sh
│   └── monitor_services.sh
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

### **Google Colab Approach**
- **Problem**: Spark job permission issues and Docker container debugging complexity
- **Solution**: Moved Spark processing to Google Colab for remote execution
- **Benefits**: 
  - No Docker permission issues
  - Real-time debugging and monitoring
  - Easy code modifications
  - Cost-effective processing

### **Infrastructure Cleanup**
- **Removed**: 127 temporary debug files
- **Simplified**: `setup_services.sh` - removed Spark job deployment code
- **Deleted**: `deploy_spark_job.sh` and test Spark job files
- **Updated**: RDS security group for Colab access

### **Current Architecture**
```
Lambda → Kafka → [Colab reads from Kafka] → [Colab processes data] → PostgreSQL
```

### **Key Advantages**
- ✅ **Simplified Debugging**: No Docker container issues
- ✅ **Real-time Monitoring**: Live logs in Colab
- ✅ **Easy Modifications**: Change code instantly
- ✅ **Cost-effective**: Free processing vs AWS costs
- ✅ **Reliable**: No permission or environment issues

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

# IoT Data Streaming Pipeline 🚀

A fully open-source real-time data streaming platform built on AWS infrastructure using Kafka, Apache Spark, PostgreSQL, S3, Prometheus, and Grafana. This project simulates IoT sensor data and processes it through a scalable, fault-tolerant pipeline for storage, analysis, and visualization.

## 🌐 Project Overview

This project demonstrates how to build a real-time IoT data pipeline using open-source tools on AWS EC2 infrastructure. Key objectives:

- Ingest sensor data using Kafka
- Process data in near real-time using Apache Spark
- Store raw data in S3 and transformed data in PostgreSQL
- Monitor system performance using Prometheus and Grafana
- Use AWS CDK (Python) for infrastructure as code

---

## 🏗️ Architecture

```
Sensor (AWS Lambda)
       ↓
   Kafka (EC2)
       ↓
Spark Processor (EC2)
  ↷           ↸
S3 (Raw)   PostgreSQL (Processed)
       ↓
 Monitoring
  (Prometheus + Grafana)
```

---

## 📦 Tech Stack

| Component      | Tech                      |
|----------------|---------------------------|
| Sensor Sim     | AWS Lambda (Python)       |
| Message Queue  | Apache Kafka (on EC2)     |
| Processing     | Apache Spark (on EC2)     |
| Storage        | AWS S3, AWS RDS (Postgres)|
| Monitoring     | Prometheus, Grafana       |
| IaC            | AWS CDK (Python)          |

---

## 🧹 Features

- ⚡ Real-time data ingestion with Kafka
- 🔥 Stream processing using Spark
- 📂 Dual storage: S3 for raw and Postgres for processed data
- 📈 Live system metrics using Prometheus and Grafana
- 🛠️ Reproducible infra setup using AWS CDK

---

## 🚧 Project Milestones

- [x] Architecture finalized
- [ ] CDK project setup
- [ ] Kafka EC2 instance
- [ ] Spark EC2 instance
- [ ] Lambda sensor simulator
- [ ] PostgreSQL schema + RDS
- [ ] Prometheus + Grafana monitoring
- [ ] Final integration + demo

---

## 📁 Folder Structure (Planned)

```
iot-streaming-pipeline/
│
├── cdk/                  # AWS CDK stacks
├── lambda-simulator/     # Sensor simulation code
├── kafka-setup/          # Kafka scripts and Dockerfiles
├── spark-processor/      # PySpark processing logic
├── monitoring/           # Prometheus & Grafana config
├── infra-scripts/        # Setup scripts
├── README.md
└── .gitignore
```

---

## 🧪 Demo Use Case

Simulate temperature and humidity data from smart building sensors and process this data to:
- Detect abnormal readings
- Store trends in a database
- Trigger alerts via monitoring dashboard

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

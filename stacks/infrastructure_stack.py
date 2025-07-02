import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_rds as rds,
    aws_secretsmanager as secretsmanager,
    aws_logs as logs,
    Duration,
    RemovalPolicy,
)
from constructs import Construct

class InfrastructureStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # VPC for our infrastructure
        vpc = ec2.Vpc(self, "StreamingVPC",
            max_azs=2,
            nat_gateways=0,  # Cost optimization for free tier
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                )
            ]
        )

        # Security Group for EC2 instance
        ec2_security_group = ec2.SecurityGroup(self, "EC2SecurityGroup",
            vpc=vpc,
            description="Security group for streaming pipeline EC2 instance",
            allow_all_outbound=True
        )

        # Allow SSH access
        ec2_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(22),
            description="SSH access"
        )

        # Allow Kafka access
        ec2_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(9092),
            description="Kafka access"
        )

        # Allow Prometheus access
        ec2_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(9090),
            description="Prometheus access"
        )

        # Allow Grafana access
        ec2_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(3000),
            description="Grafana access"
        )

        # Allow Spark UI access
        ec2_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(4040),
            description="Spark UI access"
        )

        # IAM Role for EC2 instance
        ec2_role = iam.Role(self, "EC2Role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchAgentServerPolicy")
            ]
        )

        # Add custom policy for S3 access (for Lambda to send data)
        ec2_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "s3:GetObject",
                "s3:PutObject",
                "s3:ListBucket"
            ],
            resources=["*"]
        ))

        # User data script to install Docker and setup services
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "#!/bin/bash",
            "yum update -y",
            "yum install -y docker",
            "service docker start",
            "usermod -a -G docker ec2-user",
            "yum install -y git",
            "curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)\" -o /usr/local/bin/docker-compose",
            "chmod +x /usr/local/bin/docker-compose",
            "mkdir -p /opt/streaming-pipeline",
            "cd /opt/streaming-pipeline"
        )

        # Create Docker Compose file
        docker_compose_content = '''version: '3.8'

services:
  zookeeper:
    image: confluentinc/cp-zookeeper:latest
    hostname: zookeeper
    container_name: zookeeper
    ports:
      - "2181:2181"
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    volumes:
      - zookeeper-data:/var/lib/zookeeper/data
      - zookeeper-logs:/var/lib/zookeeper/log

  kafka:
    image: confluentinc/cp-kafka:latest
    hostname: kafka
    container_name: kafka
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: 'zookeeper:2181'
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
    volumes:
      - kafka-data:/var/lib/kafka/data

  spark-master:
    image: bitnami/spark:latest
    hostname: spark-master
    container_name: spark-master
    ports:
      - "8080:8080"
      - "7077:7077"
    environment:
      - SPARK_MODE=master
      - SPARK_RPC_AUTHENTICATION_ENABLED=no
      - SPARK_RPC_ENCRYPTION_ENABLED=no
      - SPARK_LOCAL_STORAGE_ENCRYPTION_ENABLED=no
      - SPARK_SSL_ENABLED=no
    volumes:
      - spark-data:/opt/bitnami/spark

  spark-worker:
    image: bitnami/spark:latest
    hostname: spark-worker
    container_name: spark-worker
    depends_on:
      - spark-master
    environment:
      - SPARK_MODE=worker
      - SPARK_MASTER_URL=spark://spark-master:7077
      - SPARK_WORKER_MEMORY=1G
      - SPARK_WORKER_CORES=1
      - SPARK_RPC_AUTHENTICATION_ENABLED=no
      - SPARK_RPC_ENCRYPTION_ENABLED=no
      - SPARK_LOCAL_STORAGE_ENCRYPTION_ENABLED=no
      - SPARK_SSL_ENABLED=no
    volumes:
      - spark-data:/opt/bitnami/spark

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
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=200h'
      - '--web.enable-lifecycle'

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
    volumes:
      - grafana-data:/var/lib/grafana

volumes:
  zookeeper-data:
  zookeeper-logs:
  kafka-data:
  spark-data:
  prometheus-data:
  grafana-data:
'''

        # Create Prometheus configuration
        prometheus_config = '''global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'kafka'
    static_configs:
      - targets: ['localhost:9092']

  - job_name: 'spark'
    static_configs:
      - targets: ['localhost:8080']
'''

        # Add Docker Compose and config files to user data
        user_data.add_commands(
            f"cat > /opt/streaming-pipeline/docker-compose.yml << 'EOF'\n{docker_compose_content}\nEOF",
            f"cat > /opt/streaming-pipeline/prometheus.yml << 'EOF'\n{prometheus_config}\nEOF",
            "cd /opt/streaming-pipeline",
            "docker-compose up -d",
            "echo 'Infrastructure setup complete!'"
        )

        # EC2 Instance (t3.micro for free tier)
        ec2_instance = ec2.Instance(self, "StreamingInstance",
            vpc=vpc,
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            machine_image=ec2.MachineImage.latest_amazon_linux_2(),
            security_group=ec2_security_group,
            role=ec2_role,
            user_data=user_data,
            key_name=None,  # Use SSM for access instead of key pair
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(
                        volume_size=30,  # Free tier limit
                        volume_type=ec2.EbsDeviceVolumeType.GP3,
                        delete_on_termination=True
                    )
                )
            ]
        )

        # RDS PostgreSQL instance (free tier)
        db_secret = secretsmanager.Secret(self, "DatabaseSecret",
            secret_name="streaming-pipeline-db-secret",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username": "admin"}',
                generate_string_key="password",
                exclude_characters="\"@/\\"
            )
        )

        db_security_group = ec2.SecurityGroup(self, "DatabaseSecurityGroup",
            vpc=vpc,
            description="Security group for RDS PostgreSQL",
            allow_all_outbound=True
        )

        # Allow EC2 to connect to RDS
        db_security_group.add_ingress_rule(
            peer=ec2_security_group,
            connection=ec2.Port.tcp(5432),
            description="Allow EC2 to connect to RDS"
        )

        database = rds.DatabaseInstance(self, "StreamingDatabase",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15_4
            ),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_groups=[db_security_group],
            credentials=rds.Credentials.from_secret(db_secret),
            database_name="clickstream_db",
            allocated_storage=20,
            max_allocated_storage=100,
            backup_retention=Duration.days(7),
            deletion_protection=False,
            removal_policy=RemovalPolicy.DESTROY,
            publicly_accessible=True  # For free tier simplicity
        )

        # Outputs
        cdk.CfnOutput(self, "EC2InstanceId",
            value=ec2_instance.instance_id,
            description="EC2 Instance ID"
        )

        cdk.CfnOutput(self, "EC2PublicIP",
            value=ec2_instance.instance_public_ip,
            description="EC2 Public IP Address"
        )

        cdk.CfnOutput(self, "DatabaseEndpoint",
            value=database.instance_endpoint.hostname,
            description="RDS PostgreSQL Endpoint"
        )

        cdk.CfnOutput(self, "DatabaseSecretArn",
            value=db_secret.secret_arn,
            description="Database Secret ARN"
        )

        cdk.CfnOutput(self, "KafkaEndpoint",
            value=f"{ec2_instance.instance_public_ip}:9092",
            description="Kafka Endpoint"
        )

        cdk.CfnOutput(self, "GrafanaURL",
            value=f"http://{ec2_instance.instance_public_ip}:3000",
            description="Grafana Dashboard URL"
        )

        cdk.CfnOutput(self, "PrometheusURL",
            value=f"http://{ec2_instance.instance_public_ip}:9090",
            description="Prometheus Metrics URL"
        ) 
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
            connection=ec2.Port.tcp(8080),
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

        # Add CloudFormation permissions for Spark job deployment
        ec2_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "cloudformation:DescribeStacks",
                "cloudformation:ListStacks"
            ],
            resources=["*"]
        ))



        # Minimal user data script - just install Docker and create directory
        user_data = ec2.UserData.for_linux()
        
        # Basic setup commands only
        user_data.add_commands(
            "#!/bin/bash",
            "set -e",
            "exec > >(tee /var/log/user-data.log)",
            "exec 2>&1",
            "",
            "echo '=== Starting minimal infrastructure setup ==='",
            "yum update -y",
            "yum install -y docker git postgresql15",
            "systemctl enable docker",
            "systemctl start docker",
            "usermod -a -G docker ec2-user",
            "",
            "# Install Docker Compose",
            "curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)\" -o /usr/local/bin/docker-compose",
            "chmod +x /usr/local/bin/docker-compose",
            "ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose",
            "",
            "# Create working directory",
            "mkdir -p /opt/streaming-pipeline",
            "cd /opt/streaming-pipeline",
            "",
            "echo '=== Minimal setup complete - services will be configured via post-deployment script ==='",
        )

        # Docker Compose and Prometheus config moved to post-deployment script

        # No additional commands - all setup will be done via post-deployment script

        # EC2 Instance (t3.medium for better performance)
        ec2_instance = ec2.Instance(self, "StreamingInstance",
            vpc=vpc,
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM),
            machine_image=ec2.MachineImage.latest_amazon_linux2(),
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

        # Tag the instance for easy identification
        cdk.Tags.of(ec2_instance).add("Name", "Streaming-Pipeline-Instance")
        cdk.Tags.of(ec2_instance).add("Project", "ClickstreamAnalytics")

        # RDS PostgreSQL instance (free tier)
        db_secret = secretsmanager.Secret(self, "DatabaseSecret",
            secret_name="streaming-pipeline-db-secret",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username": "streamingadmin"}',
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
        
        # Allow connections from anywhere (for Colab access)
        db_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(5432),
            description="Allow PostgreSQL access from anywhere"
        )
        db_security_group.add_ingress_rule(
            peer=ec2_security_group,
            connection=ec2.Port.tcp(5432),
            description="Allow EC2 to connect to RDS"
        )

        database = rds.DatabaseInstance(self, "StreamingDatabase",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16
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

        # Add Secrets Manager permissions for database password (after db_secret is defined)
        ec2_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "secretsmanager:GetSecretValue"
            ],
            resources=[db_secret.secret_arn]
        ))

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
            description="Grafana Dashboard URL (admin/admin123)"
        )

        cdk.CfnOutput(self, "PrometheusURL",
            value=f"http://{ec2_instance.instance_public_ip}:9090",
            description="Prometheus Metrics URL"
        )

        cdk.CfnOutput(self, "SparkUIURL",
            value=f"http://{ec2_instance.instance_public_ip}:8080",
            description="Spark UI URL"
        )

        cdk.CfnOutput(self, "VPCId",
            value=vpc.vpc_id,
            description="VPC ID"
        )

        cdk.CfnOutput(self, "SSMConnectCommand",
            value=f"aws ssm start-session --target {ec2_instance.instance_id}",
            description="Command to connect via SSM"
        )

        # Note: S3 bucket name will be available in CloudFormation outputs after deployment
        # You can get it by running: aws cloudformation describe-stacks --stack-name InfrastructureStack --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' --output text
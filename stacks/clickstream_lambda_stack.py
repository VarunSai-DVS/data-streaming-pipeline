import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
)
from constructs import Construct

class ClickstreamLambdaStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Get EC2 instance public IP from infrastructure stack
        # This will be automatically updated when infrastructure is deployed
        ec2_public_ip = self.node.try_get_context('ec2_public_ip') or '18.188.120.99'  # Will be updated after infrastructure deployment

        # Create Lambda layer for Kafka libraries
        kafka_layer = _lambda.LayerVersion(self, "KafkaLayer",
            code=_lambda.Code.from_asset("lambda-layer.zip"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_9],
            description="Kafka Python client library"
        )

        fn = _lambda.Function(self, "ClickstreamLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="clickstream_generator.lambda_handler",
            code=_lambda.Code.from_asset("lambda"),
            layers=[kafka_layer],
            environment={
                "KAFKA_BOOTSTRAP_SERVERS": f"{ec2_public_ip}:9092",
                "KAFKA_TOPIC": "clickstream-events"
            },
            timeout=cdk.Duration.seconds(30),
            memory_size=512
        )

        # Grant Lambda permissions to connect to EC2/Kafka
        fn.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ec2:DescribeInstances",
                "ec2:DescribeSecurityGroups"
            ],
            resources=["*"]
        ))

        # Grant Lambda permissions to write to CloudWatch Logs
        fn.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            resources=["*"]
        ))

        # Trigger every 1 minute
        rule = events.Rule(self, "TriggerEveryMinute",
            schedule=events.Schedule.rate(cdk.Duration.minutes(1)),
        )
        rule.add_target(targets.LambdaFunction(fn))

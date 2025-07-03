import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_s3 as s3,
    aws_events as events,
    aws_events_targets as targets,
)
from constructs import Construct

class ClickstreamLambdaStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        bucket = s3.Bucket(self, "ClickstreamDataBucket")

        fn = _lambda.Function(self, "ClickstreamLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="clickstream_generator.lambda_handler",
            code=_lambda.Code.from_asset("lambda"),
            environment={
                "BUCKET_NAME": bucket.bucket_name,
                "KAFKA_BOOTSTRAP_SERVERS": "34.204.97.63:9092",
                "KAFKA_TOPIC": "clickstream-events"
            },
            timeout=cdk.Duration.seconds(30),
            memory_size=512
        )

        bucket.grant_write(fn)

        # OPTIONAL: Trigger every 1 minute
        rule = events.Rule(self, "TriggerEveryMinute",
            schedule=events.Schedule.rate(cdk.Duration.minutes(1)),
        )
        rule.add_target(targets.LambdaFunction(fn))

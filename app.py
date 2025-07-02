#!/usr/bin/env python3
import aws_cdk as cdk

from stacks.clickstream_lambda_stack import ClickstreamLambdaStack
from stacks.infrastructure_stack import InfrastructureStack

app = cdk.App()

# Deploy Lambda stack first
ClickstreamLambdaStack(app, "ClickstreamLambdaStack")

# Deploy infrastructure stack
InfrastructureStack(app, "InfrastructureStack")

app.synth()

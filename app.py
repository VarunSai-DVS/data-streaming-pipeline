#!/usr/bin/env python3
import aws_cdk as cdk

from stacks.clickstream_lambda_stack import ClickstreamLambdaStack
from stacks.infrastructure_stack import InfrastructureStack

app = cdk.App()

# Deploy infrastructure stack first
InfrastructureStack(app, "InfrastructureStack")

# Deploy Lambda stack
ClickstreamLambdaStack(app, "ClickstreamLambdaStack")

app.synth()

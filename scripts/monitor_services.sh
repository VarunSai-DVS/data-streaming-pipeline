#!/bin/bash
# Monitor streaming pipeline services

EC2_ID=$(aws cloudformation describe-stacks --stack-name InfrastructureStack --query "Stacks[0].Outputs[?OutputKey=='EC2InstanceId'].OutputValue" --output text)

echo "=== Service Status ==="
aws ssm send-command \
    --instance-ids "$EC2_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters '{"commands":["docker ps","echo","docker logs kafka --tail 10","echo","docker logs spark-master --tail 10"]}' \
    --output text

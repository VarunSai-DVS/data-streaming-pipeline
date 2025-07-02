import json
import random
from datetime import datetime
import uuid
import boto3
import os

s3 = boto3.client('s3')
BUCKET_NAME = os.environ['BUCKET_NAME']

def lambda_handler(event, context):
    user_id = f"u{random.randint(1000, 9999)}"
    session_id = str(uuid.uuid4())
    event_type = random.choice(["PAGE_VIEW", "ADD_TO_CART", "PURCHASE", "LOGIN", "LOGOUT"])
    region = random.choice(["us-east-1", "us-west-2", "eu-central-1"])
    device = random.choice(["mobile", "desktop", "tablet"])
    
    payload = {
        "userId": user_id,
        "sessionId": session_id,
        "eventType": event_type,
        "eventTime": datetime.utcnow().isoformat(),
        "page": f"/products/{random.randint(100, 999)}",
        "referrer": "/home",
        "device": device,
        "region": region
    }

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=f"clickstream/{session_id}.json",
        Body=json.dumps(payload)
    )

    return {
        'statusCode': 200,
        'body': json.dumps(payload)
    }

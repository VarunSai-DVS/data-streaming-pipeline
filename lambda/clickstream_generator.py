import json
import random
from datetime import datetime
import uuid
import boto3
import os
from kafka import KafkaProducer
from kafka.errors import KafkaError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', '34.204.97.63:9092')
KAFKA_TOPIC = os.environ.get('KAFKA_TOPIC', 'clickstream-events')
BUCKET_NAME = os.environ.get('BUCKET_NAME')  # Keep for fallback

# Initialize Kafka producer
def get_kafka_producer():
    """Create and return a Kafka producer."""
    try:
        producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            retries=3,
            acks='all'
        )
        return producer
    except Exception as e:
        logger.error(f"Failed to create Kafka producer: {e}")
        return None

def send_to_kafka(producer, topic, key, message):
    """Send message to Kafka topic."""
    try:
        future = producer.send(topic, key=key, value=message)
        record_metadata = future.get(timeout=10)
        logger.info(f"Message sent to Kafka: topic={record_metadata.topic}, partition={record_metadata.partition}, offset={record_metadata.offset}")
        return True
    except KafkaError as e:
        logger.error(f"Kafka error: {e}")
        return False
    except Exception as e:
        logger.error(f"Error sending to Kafka: {e}")
        return False

def send_to_s3_fallback(payload, session_id):
    """Fallback: Send data to S3 if Kafka fails."""
    try:
        s3 = boto3.client('s3')
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=f"clickstream/{session_id}.json",
            Body=json.dumps(payload)
        )
        logger.info(f"Data sent to S3 as fallback: {session_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send to S3: {e}")
        return False

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
        "region": region,
        "source": "lambda-kafka-producer"
    }

    # Try to send to Kafka first
    producer = get_kafka_producer()
    kafka_success = False
    
    if producer:
        kafka_success = send_to_kafka(producer, KAFKA_TOPIC, session_id, payload)
        producer.flush()  # Ensure all messages are sent
        producer.close()
    
    # Fallback to S3 if Kafka fails
    if not kafka_success:
        logger.warning("Kafka failed, falling back to S3")
        s3_success = send_to_s3_fallback(payload, session_id)
        if not s3_success:
            logger.error("Both Kafka and S3 failed")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to send data to both Kafka and S3'})
            }
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Clickstream data sent successfully',
            'kafka_success': kafka_success,
            'data': payload
        })
    }

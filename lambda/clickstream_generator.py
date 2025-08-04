import json
import random
from datetime import datetime
import uuid
import os
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = os.environ['KAFKA_BOOTSTRAP_SERVERS']
KAFKA_TOPIC = os.environ.get('KAFKA_TOPIC', 'clickstream-events')

def lambda_handler(event, context):
    # Debug: Print environment variables
    print(f"KAFKA_BOOTSTRAP_SERVERS: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"KAFKA_TOPIC: {KAFKA_TOPIC}")
    
    # Create Kafka producer with explicit configuration
    bootstrap_servers = KAFKA_BOOTSTRAP_SERVERS.split(',') if ',' in KAFKA_BOOTSTRAP_SERVERS else [KAFKA_BOOTSTRAP_SERVERS]
    print(f"Using bootstrap servers: {bootstrap_servers}")
    
    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None,
        retries=3,
        acks='all',
        request_timeout_ms=10000,
        api_version=(2, 5, 0),  # Specify API version
        security_protocol='PLAINTEXT'
    )
    
    # Generate clickstream event
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

    try:
        # Send to Kafka with session_id as key for partitioning
        future = producer.send(KAFKA_TOPIC, key=session_id, value=payload)
        record_metadata = future.get(timeout=10)
        
        producer.flush()
        producer.close()
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Event sent to Kafka successfully',
                'topic': record_metadata.topic,
                'partition': record_metadata.partition,
                'offset': record_metadata.offset,
                'payload': payload
            })
        }
        
    except KafkaError as e:
        producer.close()
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Failed to send to Kafka: {str(e)}',
                'payload': payload
            })
        }

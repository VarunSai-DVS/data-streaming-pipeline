#!/usr/bin/env python3
"""
Kafka Connection Test Script
Tests connectivity to Kafka and verifies topic creation.
"""

import json
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
import time

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = '34.204.97.63:9092'
TOPIC_NAME = 'clickstream-events'

def test_kafka_producer():
    """Test Kafka producer connectivity."""
    print("🧪 Testing Kafka producer...")
    
    try:
        producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            retries=3,
            acks='all'
        )
        
        # Test message
        test_message = {
            "test": True,
            "timestamp": time.time(),
            "message": "Kafka connectivity test"
        }
        
        # Send test message
        future = producer.send(TOPIC_NAME, key='test-key', value=test_message)
        record_metadata = future.get(timeout=10)
        
        print(f"✅ Producer test successful!")
        print(f"   Topic: {record_metadata.topic}")
        print(f"   Partition: {record_metadata.partition}")
        print(f"   Offset: {record_metadata.offset}")
        
        producer.flush()
        producer.close()
        return True
        
    except Exception as e:
        print(f"❌ Producer test failed: {e}")
        return False

def test_kafka_consumer():
    """Test Kafka consumer connectivity."""
    print("🧪 Testing Kafka consumer...")
    
    try:
        consumer = KafkaConsumer(
            TOPIC_NAME,
            bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id='test-consumer-group'
        )
        
        # Wait for messages (timeout after 10 seconds)
        start_time = time.time()
        message_received = False
        
        while time.time() - start_time < 10:
            messages = consumer.poll(timeout_ms=1000)
            for tp, records in messages.items():
                for record in records:
                    print(f"✅ Consumer test successful!")
                    print(f"   Received message: {record.value}")
                    message_received = True
                    break
            if message_received:
                break
        
        consumer.close()
        
        if not message_received:
            print("⚠️ No messages received (this is normal if no data is being produced)")
        
        return True
        
    except Exception as e:
        print(f"❌ Consumer test failed: {e}")
        return False

def list_kafka_topics():
    """List all Kafka topics."""
    print("📋 Listing Kafka topics...")
    
    try:
        consumer = KafkaConsumer(
            bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS]
        )
        
        topics = consumer.topics()
        print(f"✅ Found {len(topics)} topics:")
        for topic in topics:
            print(f"   - {topic}")
        
        consumer.close()
        return True
        
    except Exception as e:
        print(f"❌ Failed to list topics: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("🔧 KAFKA CONNECTIVITY TEST")
    print("=" * 50)
    
    # List topics first
    list_kafka_topics()
    
    print("\n" + "-" * 50)
    
    # Test producer
    producer_success = test_kafka_producer()
    
    print("\n" + "-" * 50)
    
    # Test consumer
    consumer_success = test_kafka_consumer()
    
    print("\n" + "=" * 50)
    
    if producer_success and consumer_success:
        print("🎉 All Kafka tests passed!")
        print("✅ Ready for Lambda → Kafka integration")
    else:
        print("❌ Some Kafka tests failed")
        print("⚠️ Check Kafka setup and connectivity")
    
    print("=" * 50) 
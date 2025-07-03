#!/usr/bin/env python3
"""
Kafka Topic Creation Script
Creates the clickstream-events topic for the data streaming pipeline.
"""

import subprocess
import sys
import time

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return None

def create_kafka_topic():
    """Create the clickstream-events topic in Kafka."""
    
    # Kafka topic configuration
    topic_name = "clickstream-events"
    partitions = 3
    replication_factor = 1
    
    # Docker command to create topic
    create_topic_command = f"""
    docker exec kafka kafka-topics \
        --create \
        --topic {topic_name} \
        --partitions {partitions} \
        --replication-factor {replication_factor} \
        --bootstrap-server localhost:9092
    """
    
    # List topics command to verify
    list_topics_command = """
    docker exec kafka kafka-topics \
        --list \
        --bootstrap-server localhost:9092
    """
    
    # Describe topic command to show details
    describe_topic_command = f"""
    docker exec kafka kafka-topics \
        --describe \
        --topic {topic_name} \
        --bootstrap-server localhost:9092
    """
    
    print("🚀 Setting up Kafka topic for clickstream events...")
    print(f"📋 Topic: {topic_name}")
    print(f"📊 Partitions: {partitions}")
    print(f"🔄 Replication Factor: {replication_factor}")
    print("-" * 50)
    
    # Create the topic
    result = run_command(create_topic_command, "Creating Kafka topic")
    if result is None:
        print("❌ Failed to create Kafka topic")
        return False
    
    # Wait a moment for topic to be created
    time.sleep(2)
    
    # List all topics to verify
    print("\n📋 Listing all Kafka topics:")
    list_result = run_command(list_topics_command, "Listing topics")
    if list_result:
        print(list_result)
    
    # Describe the created topic
    print(f"\n📊 Describing topic '{topic_name}':")
    describe_result = run_command(describe_topic_command, "Describing topic")
    if describe_result:
        print(describe_result)
    
    print("\n🎉 Kafka topic setup completed!")
    return True

def test_kafka_connection():
    """Test Kafka connectivity from Lambda perspective."""
    print("\n🧪 Testing Kafka connectivity...")
    
    # Test command to check if Kafka is accessible
    test_command = """
    docker exec kafka kafka-broker-api-versions \
        --bootstrap-server localhost:9092
    """
    
    result = run_command(test_command, "Testing Kafka connectivity")
    if result:
        print("✅ Kafka is accessible and running")
        return True
    else:
        print("❌ Kafka connectivity test failed")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 KAFKA TOPIC SETUP FOR CLICKSTREAM PIPELINE")
    print("=" * 60)
    
    # Test connectivity first
    if not test_kafka_connection():
        print("❌ Cannot proceed - Kafka is not accessible")
        sys.exit(1)
    
    # Create the topic
    if create_kafka_topic():
        print("\n🎯 Next Steps:")
        print("1. Update Lambda function to send data to Kafka")
        print("2. Test the Lambda → Kafka integration")
        print("3. Set up Spark streaming job to consume from Kafka")
        print("4. Connect Spark to PostgreSQL for data storage")
    else:
        print("\n❌ Topic creation failed. Please check Kafka setup.")
        sys.exit(1) 
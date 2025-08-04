#!/usr/bin/env python3
"""
Clickstream Data Processing Spark Streaming Job

This job:
1. Reads clickstream events from Kafka
2. Processes and aggregates the data in real-time
3. Writes processed results to PostgreSQL
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.sql.streaming import DataStreamWriter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ClickstreamProcessor")

class ClickstreamProcessor:
    def __init__(self):
        self.spark = None
        self.kafka_bootstrap_servers = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.kafka_topic = "clickstream-events"
        
        # Get PostgreSQL connection details from environment
        postgres_host = os.environ.get('DB_HOST', 'localhost')
        postgres_password = os.environ.get('DB_PASSWORD', 'your_password_here')
        
        self.postgres_url = f"jdbc:postgresql://{postgres_host}:5432/clickstream_db"
        self.postgres_properties = {
            "user": "streamingadmin",
            "password": postgres_password,
            "driver": "org.postgresql.Driver"
        }
        
    def create_spark_session(self):
        """Create Spark session with Kafka and PostgreSQL support"""
        self.spark = SparkSession.builder \
            .appName("ClickstreamProcessor") \
            .config("spark.jars.packages", 
                   "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0," +
                   "org.postgresql:postgresql:42.7.1") \
            .config("spark.sql.streaming.checkpointLocation", "/tmp/checkpoint") \
            .getOrCreate()
        
        # Set log level
        self.spark.sparkContext.setLogLevel("WARN")
        
    def define_schema(self):
        """Define schema for clickstream events"""
        return StructType([
            StructField("userId", StringType(), True),
            StructField("sessionId", StringType(), True),
            StructField("eventType", StringType(), True),
            StructField("eventTime", StringType(), True),
            StructField("page", StringType(), True),
            StructField("referrer", StringType(), True),
            StructField("device", StringType(), True),
            StructField("region", StringType(), True)
        ])
    
    def process_clickstream_data(self, df):
        """Process and aggregate clickstream data"""
        
        # Parse timestamp
        df_parsed = df.withColumn("timestamp", to_timestamp("eventTime"))
        
        # Create window for aggregations (5-minute windows)
        window_spec = Window.partitionBy("userId").orderBy("timestamp").rangeBetween(-300, 0)
        
        # Calculate session metrics
        session_metrics = df_parsed \
            .withWatermark("timestamp", "10 minutes") \
            .groupBy(
                "userId",
                "sessionId",
                window("timestamp", "5 minutes")
            ) \
            .agg(
                count("*").alias("event_count"),
                countDistinct("eventType").alias("unique_events"),
                collect_list("eventType").alias("events"),
                first("timestamp").alias("session_start"),
                last("timestamp").alias("session_end"),
                sum(when(col("eventType") == "PURCHASE", 1).otherwise(0)).alias("purchases"),
                sum(when(col("eventType") == "ADD_TO_CART", 1).otherwise(0)).alias("add_to_cart"),
                first("device").alias("device"),
                first("region").alias("region")
            )
        
        # Calculate real-time metrics
        realtime_metrics = df_parsed \
            .withWatermark("timestamp", "10 minutes") \
            .groupBy(
                window("timestamp", "1 minute")
            ) \
            .agg(
                count("*").alias("total_events"),
                countDistinct("userId").alias("unique_users"),
                countDistinct("sessionId").alias("unique_sessions"),
                sum(when(col("eventType") == "PURCHASE", 1).otherwise(0)).alias("total_purchases"),
                sum(when(col("eventType") == "ADD_TO_CART", 1).otherwise(0)).alias("total_add_to_cart")
            )
        
        return session_metrics, realtime_metrics
    
    def write_to_postgresql(self, df, table_name):
        """Write DataFrame to PostgreSQL"""
        df.write \
            .mode("append") \
            .format("jdbc") \
            .option("url", self.postgres_url) \
            .option("dbtable", table_name) \
            .option("user", self.postgres_properties["user"]) \
            .option("password", self.postgres_properties["password"]) \
            .option("driver", self.postgres_properties["driver"]) \
            .save()
    
    def start_streaming(self):
        """Start the streaming job"""
        try:
            logger.info("Starting Clickstream Processing Job...")
            logger.info(f"Kafka Bootstrap Servers: {self.kafka_bootstrap_servers}")
            logger.info(f"Database Host: {os.getenv('DB_HOST', 'Not Set')}")
            
            # Create Spark session
            self.create_spark_session()
            
            # Read from Kafka
            kafka_df = self.spark \
                .readStream \
                .format("kafka") \
                .option("kafka.bootstrap.servers", self.kafka_bootstrap_servers) \
                .option("subscribe", self.kafka_topic) \
                .option("startingOffsets", "latest") \
                .load()
            
            # Parse JSON data
            schema = self.define_schema()
            parsed_df = kafka_df \
                .select(from_json(col("value").cast("string"), schema).alias("data")) \
                .select("data.*")
            
            # Process data
            session_metrics, realtime_metrics = self.process_clickstream_data(parsed_df)
            
            # Write session metrics to PostgreSQL
            session_query = session_metrics \
                .writeStream \
                .foreachBatch(self.write_session_metrics) \
                .outputMode("append") \
                .trigger(processingTime="1 minute") \
                .start()
            
            # Write real-time metrics to PostgreSQL
            realtime_query = realtime_metrics \
                .writeStream \
                .foreachBatch(self.write_realtime_metrics) \
                .outputMode("append") \
                .trigger(processingTime="1 minute") \
                .start()
            
            # Wait for termination
            self.spark.streams.awaitAnyTermination()
            
        except Exception as e:
            logger.error(f"Error in streaming job: {e}")
            raise
    
    def write_session_metrics(self, df, epoch_id):
        """Write session metrics to PostgreSQL"""
        if not df.rdd.isEmpty():
            logger.info(f"Processing batch {epoch_id} with {df.count()} records")
            self.write_to_postgresql(df, "session_metrics")
            logger.info(f"Successfully processed batch {epoch_id}")
    
    def write_realtime_metrics(self, df, epoch_id):
        """Write real-time metrics to PostgreSQL"""
        if not df.rdd.isEmpty():
            logger.info(f"Processing real-time batch {epoch_id} with {df.count()} records")
            self.write_to_postgresql(df, "realtime_metrics")
            logger.info(f"Successfully processed real-time batch {epoch_id}")

def main():
    """Main function"""
    processor = ClickstreamProcessor()
    
    # Update PostgreSQL password from environment if available
    if os.environ.get('DB_PASSWORD'):
        processor.postgres_properties["password"] = os.environ.get('DB_PASSWORD')
    
    # Update Kafka bootstrap servers from environment if available
    if os.environ.get('KAFKA_BOOTSTRAP_SERVERS'):
        processor.kafka_bootstrap_servers = os.environ.get('KAFKA_BOOTSTRAP_SERVERS')
    
    try:
        processor.start_streaming()
    except KeyboardInterrupt:
        logger.info("Stopping streaming job...")
    except Exception as e:
        logger.error(f"Error in streaming job: {e}")
        raise

if __name__ == "__main__":
    main() 
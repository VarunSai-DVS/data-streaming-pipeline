#!/usr/bin/env python3
"""
Enhanced Clickstream Processor with Business Metrics using JDBC
Runs inside Docker network with automatic restarts
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.sql.window import Window
from pyspark.sql.functions import to_timestamp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ClickstreamProcessor")

# Environment configuration - uses Docker network names
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')
POSTGRES_USER = 'streamingadmin'
POSTGRES_DB = 'clickstream_db'

logger.info(f"Starting with config: Kafka={KAFKA_BOOTSTRAP_SERVERS}, DB={POSTGRES_HOST}")

# Initialize Spark Session
spark = SparkSession.builder \
    .appName("ClickstreamProcessor") \
    .master("spark://spark-master:7077") \
    .config("spark.sql.streaming.checkpointLocation", "/tmp/checkpoint") \
    .config("spark.sql.streaming.forceDeleteTempCheckpointLocation", "true") \
    .config("spark.streaming.stopGracefullyOnShutdown", "true") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# Define schema to match actual Kafka message format
clickstream_schema = StructType([
    StructField("userId", StringType(), True),
    StructField("sessionId", StringType(), True),
    StructField("eventType", StringType(), True),
    StructField("eventTime", StringType(), True),  # Keep as string, convert to timestamp later
    StructField("page", StringType(), True),
    StructField("referrer", StringType(), True),
    StructField("device", StringType(), True),
    StructField("region", StringType(), True)
])

def verify_tables():
    """Verify that all required tables exist in the database"""
    try:
        required_tables = [
            "clickstream_events",
            "realtime_metrics", 
            "page_metrics",
            "user_behavior",
            "device_analytics"
        ]
        
        # Test connection and verify tables exist
        for table_name in required_tables:
            try:
                # Try to read from the table to verify it exists
                test_df = spark.read \
                    .format("jdbc") \
                    .option("url", f"jdbc:postgresql://{POSTGRES_HOST}:5432/{POSTGRES_DB}") \
                    .option("dbtable", table_name) \
                    .option("user", POSTGRES_USER) \
                    .option("password", POSTGRES_PASSWORD) \
                    .option("driver", "org.postgresql.Driver") \
                    .load()
                
                logger.info(f"✅ Table {table_name} exists and is accessible")
            except Exception as e:
                logger.error(f"❌ Table {table_name} not found or not accessible: {e}")
                raise Exception(f"Required table {table_name} is missing. Please run database_schema.sql first.")
        
        logger.info("✅ All required tables verified successfully")
        
    except Exception as e:
        logger.error(f"❌ Database verification failed: {e}")
        raise

def write_to_postgres(df, table_name, mode="append"):
    """Write DataFrame to PostgreSQL using JDBC"""
    try:
        df.write \
            .format("jdbc") \
            .option("url", f"jdbc:postgresql://{POSTGRES_HOST}:5432/{POSTGRES_DB}") \
            .option("dbtable", table_name) \
            .option("user", POSTGRES_USER) \
            .option("password", POSTGRES_PASSWORD) \
            .option("driver", "org.postgresql.Driver") \
            .mode(mode) \
            .save()
        logger.info(f"✅ Successfully wrote to {table_name}")
    except Exception as e:
        logger.error(f"❌ Error writing to {table_name}: {e}")
        raise

def process_batch(df, epoch_id):
    """Process each batch of streaming data"""
    
    if df.count() == 0:
        logger.info(f"Empty batch {epoch_id}")
        return
    
    logger.info(f"Processing batch {epoch_id} with {df.count()} records")
    
    try:
        # Cache the DataFrame for multiple operations
        df.cache()
        
        # 1. Store raw events
        try:
            store_raw_events(df)
        except Exception as e:
            logger.error(f"❌ Error storing raw events: {e}")
        
        # 2. Calculate real-time metrics
        try:
            calculate_realtime_metrics(df)
        except Exception as e:
            logger.error(f"❌ Error calculating metrics: {e}")
        
        # 3. Update page metrics
        try:
            update_page_metrics(df)
        except Exception as e:
            logger.error(f"❌ Error updating page metrics: {e}")
        
        # 4. Update user behavior
        try:
            update_user_behavior(df)
        except Exception as e:
            logger.error(f"❌ Error updating user behavior: {e}")
        
        # 5. Update device/country analytics
        try:
            update_device_analytics(df)
        except Exception as e:
            logger.error(f"❌ Error updating device analytics: {e}")
        
        # Unpersist the cached DataFrame
        df.unpersist()
        
        logger.info(f"✅ Successfully processed batch {epoch_id}")
        
    except Exception as e:
        logger.error(f"❌ Error processing batch {epoch_id}: {e}")
        # Don't raise the exception to keep the job running

def store_raw_events(df):
    """Store raw clickstream events using JDBC"""
    # Map new field names to database column names and convert data types
    events_df = df.select(
        col("userId").alias("user_id"),
        col("page").alias("page_url"),
        col("eventType").alias("event_type"),
        to_timestamp(col("eventTime")).alias("timestamp"),  # Convert string to timestamp
        col("sessionId").alias("session_id"),
        col("device"),
        col("region"),
        col("referrer")
    ).withColumn("created_at", current_timestamp())
    write_to_postgres(events_df, "clickstream_events")

def calculate_realtime_metrics(df):
    """Calculate real-time metrics for dashboard using JDBC"""
    
    # Calculate metrics
    metrics = df.agg(
        count("*").alias("total_events"),
        countDistinct("userId").alias("unique_users"),
        countDistinct("sessionId").alias("unique_sessions"),
        sum(when(col("eventType") == "PAGE_VIEW", 1).otherwise(0)).alias("page_views"),
        sum(when(col("eventType") == "PURCHASE", 1).otherwise(0)).alias("purchases"),
        sum(when(col("eventType") == "ADD_TO_CART", 1).otherwise(0)).alias("cart_additions")
    ).collect()[0]
    
    # Calculate bounce rate (sessions with only 1 event)
    session_events = df.groupBy("sessionId").count()
    bounce_sessions = session_events.filter(col("count") == 1).count()
    total_sessions = session_events.count()
    bounce_rate = (bounce_sessions / total_sessions * 100) if total_sessions > 0 else 0
    
    # Create metrics DataFrame
    metrics_df = spark.createDataFrame([(
        datetime.now(),
        metrics['total_events'],
        metrics['unique_users'],
        metrics['unique_sessions'],
        metrics['page_views'],
        metrics['purchases'],
        metrics['cart_additions'],
        float(bounce_rate),
        0  # avg_session_duration placeholder
    )], ["metric_timestamp", "total_events", "unique_users", "unique_sessions", 
          "page_views", "purchases", "cart_additions", "bounce_rate", "avg_session_duration"])
    
    write_to_postgres(metrics_df, "realtime_metrics")

def update_page_metrics(df):
    """Update page-level metrics using JDBC"""
    
    page_metrics = df.filter(col("eventType") == "PAGE_VIEW") \
        .groupBy("page") \
        .agg(
            count("*").alias("view_count"),
            countDistinct("userId").alias("unique_visitors")
        )
    
    if page_metrics.count() > 0:
        # Map field names to database columns
        page_metrics_mapped = page_metrics.select(
            col("page").alias("page_url"),
            col("view_count"),
            col("unique_visitors")
        )
        write_to_postgres(page_metrics_mapped, "page_metrics", mode="append")

def update_user_behavior(df):
    """Update user behavior metrics using JDBC"""
    
    user_metrics = df.groupBy("userId").agg(
        countDistinct("sessionId").alias("sessions"),
        count("*").alias("events"),
        sum(when(col("eventType") == "PURCHASE", 1).otherwise(0)).alias("purchases"),
        max(to_timestamp(col("eventTime"))).alias("last_active")  # Convert to timestamp
    )
    
    if user_metrics.count() > 0:
        # Map field names to database columns
        user_metrics_mapped = user_metrics.select(
            col("userId").alias("user_id"),
            col("sessions"),
            col("events"),
            col("purchases"),
            col("last_active")
        )
        write_to_postgres(user_metrics_mapped, "user_behavior", mode="append")

def update_device_analytics(df):
    """Update device and country analytics using JDBC"""
    
    # Device analytics
    device_metrics = df.groupBy("device").agg(
        count("*").alias("event_count"),
        countDistinct("userId").alias("unique_users")
    )
    
    # Country analytics
    country_metrics = df.groupBy("region").agg(
        count("*").alias("event_count"),
        countDistinct("userId").alias("unique_users")
    )
    
    # Combine device and country metrics
    device_metrics = device_metrics.withColumn("dimension_type", lit("device")) \
        .withColumnRenamed("device", "dimension_value")
    
    country_metrics = country_metrics.withColumn("dimension_type", lit("country")) \
        .withColumnRenamed("region", "dimension_value")
    
    combined_metrics = device_metrics.union(country_metrics)
    
    if combined_metrics.count() > 0:
        write_to_postgres(combined_metrics, "device_analytics", mode="append")

# Main execution
if __name__ == "__main__":
    # Verify tables exist
    verify_tables()
    
    # Read from Kafka
    kafka_df = spark \
        .readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", "clickstream-events") \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load()
    
    # Parse JSON data
    parsed_df = kafka_df \
        .select(from_json(col("value").cast("string"), clickstream_schema).alias("data")) \
        .select("data.*") \
        .filter(col("userId").isNotNull())
    
    # Start streaming query
    query = parsed_df \
        .writeStream \
        .outputMode("append") \
        .foreachBatch(process_batch) \
        .trigger(processingTime="30 seconds") \
        .start()
    
    logger.info("🚀 Streaming job started successfully!")
    logger.info(f"📊 Processing from {KAFKA_BOOTSTRAP_SERVERS} to {POSTGRES_HOST}")
    
    # Keep running
    query.awaitTermination()

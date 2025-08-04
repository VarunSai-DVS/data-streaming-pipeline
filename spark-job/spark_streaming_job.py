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

# Define schema
clickstream_schema = StructType([
    StructField("user_id", StringType(), True),
    StructField("page_url", StringType(), True),
    StructField("event_type", StringType(), True),
    StructField("timestamp", TimestampType(), True),
    StructField("session_id", StringType(), True),
    StructField("user_agent", StringType(), True),
    StructField("ip_address", StringType(), True),
    StructField("country", StringType(), True),
    StructField("device_type", StringType(), True),
    StructField("referrer", StringType(), True)
])

def create_tables():
    """Create all necessary tables for metrics using JDBC"""
    try:
        # Create tables using Spark SQL and JDBC
        tables_config = [
            {
                "name": "clickstream_events",
                "sql": """
                    CREATE TABLE IF NOT EXISTS clickstream_events (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(50),
                        page_url VARCHAR(500),
                        event_type VARCHAR(50),
                        timestamp TIMESTAMP,
                        session_id VARCHAR(100),
                        user_agent TEXT,
                        ip_address VARCHAR(50),
                        country VARCHAR(50),
                        device_type VARCHAR(50),
                        referrer VARCHAR(500),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
            },
            {
                "name": "realtime_metrics",
                "sql": """
                    CREATE TABLE IF NOT EXISTS realtime_metrics (
                        id SERIAL PRIMARY KEY,
                        metric_timestamp TIMESTAMP,
                        total_events INTEGER,
                        unique_users INTEGER,
                        unique_sessions INTEGER,
                        page_views INTEGER,
                        purchases INTEGER,
                        cart_additions INTEGER,
                        bounce_rate DECIMAL(5,2),
                        avg_session_duration INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
            },
            {
                "name": "page_metrics",
                "sql": """
                    CREATE TABLE IF NOT EXISTS page_metrics (
                        id SERIAL PRIMARY KEY,
                        page_url VARCHAR(500),
                        view_count INTEGER,
                        unique_visitors INTEGER,
                        avg_time_on_page INTEGER,
                        bounce_rate DECIMAL(5,2),
                        conversion_rate DECIMAL(5,2),
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
            },
            {
                "name": "user_behavior",
                "sql": """
                    CREATE TABLE IF NOT EXISTS user_behavior (
                        user_id VARCHAR(50) PRIMARY KEY,
                        total_sessions INTEGER,
                        total_page_views INTEGER,
                        total_purchases INTEGER,
                        avg_session_duration INTEGER,
                        last_active TIMESTAMP,
                        lifetime_value DECIMAL(10,2),
                        churn_risk_score DECIMAL(3,2),
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
            },
            {
                "name": "device_analytics",
                "sql": """
                    CREATE TABLE IF NOT EXISTS device_analytics (
                        id SERIAL PRIMARY KEY,
                        dimension_type VARCHAR(50),
                        dimension_value VARCHAR(100),
                        event_count INTEGER,
                        unique_users INTEGER,
                        conversion_rate DECIMAL(5,2),
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(dimension_type, dimension_value)
                    )
                """
            }
        ]
        
        # Execute table creation using JDBC
        for table_config in tables_config:
            try:
                # Create empty DataFrame to trigger table creation
                empty_df = spark.createDataFrame([], StructType([StructField("dummy", StringType(), True)]))
                empty_df.write \
                    .format("jdbc") \
                    .option("url", f"jdbc:postgresql://{POSTGRES_HOST}:5432/{POSTGRES_DB}") \
                    .option("dbtable", table_config["name"]) \
                    .option("user", POSTGRES_USER) \
                    .option("password", POSTGRES_PASSWORD) \
                    .option("driver", "org.postgresql.Driver") \
                    .mode("ignore") \
                    .save()
                logger.info(f"✅ Table {table_config['name']} ready")
            except Exception as e:
                logger.warning(f"⚠️  Table {table_config['name']} may already exist: {e}")
        
        logger.info("✅ All tables created successfully")
        
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        # Continue anyway - tables might already exist

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
    """Process each micro-batch with multiple analytics using JDBC"""
    
    if df.count() == 0:
        logger.info(f"Empty batch {epoch_id}")
        return
    
    logger.info(f"Processing batch {epoch_id} with {df.count()} records")
    
    try:
        # Cache the DataFrame for multiple operations
        df.cache()
        
        # 1. Store raw events
        store_raw_events(df)
        
        # 2. Calculate real-time metrics
        calculate_realtime_metrics(df)
        
        # 3. Update page metrics
        update_page_metrics(df)
        
        # 4. Update user behavior
        update_user_behavior(df)
        
        # 5. Update device/country analytics
        update_device_analytics(df)
        
        # Unpersist the cached DataFrame
        df.unpersist()
        
        logger.info(f"✅ Successfully processed batch {epoch_id}")
        
    except Exception as e:
        logger.error(f"❌ Error processing batch {epoch_id}: {e}")
        raise

def store_raw_events(df):
    """Store raw clickstream events using JDBC"""
    # Add created_at column
    events_df = df.withColumn("created_at", current_timestamp())
    write_to_postgres(events_df, "clickstream_events")

def calculate_realtime_metrics(df):
    """Calculate real-time metrics for dashboard using JDBC"""
    
    # Calculate metrics
    metrics = df.agg(
        count("*").alias("total_events"),
        countDistinct("user_id").alias("unique_users"),
        countDistinct("session_id").alias("unique_sessions"),
        sum(when(col("event_type") == "page_view", 1).otherwise(0)).alias("page_views"),
        sum(when(col("event_type") == "purchase", 1).otherwise(0)).alias("purchases"),
        sum(when(col("event_type") == "add_to_cart", 1).otherwise(0)).alias("cart_additions")
    ).collect()[0]
    
    # Calculate bounce rate (sessions with only 1 event)
    session_events = df.groupBy("session_id").count()
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
    
    page_metrics = df.filter(col("event_type") == "page_view") \
        .groupBy("page_url") \
        .agg(
            count("*").alias("view_count"),
            countDistinct("user_id").alias("unique_visitors")
        )
    
    if page_metrics.count() > 0:
        write_to_postgres(page_metrics, "page_metrics", mode="overwrite")

def update_user_behavior(df):
    """Update user behavior metrics using JDBC"""
    
    user_metrics = df.groupBy("user_id").agg(
        countDistinct("session_id").alias("sessions"),
        count("*").alias("events"),
        sum(when(col("event_type") == "purchase", 1).otherwise(0)).alias("purchases"),
        max("timestamp").alias("last_active")
    )
    
    if user_metrics.count() > 0:
        write_to_postgres(user_metrics, "user_behavior", mode="overwrite")

def update_device_analytics(df):
    """Update device and country analytics using JDBC"""
    
    # Device analytics
    device_metrics = df.groupBy("device_type").agg(
        count("*").alias("event_count"),
        countDistinct("user_id").alias("unique_users")
    )
    
    # Country analytics
    country_metrics = df.groupBy("country").agg(
        count("*").alias("event_count"),
        countDistinct("user_id").alias("unique_users")
    )
    
    # Combine device and country metrics
    device_metrics = device_metrics.withColumn("dimension_type", lit("device")) \
        .withColumnRenamed("device_type", "dimension_value")
    
    country_metrics = country_metrics.withColumn("dimension_type", lit("country")) \
        .withColumnRenamed("country", "dimension_value")
    
    combined_metrics = device_metrics.union(country_metrics)
    
    if combined_metrics.count() > 0:
        write_to_postgres(combined_metrics, "device_analytics", mode="overwrite")

# Main execution
if __name__ == "__main__":
    # Create tables
    create_tables()
    
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
        .filter(col("user_id").isNotNull())
    
    # Start streaming query
    query = parsed_df \
        .writeStream \
        .outputMode("append") \
        .foreachBatch(process_batch) \
        .trigger(processingTime="10 seconds") \
        .start()
    
    logger.info("🚀 Streaming job started successfully!")
    logger.info(f"📊 Processing from {KAFKA_BOOTSTRAP_SERVERS} to {POSTGRES_HOST}")
    
    # Keep running
    query.awaitTermination()

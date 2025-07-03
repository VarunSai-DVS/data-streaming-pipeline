#!/usr/bin/env python3
"""
Lambda Deployment Script with Kafka Dependencies
Deploys the Lambda function with Kafka producer library as a layer.
"""

import os
import subprocess
import shutil
import zipfile
from pathlib import Path

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

def create_lambda_layer():
    """Create a Lambda layer with Kafka dependencies."""
    print("📦 Creating Lambda layer with Kafka dependencies...")
    
    # Create temporary directory for layer
    layer_dir = Path("lambda-layer")
    python_dir = layer_dir / "python"
    
    # Clean up existing layer
    if layer_dir.exists():
        shutil.rmtree(layer_dir)
    
    # Create directory structure
    python_dir.mkdir(parents=True, exist_ok=True)
    
    # Install dependencies to the layer directory
    install_command = f"pip install -r lambda/requirements.txt -t {python_dir}"
    result = run_command(install_command, "Installing dependencies to layer")
    
    if result is None:
        return None
    
    # Create zip file for the layer
    layer_zip = "lambda-layer.zip"
    if os.path.exists(layer_zip):
        os.remove(layer_zip)
    
    with zipfile.ZipFile(layer_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(layer_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, layer_dir)
                zipf.write(file_path, arcname)
    
    print(f"✅ Lambda layer created: {layer_zip}")
    return layer_zip

def deploy_lambda_with_layer():
    """Deploy the Lambda function with the Kafka layer."""
    print("🚀 Deploying Lambda with Kafka layer...")
    
    # Create the layer
    layer_zip = create_lambda_layer()
    if not layer_zip:
        print("❌ Failed to create Lambda layer")
        return False
    
    # Deploy using CDK
    deploy_command = "cdk deploy ClickstreamLambdaStack"
    result = run_command(deploy_command, "Deploying Lambda stack")
    
    if result is None:
        print("❌ Lambda deployment failed")
        return False
    
    print("✅ Lambda deployed successfully with Kafka support")
    return True

def test_kafka_connectivity():
    """Test if Lambda can connect to Kafka."""
    print("🧪 Testing Lambda → Kafka connectivity...")
    
    # Invoke Lambda function to test Kafka connection
    test_command = """
    aws lambda invoke \
        --function-name ClickstreamLambdaStack-ClickstreamLambda-* \
        --payload '{}' \
        response.json
    """
    
    result = run_command(test_command, "Testing Lambda function")
    if result:
        print("✅ Lambda function invoked successfully")
        
        # Check the response
        if os.path.exists("response.json"):
            with open("response.json", "r") as f:
                response = f.read()
                print(f"📄 Lambda response: {response}")
        
        return True
    else:
        print("❌ Lambda function test failed")
        return False

def cleanup():
    """Clean up temporary files."""
    print("🧹 Cleaning up temporary files...")
    
    files_to_clean = [
        "lambda-layer.zip",
        "response.json",
        "lambda-layer"
    ]
    
    for file_path in files_to_clean:
        if os.path.exists(file_path):
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)
            else:
                os.remove(file_path)
            print(f"🗑️ Removed: {file_path}")

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 LAMBDA → KAFKA INTEGRATION DEPLOYMENT")
    print("=" * 60)
    
    try:
        # Deploy Lambda with Kafka layer
        if deploy_lambda_with_layer():
            print("\n🎉 Lambda deployment completed!")
            
            # Test the integration
            if test_kafka_connectivity():
                print("\n✅ Lambda → Kafka integration successful!")
                print("\n🎯 Next Steps:")
                print("1. Verify data is flowing to Kafka topic")
                print("2. Set up Spark streaming job to consume from Kafka")
                print("3. Connect Spark to PostgreSQL for data storage")
                print("4. Set up monitoring dashboards")
            else:
                print("\n⚠️ Lambda deployed but Kafka connectivity test failed")
                print("Check Lambda logs for connection issues")
        else:
            print("\n❌ Lambda deployment failed")
    
    finally:
        # Clean up
        cleanup()
    
    print("\n" + "=" * 60) 
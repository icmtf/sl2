import os
import time
import math
import redis
import json
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
from jsonschema import validate, ValidationError
from datetime import datetime, timezone

from pyinet.common.config_loader import ConfigLoader

# Initialize OpenTelemetry
resource = Resource.create({"service.name": "s3-worker"})
trace.set_tracer_provider(TracerProvider(resource=resource))
otlp_exporter = OTLPSpanExporter(
    endpoint=os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://jaeger:4317')
)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Instrument botocore
BotocoreInstrumentor().instrument()

tracer = trace.get_tracer(__name__)

# Load environment variables
load_dotenv()

# Load configuration
required_keys = ["S3_ENDPOINT", "S3_BUCKET", "S3_KEY", "S3_SECRET", "S3_BACKUPS_ROOT_DIR"]
config_loader = ConfigLoader(required_keys=required_keys, yaml_path='settings.yaml', env="prd")
config = config_loader.get_config()

# Initialize Redis client
redis_client = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379'))

# S3 Client Config
client_kwargs = {
    'service_name': 's3',
    'endpoint_url': config['S3_ENDPOINT'],
    'aws_access_key_id': config['S3_KEY'],
    'aws_secret_access_key': config['S3_SECRET'],
    'use_ssl': config.get('S3_USE_SSL', False),
    'verify': config.get('S3_VERIFY', False),
    'config': boto3.session.Config(
        signature_version='s3v4',
        s3={'addressing_style': 'path'}
    )
}

# Initialize S3 client
s3_client = boto3.client(**client_kwargs)

def get_s3_file_content(key):
    """Get content of a file from S3 bucket"""
    with tracer.start_as_current_span("get_s3_file_content"):
        try:
            response = s3_client.get_object(Bucket=config['S3_BUCKET'], Key=key)
            return json.loads(response['Body'].read().decode('utf-8'))
        except Exception as e:
            print(f"Error getting file content: {str(e)}")
            return None

def get_s3_backups_data():
    """Get backup data from S3 and process it"""
    with tracer.start_as_current_span("get_s3_backups_data"):
        try:
            response = s3_client.list_objects_v2(
                Bucket=config['S3_BUCKET'],
                Prefix=f"{config['S3_BACKUPS_ROOT_DIR']}/"
            )
            
            backups = {}
            templates = {}
            
            # First, find all template.json files
            for obj in response.get('Contents', []):
                key = obj['Key']
                parts = key.split('/')
                if len(parts) == 4 and parts[-1] == 'template.json':
                    device_class, vendor = parts[1:3]
                    template_data = get_s3_file_content(key)
                    if template_data:
                        templates[f"{device_class}/{vendor}"] = template_data
            
            # Now process backup.json files
            for obj in response.get('Contents', []):
                key = obj['Key']
                parts = key.split('/')
                if len(parts) == 5 and parts[-1] == 'backup.json':
                    device_class, vendor, hostname = parts[1:4]
                    backup_data = get_s3_file_content(key)
                    if backup_data:
                        template_key = f"{device_class}/{vendor}"
                        has_schema = template_key in templates
                        
                        # Add backup_json_data to the backups dictionary
                        backups[hostname] = {
                            'device_class': device_class,
                            'vendor': vendor,
                            'schema': has_schema,
                            'valid_schema': None,
                            'backup_json_data': backup_data
                        }
                        
                        # Validate against template
                        if has_schema:
                            try:
                                validate(instance=backup_data, schema=templates[template_key])
                                backups[hostname]['valid_schema'] = True
                            except ValidationError:
                                backups[hostname]['valid_schema'] = False
            
            return backups
        except ClientError as e:
            print(f"Error in get_s3_backups_data: {str(e)}")
            return {}

def get_s3_validation_and_opstatus_data():
    """Get validation data (operational_status.json and config_validation.json) from S3"""
    with tracer.start_as_current_span("get_s3_validation_and_opstatus_data"):
        try:
            response = s3_client.list_objects_v2(
                Bucket=config['S3_BUCKET'],
                Prefix=f"{config['S3_BACKUPS_ROOT_DIR']}/"
            )
            
            validation_data = {}
            opstatus_data = {}
            
            # Process all files in S3
            for obj in response.get('Contents', []):
                key = obj['Key']
                parts = key.split('/')
                
                # Check if the file is either operational_status.json or config_validation.json
                if len(parts) == 5 and parts[-1] in ['operational_status.json', 'config_validation.json']:
                    device_class, vendor, hostname = parts[1:4]
                    file_type = parts[-1]
                    
                    # Get the file content
                    file_content = get_s3_file_content(key)
                    if file_content:
                        # Initialize device entry if it doesn't exist
                        if hostname not in validation_data:
                            validation_data[hostname] = {
                                'device_class': device_class,
                                'vendor': vendor,
                                'validation_data': {},
                            }
                        if hostname not in opstatus_data:
                            opstatus_data[hostname] = {
                                'device_class': device_class,
                                'vendor': vendor,
                                'operational_status_data': {}
                            }
                        
                        # Add file content to appropriate key and dictionary
                        if file_type == 'config_validation.json':
                            validation_data[hostname]['validation_data'] = file_content
                        elif file_type == 'operational_status.json':
                            opstatus_data[hostname]['operational_status_data'] = file_content
            
            return validation_data, opstatus_data
        except ClientError as e:
            print(f"Error in get_s3_validation_and_opstatus_data: {str(e)}")
            return {}, {}

def store_s3_data_in_redis(data, redis_key_prefix):
    """Store data in Redis with proper key prefixes
    
    Args:
        data (dict): Data to store in Redis
        redis_key_prefix (str): Prefix for Redis keys (e.g., "s3_validation")
    """
    with tracer.start_as_current_span("store_s3_data_in_redis"):
        try:
            pipeline = redis_client.pipeline()
            
            # Clear existing keys with this prefix
            existing_keys = redis_client.keys(f"{redis_key_prefix}:*")
            if existing_keys:
                pipeline.delete(*existing_keys)
            
            # Store new data
            for hostname, device_data in data.items():
                redis_key = f"{redis_key_prefix}:{hostname}"
                if redis_key_prefix == "s3_validation":
                    pipeline.hset(redis_key, mapping={
                        "vendor": device_data["vendor"],
                        "validation_data": json.dumps(device_data["validation_data"])
                    })
                elif redis_key_prefix == "s3_opstatus":
                    pipeline.hset(redis_key, mapping={
                        "vendor": device_data["vendor"],
                        "operational_status_data": json.dumps(device_data["operational_status_data"])
                    })
                else:  # s3_backups
                    pipeline.hset(redis_key, mapping={
                        "vendor": device_data["vendor"],
                        "backup_data": json.dumps(device_data)
                    })
            
            # Execute all commands
            pipeline.execute()
            print(f"Stored {redis_key_prefix} data for {len(data)} devices in Redis")
        except redis.RedisError as e:
            print(f"Error storing {redis_key_prefix} data in Redis: {str(e)}")

def main():
    """Main function - runs continuously and updates backup data"""
    while True:
        with tracer.start_as_current_span("s3_worker_main_loop"):
            s3_backups = get_s3_backups_data()
            s3_validation, s3_opstatus = get_s3_validation_and_opstatus_data()
            
            store_s3_data_in_redis(s3_backups, "s3_backups")
            store_s3_data_in_redis(s3_validation, "s3_validation")
            store_s3_data_in_redis(s3_opstatus, "s3_opstatus")
            
            time.sleep(600)  # Run every 10 minutes

if __name__ == "__main__":
    main()
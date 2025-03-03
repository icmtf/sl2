import os
import time
import math
import redis
import json
import boto3
import csv
import logging
from io import StringIO
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
from jsonschema import validate, ValidationError
import traceback
import sys
from datetime import datetime, timezone
import re

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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Configure specific loggers
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('s3transfer').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# Create logger for this module
logger = logging.getLogger('s3_worker')

# Load environment variables
load_dotenv()

# Load configuration
required_keys = [
    "S3_ENDPOINT", "S3_BUCKET", "S3_KEY", "S3_SECRET", 
    "S3_BACKUPS_ROOT_DIR", "S3_REMOTE_ACCESS_ROOT_DIR",
    "S3_REMOTE_ACCESS_FILE_NAME", "S3_ARP_ROOT_DIR",
    "S3_ARP_FILE_NAME"
]
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
            logger.debug(f"Fetching content from S3: {key}")
            response = s3_client.get_object(Bucket=config['S3_BUCKET'], Key=key)
            content = response['Body'].read().decode('utf-8')
            parsed_content = json.loads(content)
            logger.debug(f"Successfully parsed content from: {key}")
            return parsed_content
        except Exception as e:
            logger.error(f"Error getting file content from {key}: {str(e)}")
            logger.error(traceback.format_exc())
            return None

def get_s3_backups_data():
    """Get backup data from S3 and process it"""
    with tracer.start_as_current_span("get_s3_backups_data"):
        try:
            response = s3_client.list_objects_v2(
                Bucket=config['S3_BUCKET'],
                Prefix=f"{config['S3_BACKUPS_ROOT_DIR']}/"
            )
            
            logger.info(f"Looking for templates in {config['S3_BACKUPS_ROOT_DIR']}/")
            logger.info(f"Found {len(response.get('Contents', []))} objects")
            
            backups = {}
            templates = {}
            
            # First, find all template.json files
            for obj in response.get('Contents', []):
                key = obj['Key']
                logger.info(f"Processing S3 object: {key}")
                parts = key.split('/')
                if len(parts) == 4 and parts[-1] == 'template.json':
                    device_class, vendor = parts[1:3]
                    logger.info(f"Found template.json for {device_class}/{vendor}")
                    template_data = get_s3_file_content(key)
                    if template_data:
                        templates[f"{device_class}/{vendor}"] = template_data
                        logger.info(f"Successfully loaded template for {device_class}/{vendor}")
            
            # Dodaj ręcznie szablon dla Firewall/Fortinet
            try:
                fortinet_template_key = "inetportalNG/Firewall/Fortinet/template.json"
                logger.info(f"Próba ręcznego załadowania szablonu: {fortinet_template_key}")
                fortinet_template = get_s3_file_content(fortinet_template_key)
                if fortinet_template:
                    templates["Firewall/Fortinet"] = fortinet_template
                    logger.info(f"Ręcznie załadowano szablon dla Firewall/Fortinet")
            except Exception as e:
                logger.error(f"Błąd podczas ręcznego ładowania szablonu: {str(e)}")
                logger.error(traceback.format_exc())
            
            logger.info(f"Found and loaded {len(templates)} templates: {list(templates.keys())}")
            
            # Now process backup.json files
            for obj in response.get('Contents', []):
                key = obj['Key']
                parts = key.split('/')
                if len(parts) == 5 and parts[-1] == 'backup.json':
                    device_class, vendor, hostname = parts[1:4]
                    logger.info(f"Processing backup.json for {hostname}, device_class={device_class}, vendor={vendor}")
                    backup_data = get_s3_file_content(key)
                    if backup_data:
                        template_key = f"{device_class}/{vendor}"
                        has_schema = template_key in templates
                        logger.info(f"Template key: {template_key}, has_schema: {has_schema}")
                        
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
                                logger.info(f"Validating backup.json for {hostname} against schema for {device_class}/{vendor}")
                                validate(instance=backup_data, schema=templates[template_key])
                                backups[hostname]['valid_schema'] = True
                                logger.info(f"Validation SUCCESS for {hostname}")
                            except ValidationError as ve:
                                backups[hostname]['valid_schema'] = False
                                # Log validation error details
                                logger.error(f"Validation FAILED for {hostname}:")
                                logger.error(f"  - Error message: {str(ve)}")
                                logger.error(f"  - JSON path: {' -> '.join([str(p) for p in ve.path])}")
                                logger.error(f"  - Schema path: {' -> '.join([str(p) for p in ve.schema_path])}")
                                logger.error(f"  - Schema: {json.dumps(ve.schema, indent=2)}")
                                logger.error(f"  - Instance: {json.dumps(ve.instance, indent=2)}")
                                
                                # Log backup.json and template.json for comparison
                                logger.info(f"Template JSON for {device_class}/{vendor}:\n{json.dumps(templates[template_key], indent=2)}")
                                logger.info(f"Backup JSON for {hostname}:\n{json.dumps(backup_data, indent=2)}")
            
            return backups
        except ClientError as e:
            logger.error(f"Error in get_s3_backups_data: {str(e)}")
            logger.error(traceback.format_exc())
            return {}

def get_s3_validation_and_opstatus_data():
    """Get validation data from S3"""
    with tracer.start_as_current_span("get_s3_validation_and_opstatus_data"):
        try:
            response = s3_client.list_objects_v2(
                Bucket=config['S3_BUCKET'],
                Prefix=f"{config['S3_BACKUPS_ROOT_DIR']}/"
            )
            
            validation_data = {}
            opstatus_data = []
            
            for obj in response.get('Contents', []):
                key = obj['Key']
                parts = key.split('/')
                
                if len(parts) == 5 and parts[-1] in ['operational_status.json', 'config_validation.json']:
                    device_class, vendor, hostname = parts[1:4]
                    file_type = parts[-1]
                    
                    file_content = get_s3_file_content(key)
                    if file_content:
                        if hostname not in validation_data:
                            validation_data[hostname] = {
                                'device_class': device_class,
                                'vendor': vendor,
                                'validation_data': {},
                            }
                        
                        if file_type == 'config_validation.json':
                            validation_data[hostname]['validation_data'] = file_content
                        elif file_type == 'operational_status.json':
                            opstatus_data.append(file_content)
            
            return validation_data, opstatus_data
        except ClientError as e:
            print(f"Error in get_s3_validation_and_opstatus_data: {str(e)}")
            return {}, []

def get_remote_access_data():
    """Get remote access data from S3 and store it in Redis"""
    with tracer.start_as_current_span("get_remote_access_data"):
        try:
            key = f"{config['S3_REMOTE_ACCESS_ROOT_DIR']}/{config['S3_REMOTE_ACCESS_FILE_NAME']}"
            
            response = s3_client.get_object(Bucket=config['S3_BUCKET'], Key=key)
            csv_content = response['Body'].read().decode('utf-8')
            
            csv_file = StringIO(csv_content)
            csv_reader = csv.DictReader(csv_file)
            records = list(csv_reader)
            
            redis_client.set("remote_access_data", json.dumps(records))
            print(f"Processed {len(records)} records from remote access CSV")
            
            return True
        except Exception as e:
            print(f"Error processing remote access data: {str(e)}")
            return False

def get_arp_data():
    """Get ARP data from S3 and store it in Redis"""
    with tracer.start_as_current_span("get_arp_data"):
        try:
            key = f"{config['S3_ARP_ROOT_DIR']}/{config['S3_ARP_FILE_NAME']}"
            
            response = s3_client.get_object(Bucket=config['S3_BUCKET'], Key=key)
            content = response['Body'].read().decode('utf-8')
            
            arp_entries = []
            current_device = None
            
            for line in content.split('\n'):
                line = line.strip()
                
                # Skip empty lines - they mark the end of ARP entries for current device
                if not line:
                    current_device = None
                    continue
                    
                # Ignore lines with asterisks
                if '*' in line:
                    continue
                    
                # Check if this is a line with device name
                if line.startswith('#'):
                    device_match = re.match(r'#+([^#]+)#+$', line)
                    if device_match:
                        current_device = device_match.group(1).strip()
                    continue
                
                # If we have a device, try to parse ARP entry
                if current_device:
                    arp_match = re.match(r'(\S+)\s+is\s+at\s+(\S+)\s+on\s+(.+)$', line)
                    if arp_match:
                        arp_entries.append({
                            'device': current_device,
                            'first_address': arp_match.group(1),
                            'second_address': arp_match.group(2),
                            'interface': arp_match.group(3).strip()
                        })
            
            # Save to Redis
            redis_client.set("arp_data", json.dumps(arp_entries))
            print(f"Processed {len(arp_entries)} ARP entries")
            
            return True
        except Exception as e:
            print(f"Error processing ARP data: {str(e)}")
            return False

def store_s3_data_in_redis(data, redis_key_prefix):
    """Store data in Redis with proper key prefixes"""
    with tracer.start_as_current_span("store_s3_data_in_redis"):
        try:
            logger.info(f"Storing {redis_key_prefix} data in Redis, {len(data)} items")
            
            if redis_key_prefix == "s3_opstatus":
                redis_client.set(redis_key_prefix, json.dumps(data))
                logger.info(f"Stored operational status data in Redis")
                return

            pipeline = redis_client.pipeline()
            
            existing_keys = redis_client.keys(f"{redis_key_prefix}:*")
            if existing_keys:
                logger.info(f"Deleting {len(existing_keys)} existing keys with prefix {redis_key_prefix}")
                pipeline.delete(*existing_keys)
            
            for hostname, device_data in data.items():
                redis_key = f"{redis_key_prefix}:{hostname}"
                logger.debug(f"Preparing Redis data for {redis_key}")
                
                if redis_key_prefix == "s3_validation":
                    pipeline.hset(redis_key, mapping={
                        "vendor": device_data["vendor"],
                        "validation_data": json.dumps(device_data["validation_data"])
                    })
                else:  # s3_backups
                    # Log validation status for each device
                    has_schema = device_data.get('schema', False)
                    valid_schema = device_data.get('valid_schema', None)
                    logger.info(f"Device {hostname}: has_schema={has_schema}, valid_schema={valid_schema}")
                    
                    pipeline.hset(redis_key, mapping={
                        "vendor": device_data["vendor"],
                        "backup_data": json.dumps(device_data)
                    })
            
            pipeline.execute()
            logger.info(f"Successfully stored {redis_key_prefix} data for {len(data)} devices in Redis")
        except redis.RedisError as e:
            logger.error(f"Error storing {redis_key_prefix} data in Redis: {str(e)}")
            logger.error(traceback.format_exc())

def main():
    """Main function - runs continuously and updates data"""
    while True:
        with tracer.start_as_current_span("s3_worker_main_loop"):
            logger.info("===== Starting S3 worker data refresh cycle =====")
            
            # Get and store backups data
            logger.info("Fetching backup data from S3")
            s3_backups = get_s3_backups_data()
            logger.info(f"Retrieved backup data for {len(s3_backups)} devices")
            store_s3_data_in_redis(s3_backups, "s3_backups")
            
            # Get and store validation and operational status data
            logger.info("Fetching validation and operational status data from S3")
            s3_validation, s3_opstatus = get_s3_validation_and_opstatus_data()
            logger.info(f"Retrieved validation data for {len(s3_validation)} devices")
            store_s3_data_in_redis(s3_validation, "s3_validation")
            store_s3_data_in_redis(s3_opstatus, "s3_opstatus")
            
            # Get remote access data
            logger.info("Fetching remote access data from S3")
            get_remote_access_data()
            
            # Get ARP data
            logger.info("Fetching ARP data from S3")
            get_arp_data()
            
            logger.info("===== Completed S3 worker data refresh cycle =====")
            logger.info(f"Next update in 10 minutes")
            
            # Wait 10 minutes before next iteration
            time.sleep(600)

def run_once(target_hostname=None):
    """Run the worker once for testing purposes"""
    logger.info("===== Starting S3 worker single run for testing =====")
    
    # Get and store backups data
    logger.info("Fetching backup data from S3")
    s3_backups = get_s3_backups_data()
    logger.info(f"Retrieved backup data for {len(s3_backups)} devices")
    
    # If a target hostname is specified, print detailed information for that device
    if target_hostname and target_hostname in s3_backups:
        device_data = s3_backups[target_hostname]
        logger.info(f"\n\n==== DETAILED INFO FOR {target_hostname} ====\n")
        logger.info(f"Device Class: {device_data.get('device_class')}")
        logger.info(f"Vendor: {device_data.get('vendor')}")
        logger.info(f"Has Schema: {device_data.get('schema')}")
        logger.info(f"Valid Schema: {device_data.get('valid_schema')}")
        
        # If backup_json_data exists, show its vendor and other details
        backup_json = device_data.get('backup_json_data', {})
        logger.info(f"\nBackup JSON Data:")
        logger.info(f"  - Hostname: {backup_json.get('hostname')}")
        logger.info(f"  - Vendor in backup_json: {backup_json.get('vendor')}")
        
        # Check for vendor mismatch
        if device_data.get('vendor') != backup_json.get('vendor'):
            logger.warning(f"VENDOR MISMATCH: {device_data.get('vendor')} (metadata) vs {backup_json.get('vendor')} (backup.json)")
    
    store_s3_data_in_redis(s3_backups, "s3_backups")
    
    logger.info("===== Completed S3 worker test run =====")

if __name__ == "__main__":
    # Use run_once() for testing or main() for normal operation
    # Specify a hostname to analyze a specific device or leave empty for all devices
    run_once("frpa3-man-ppfw-fg02")
    # main()
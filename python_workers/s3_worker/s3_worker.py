import os
import time
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
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('s3transfer').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

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
            response = s3_client.get_object(Bucket=config['S3_BUCKET'], Key=key)
            return json.loads(response['Body'].read().decode('utf-8'))
        except Exception as e:
            print(f"Error getting file content: {str(e)}")
            return None

def get_s3_backups_data():
    """Get backup data from S3 and process it"""
    with tracer.start_as_current_span("get_s3_backups_data"):
        try:
            # Use paginator instead of a single list_objects_v2 call
            paginator = s3_client.get_paginator('list_objects_v2')
            
            backups = {}
            templates = {}
            
            # First, find all template.json files using pagination
            template_pages = paginator.paginate(
                Bucket=config['S3_BUCKET'],
                Prefix=f"{config['S3_BACKUPS_ROOT_DIR']}/"
            )
            
            for page in template_pages:
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    parts = key.split('/')
                    if len(parts) == 4 and parts[-1] == 'template.json':
                        device_class, vendor = parts[1:3]
                        template_data = get_s3_file_content(key)
                        if template_data:
                            templates[f"{device_class}/{vendor}"] = template_data
            
            # Now process backup.json files using pagination again
            backup_pages = paginator.paginate(
                Bucket=config['S3_BUCKET'],
                Prefix=f"{config['S3_BACKUPS_ROOT_DIR']}/"
            )
            
            for page in backup_pages:
                for obj in page.get('Contents', []):
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
    """Get validation data from S3"""
    with tracer.start_as_current_span("get_s3_validation_and_opstatus_data"):
        try:
            # Use paginator instead of a single list_objects_v2 call
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=config['S3_BUCKET'],
                Prefix=f"{config['S3_BACKUPS_ROOT_DIR']}/"
            )
            
            validation_data = {}
            opstatus_data = []
            
            for page in pages:
                for obj in page.get('Contents', []):
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

def store_unified_device_data(data_type, data):
    """Store data in a unified structure under device:hostname keys"""
    with tracer.start_as_current_span(f"store_unified_{data_type}_data"):
        try:
            pipeline = redis_client.pipeline()
            
            # Depending on the data type, we process it in the appropriate way
            if data_type == "backup_data":
                # For backup_data, we have a mapping hostname -> data
                for hostname, backup_info in data.items():
                    # Get existing device data, if it exists
                    device_key = f"device:{hostname}"
                    device_data = redis_client.get(device_key)
                    
                    if device_data:
                        try:
                            # Parse existing data
                            device_json = json.loads(device_data)
                            
                            # Ensure we're dealing with a dictionary
                            if not isinstance(device_json, dict):
                                device_json = {}
                                
                            # Add backup data without touching other sections
                            device_json["backup_data"] = backup_info
                            
                            # Save updated data
                            pipeline.set(device_key, json.dumps(device_json))
                        except json.JSONDecodeError:
                            # If existing data is corrupt, create a new structure
                            new_device = {"backup_data": backup_info}
                            pipeline.set(device_key, json.dumps(new_device))
                    else:
                        # If the device doesn't exist, create a new entry
                        new_device = {"backup_data": backup_info}
                        pipeline.set(device_key, json.dumps(new_device))
            
            elif data_type == "validation":
                # For validation, we have a mapping hostname -> data
                for hostname, validation_info in data.items():
                    device_key = f"device:{hostname}"
                    device_data = redis_client.get(device_key)
                    
                    if device_data:
                        try:
                            # Parse existing data
                            device_json = json.loads(device_data)
                            
                            # Ensure we're dealing with a dictionary
                            if not isinstance(device_json, dict):
                                device_json = {}
                                
                            # Add validation data without nested structures
                            device_json["validation"] = validation_info
                            
                            # Save updated data
                            pipeline.set(device_key, json.dumps(device_json))
                        except json.JSONDecodeError:
                            # If existing data is corrupt, create a new structure
                            new_device = {"validation": validation_info}
                            pipeline.set(device_key, json.dumps(new_device))
                    else:
                        new_device = {"validation": validation_info}
                        pipeline.set(device_key, json.dumps(new_device))
            
            elif data_type == "opstatus":
                # For opstatus, we have a list of devices
                for status_entry in data:
                    hostname = status_entry.get("hostname")
                    if hostname:
                        device_key = f"device:{hostname}"
                        device_data = redis_client.get(device_key)
                        
                        if device_data:
                            try:
                                # Parse existing data
                                device_json = json.loads(device_data)
                                
                                # Ensure we're dealing with a dictionary
                                if not isinstance(device_json, dict):
                                    device_json = {}
                                    
                                # Add operational status data
                                device_json["opstatus"] = status_entry
                                
                                # Save updated data
                                pipeline.set(device_key, json.dumps(device_json))
                            except json.JSONDecodeError:
                                # If existing data is corrupt, create a new structure
                                new_device = {"opstatus": status_entry}
                                pipeline.set(device_key, json.dumps(new_device))
                        else:
                            new_device = {"opstatus": status_entry}
                            pipeline.set(device_key, json.dumps(new_device))
            
            # Execute all operations in a single transaction
            pipeline.execute()
            print(f"Stored unified {data_type} data in Redis")
            
        except redis.RedisError as e:
            print(f"Error storing unified {data_type} data in Redis: {str(e)}")

def repair_existing_data_structure():
    """Fix existing data structure in Redis to match the expected format"""
    with tracer.start_as_current_span("repair_existing_data_structure"):
        try:
            # Get all device keys
            device_keys = redis_client.keys("device:*")
            fixed_count = 0
            
            for key in device_keys:
                device_data = redis_client.get(key)
                if device_data:
                    try:
                        device_json = json.loads(device_data)
                        
                        # Check if we need to repair the data structure
                        needs_repair = False
                        
                        # Case 1: easynet contains a nested easynet structure
                        if "easynet" in device_json and isinstance(device_json["easynet"], dict):
                            if "easynet" in device_json["easynet"]:
                                needs_repair = True
                                
                                # Try to extract useful data from the nested structure
                                nested_easynet = device_json["easynet"].get("easynet", {})
                                
                                # If nested_easynet contains validation data, move it to the validation section
                                if "validation" in nested_easynet and isinstance(nested_easynet["validation"], dict):
                                    # Preserve existing validation data if it exists
                                    if "validation" not in device_json:
                                        device_json["validation"] = nested_easynet["validation"]
                                
                                # Clear the corrupted easynet section
                                # We'll need to wait for EasyNet Worker to fill it with proper data
                                device_json["easynet"] = {}
                        
                        # Case 2: ValidationData is inside easynet but should be in validation
                        if "easynet" in device_json and isinstance(device_json["easynet"], dict):
                            if "validation" in device_json["easynet"] and isinstance(device_json["easynet"]["validation"], dict):
                                needs_repair = True
                                
                                # Move validation data to the correct section
                                if "validation" not in device_json:
                                    device_json["validation"] = device_json["easynet"]["validation"]
                                
                                # Remove validation data from easynet section
                                del device_json["easynet"]["validation"]
                        
                        # Save the fixed data if repairs were made
                        if needs_repair:
                            redis_client.set(key, json.dumps(device_json))
                            fixed_count += 1
                            
                    except json.JSONDecodeError:
                        # If data is corrupted, we can't repair it
                        pass
            
            print(f"Repaired {fixed_count} out of {len(device_keys)} device records in Redis")
            
        except redis.RedisError as e:
            print(f"Error repairing data structure in Redis: {str(e)}")

def debug_s3_paths():
    """Funkcja diagnostyczna do debugowania ścieżek S3"""
    print("\n=== DIAGNOSTYKA ŚCIEŻEK S3 ===")
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(
            Bucket=config['S3_BUCKET'],
            Prefix=f"{config['S3_BACKUPS_ROOT_DIR']}/"
        )
        
        all_paths = []
        for page in pages:
            if 'Contents' in page:
                all_paths.extend([obj['Key'] for obj in page['Contents']])
        
        print(f"Znaleziono {len(all_paths)} obiektów w ścieżce: {config['S3_BACKUPS_ROOT_DIR']}/")
        print("\nPrzykładowe ścieżki:")
        for path in all_paths[:10]:
            print(f"- {path}")
            
        backup_files = [p for p in all_paths if p.endswith('backup.json')]
        print(f"\nZnaleziono {len(backup_files)} plików backup.json")
        
        path_structures = {}
        for path in backup_files[:20]:
            parts = path.split('/')
            parts_count = len(parts)
            if parts_count not in path_structures:
                path_structures[parts_count] = []
            path_structures[parts_count].append(path)
        
        print("\nStruktura ścieżek plików backup.json:")
        for parts_count, paths in path_structures.items():
            print(f"\n{parts_count} części w ścieżce ({len(paths)} plików):")
            for path in paths[:3]:
                parts = path.split('/')
                print(f"- {path}")
                print(f"  Części: {parts}")
        
        print("\n=== URZĄDZENIA W REDIS ===")
        device_keys = redis_client.keys("device:*")
        print(f"Znaleziono {len(device_keys)} urządzeń w Redis")
        
        for key in device_keys[:5]:
            hostname = key.decode().split(':')[1]
            device_data = redis_client.get(key)
            if device_data:
                device_json = json.loads(device_data)
                easynet = device_json.get("easynet", {})
                device_class = easynet.get("device_class")
                vendor = easynet.get("vendor")
                
                expected_path = f"{config['S3_BACKUPS_ROOT_DIR']}/{device_class}/{vendor}/{hostname}/backup.json"
                exists = expected_path in all_paths
                
                print(f"\nUrządzenie: {hostname}")
                print(f"- device_class: {device_class}")
                print(f"- vendor: {vendor}")
                print(f"- Oczekiwana ścieżka: {expected_path}")
                print(f"- Ścieżka istnieje: {exists}")
                
                alt_paths = [p for p in all_paths if f"/{hostname}/" in p and p.endswith('backup.json')]
                if alt_paths:
                    print(f"- Znaleziono alternatywne ścieżki ({len(alt_paths)}):")
                    for p in alt_paths:
                        print(f"  * {p}")
    except Exception as e:
        print(f"Błąd diagnostyki: {str(e)}")
        import traceback
        print(traceback.format_exc())
    print("=== KONIEC DIAGNOSTYKI ===\n")

def main():
    """Main function - runs continuously and updates data"""
    # Wykonaj diagnostykę
    debug_s3_paths()
    
    # At the beginning, repair any corrupted data structure
    repair_existing_data_structure()
    
    while True:
        with tracer.start_as_current_span("s3_worker_main_loop"):
            # Get and store backups data
            s3_backups = get_s3_backups_data()
            store_unified_device_data("backup_data", s3_backups)
            
            # Get and store validation and operational status data
            s3_validation, s3_opstatus = get_s3_validation_and_opstatus_data()
            store_unified_device_data("validation", s3_validation)
            store_unified_device_data("opstatus", s3_opstatus)
            
            # Get remote access data
            get_remote_access_data()
            
            # Get ARP data
            get_arp_data()
            
            # Wait 10 minutes before next iteration
            time.sleep(600)

if __name__ == "__main__":
    main()
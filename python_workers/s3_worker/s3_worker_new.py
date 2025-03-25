import os
import time
import redis
import json
import boto3
import logging
import traceback
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.botocore import BotocoreInstrumentor

from pyinet.common.config_loader import ConfigLoader

# Konfiguracja loggera
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("s3_worker_new")

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

def test_redis_connection():
    """Test Redis connection and verify operations"""
    try:
        # Testowy zapis i odczyt
        test_key = "test:s3worker:connection"
        test_value = {"timestamp": time.time(), "status": "ok", "test": True}
        
        # Zapisz testowe dane
        logger.info(f"Testing Redis connection by writing to {test_key}")
        redis_client.set(test_key, json.dumps(test_value))
        
        # Odczytaj testowe dane
        read_value = redis_client.get(test_key)
        if read_value:
            parsed_value = json.loads(read_value)
            logger.info(f"Successfully read test data from Redis: {parsed_value}")
            
            # Dodatkowa weryfikacja klucza test
            if parsed_value.get("test") == True:
                logger.info("Redis write/read test passed!")
                return True
            else:
                logger.warning("Redis test value has unexpected content")
        else:
            logger.error("Failed to read test value from Redis!")
    except Exception as e:
        logger.error(f"Redis connection test failed: {str(e)}")
        logger.error(traceback.format_exc())
    return False

def get_devices_from_redis():
    """Get all devices from Redis"""
    with tracer.start_as_current_span("get_devices_from_redis"):
        try:
            devices = {}
            # Get all device keys
            device_keys = redis_client.keys("device:*")
            
            for key in device_keys:
                device_data = redis_client.get(key)
                if device_data:
                    try:
                        device_json = json.loads(device_data)
                        hostname = key.decode().split(':')[1]
                        devices[hostname] = device_json
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse data for {key.decode()}")
            
            return devices
        except redis.RedisError as e:
            logger.error(f"Redis error: {str(e)}")
            return {}

def list_files_in_s3():
    """List all files in S3 bucket under the given prefix"""
    with tracer.start_as_current_span("list_files_in_s3"):
        try:
            # Use paginator to handle large number of files
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=config['S3_BUCKET'],
                Prefix=f"{config['S3_BACKUPS_ROOT_DIR']}/"
            )
            
            all_files = []
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        all_files.append(obj['Key'])
            
            logger.info(f"Found {len(all_files)} files in S3 bucket under prefix {config['S3_BACKUPS_ROOT_DIR']}/")
            
            # Pogrupuj pliki według typów
            backup_files = [f for f in all_files if f.endswith('/backup.json')]
            template_files = [f for f in all_files if f.endswith('/template.json')]
            opstatus_files = [f for f in all_files if f.endswith('/operational_status.json')]
            validation_files = [f for f in all_files if f.endswith('/config_validation.json')]
            
            logger.info(f"Files breakdown:")
            logger.info(f"  - backup.json files: {len(backup_files)}")
            logger.info(f"  - template.json files: {len(template_files)}")
            logger.info(f"  - operational_status.json files: {len(opstatus_files)}")
            logger.info(f"  - config_validation.json files: {len(validation_files)}")
            
            # Log first 5 files of each type as examples
            logger.info("Sample backup.json files:")
            for file_path in backup_files[:5]:
                logger.info(f"  - {file_path}")
            
            logger.info("Sample template.json files:")
            for file_path in template_files[:5]:
                logger.info(f"  - {file_path}")
            
            return {
                'all_files': all_files,
                'backup_files': backup_files,
                'template_files': template_files,
                'opstatus_files': opstatus_files,
                'validation_files': validation_files
            }
        except Exception as e:
            logger.error(f"Error listing files in S3: {str(e)}")
            return {
                'all_files': [],
                'backup_files': [],
                'template_files': [],
                'opstatus_files': [],
                'validation_files': []
            }

def get_file_content(file_path):
    """Get content of a file from S3 bucket"""
    with tracer.start_as_current_span("get_file_content"):
        try:
            response = s3_client.get_object(Bucket=config['S3_BUCKET'], Key=file_path)
            content = response['Body'].read().decode('utf-8')
            try:
                data = json.loads(content)
                return data
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error for {file_path}: {str(e)}")
                logger.error(f"Content preview: {content[:100]}...")
                return {}
        except Exception as e:
            logger.error(f"Error getting file content for {file_path}: {str(e)}")
            return {}

def process_device_files(devices, s3_files):
    """Process device files and update Redis"""
    with tracer.start_as_current_span("process_device_files"):
        logger.info("Processing device files and updating Redis...")
        files_processed = 0
        devices_updated = 0
        devices_with_missing_files = 0

        all_files_set = set(s3_files['all_files'])
        
        # Iterate through each device in Redis
        for hostname, device_data in devices.items():
            easynet_data = device_data.get('easynet', {})
            device_class = easynet_data.get('device_class')
            vendor = easynet_data.get('vendor')
            
            # Skip if required data is missing
            if not device_class or not vendor or not hostname:
                logger.warning(f"[{hostname}] is missing required data in EasyNet used to locate S3 files (device_class={device_class}, vendor={vendor}). Will be ignored.")
                continue
            
            # Build expected paths
            base_path = f"{config['S3_BACKUPS_ROOT_DIR']}/{device_class}/{vendor}"
            template_path = f"{base_path}/template.json"
            backup_path = f"{base_path}/{hostname}/backup.json"
            config_validation_path = f"{base_path}/{hostname}/config_validation.json"
            operational_status_path = f"{base_path}/{hostname}/operational_status.json"
            
            # Check if files exist and update Redis
            updated_data = device_data.copy()
            missing_files = []
            
            # Check backup.json
            if backup_path in all_files_set:
                logger.info(f"Found backup.json for {hostname}")
                backup_data = get_file_content(backup_path)
                if backup_data:
                    updated_data['backup'] = backup_data
                    logger.info(f"Backup data loaded for {hostname}")
                else:
                    logger.warning(f"Backup data empty for {hostname} despite file existing at {backup_path}")
                    updated_data['backup'] = {}
                files_processed += 1
            else:
                logger.warning(f"[{hostname}] backup.json missing at expected: {backup_path}")
                updated_data['backup'] = {}
                missing_files.append('backup.json')
            
            # Check config_validation.json
            if config_validation_path in all_files_set:
                logger.info(f"Found config_validation.json for {hostname}")
                config_validation_data = get_file_content(config_validation_path)
                if config_validation_data:
                    updated_data['config_validation'] = config_validation_data
                    logger.info(f"Config validation data loaded for {hostname}")
                else:
                    logger.warning(f"Config validation data empty for {hostname} despite file existing at {config_validation_path}")
                    updated_data['config_validation'] = {}
                files_processed += 1
            else:
                logger.warning(f"[{hostname}] config_validation.json missing at expected: {config_validation_path}")
                updated_data['config_validation'] = {}
                missing_files.append('config_validation.json')
            
            # Check operational_status.json
            if operational_status_path in all_files_set:
                logger.info(f"Found operational_status.json for {hostname}")
                operational_status_data = get_file_content(operational_status_path)
                if operational_status_data:
                    updated_data['operational_status'] = operational_status_data
                    logger.info(f"Operational status data loaded for {hostname}")
                else:
                    logger.warning(f"Operational status data empty for {hostname} despite file existing at {operational_status_path}")
                    updated_data['operational_status'] = {}
                files_processed += 1
            else:
                logger.warning(f"[{hostname}] operational_status.json missing at expected: {operational_status_path}")
                updated_data['operational_status'] = {}
                missing_files.append('operational_status.json')
            
            # Update Redis - bezpieczna aktualizacja z blokadą
            redis_key = f"device:{hostname}"
            try:
                # Implementujemy atomową aktualizację - pobieramy najnowsze dane, dodajemy nasze klucze, zapisujemy z powrotem
                pipe = redis_client.pipeline()
                
                # Pobierz aktualne dane - to zapewni, że nie nadpiszemy danych, które mogły zostać zmienione przez inny proces
                current_data = redis_client.get(redis_key)
                if current_data:
                    current_json = json.loads(current_data)
                    
                    # Zaktualizuj klucze, które chcemy dodać, zachowując inne klucze
                    for k in ['backup', 'config_validation', 'operational_status']:
                        if k in updated_data:
                            current_json[k] = updated_data[k]
                    
                    # Zapisz zaktualizowane dane
                    pipe.set(redis_key, json.dumps(current_json))
                    pipe.execute()
                else:
                    # Nie znaleziono danych - zapisz nasze dane
                    pipe.set(redis_key, json.dumps(updated_data))
                    pipe.execute()
                
                # Określamy, które konkretnie dane zostały dodane
                added_data_types = []
                for k in ['backup', 'config_validation', 'operational_status']:
                    if k in updated_data and updated_data[k] and updated_data[k] != {}: 
                        added_data_types.append(k)
                        
                if added_data_types:
                    logger.info(f"Updated Redis entry for {hostname} with {', '.join(added_data_types)}")
                else:
                    logger.info(f"Updated Redis entry for {hostname} with empty keys")
                    
                devices_updated += 1
            except Exception as e:
                logger.error(f"Failed to update Redis for {hostname}: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Log missing files
            if missing_files:
                devices_with_missing_files += 1
        
        logger.info(f"Updated {devices_updated} devices in Redis")
        logger.info(f"Processed {files_processed} files in total")
        logger.info(f"{devices_with_missing_files} devices have missing files")

def main():
    """Main function"""
    logger.info("S3 Worker starting...")
    
    # Test połączenia z Redis
    logger.info("Testing Redis connection...")
    redis_test = test_redis_connection()
    if not redis_test:
        logger.error("Redis connection test failed. Check Redis configuration.")
    
    # Opóźnienie startu o 5 sekund
    logger.info("Waiting 5 seconds before starting...")
    time.sleep(5)
    
    # Pobierz dane urządzeń z Redis
    devices = get_devices_from_redis()
    logger.info(f"Retrieved {len(devices)} devices from Redis")
    
    # Listuj pliki w S3
    s3_files = list_files_in_s3()
    
    # Przetwórz pliki urządzeń i zaktualizuj Redis
    process_device_files(devices, s3_files)

if __name__ == "__main__":
    main()
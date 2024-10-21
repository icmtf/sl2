import os
import time
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
    with tracer.start_as_current_span("get_s3_file_content"):
        try:
            response = s3_client.get_object(Bucket=config['S3_BUCKET'], Key=key)
            return json.loads(response['Body'].read().decode('utf-8'))
        except Exception as e:
            return None

def get_s3_backups_data():
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
                        backups[hostname] = {
                            'device_class': device_class,
                            'vendor': vendor,
                            'has_backup': True,
                            'backup.json_s3_date': obj['LastModified'].isoformat(),
                            'backup_data': backup_data,
                            'schema': has_schema,
                            'valid_schema': None
                        }
                        
                        # Validate against template
                        if has_schema:
                            try:
                                validate(instance=backup_data, schema=templates[template_key])
                                backups[hostname]['valid_schema'] = True
                            except ValidationError:
                                backups[hostname]['valid_schema'] = False
            
            return backups
        except ClientError:
            return {}

def store_s3_data_in_redis(s3_backups):
    with tracer.start_as_current_span("store_s3_data_in_redis"):
        try:
            redis_client.set("s3_backups", json.dumps(s3_backups))
        except redis.RedisError:
            pass

def main():
    while True:
        with tracer.start_as_current_span("s3_worker_main_loop"):
            s3_backups = get_s3_backups_data()
            store_s3_data_in_redis(s3_backups)
            time.sleep(600)  # Run every 10 minutes

if __name__ == "__main__":
    main()

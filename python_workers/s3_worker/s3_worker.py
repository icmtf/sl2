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

from pyinet.common.config_loader import ConfigLoader
from pyinet.common.easynet import EasyNet

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
required_keys = ["S3_ENDPOINT", "S3_BUCKET", "S3_KEY", "S3_SECRET"]
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

def get_s3_backups_list():
    with tracer.start_as_current_span("get_s3_backups_list"):
        try:
            response = s3_client.list_objects_v2(
                Bucket=config['S3_BUCKET'],
                Prefix='backups/'
            )
            
            # Filter results to get only filenames (without full path)
            files = []
            for obj in response.get('Contents', []):
                with tracer.start_as_current_span("process_s3_object"):
                    key = obj['Key']
                    if key != 'backups/':  # Skip the directory itself
                        files.append({
                            'name': key,
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'].isoformat()
                        })
            
            return files
        except ClientError as e:
            with tracer.start_as_current_span("s3_client_error"):
                print(f"Error getting S3 backups list: {e}")
                return []

def store_s3_data_in_redis(s3_backups):
    with tracer.start_as_current_span("store_s3_data_in_redis"):
        try:
            redis_client.set("s3_list", json.dumps(s3_backups))
            print(f"Stored {len(s3_backups)} S3 backup files in Redis")
        except redis.RedisError as e:
            print(f"Error storing S3 data in Redis: {e}")

def main():
    while True:
        with tracer.start_as_current_span("s3_worker_main_loop"):
            print("S3 task is running...")
            s3_backups = get_s3_backups_list()
            store_s3_data_in_redis(s3_backups)
            time.sleep(60)  # Run every 60 seconds

if __name__ == "__main__":
    main()
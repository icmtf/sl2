import os
import time
import redis
import json
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.requests import RequestsInstrumentor

from pyinet.common.config_loader import ConfigLoader
from pyinet.common.easynet import EasyNet

# Initialize OpenTelemetry
resource = Resource.create({"service.name": "easynet-worker"})
trace.set_tracer_provider(TracerProvider(resource=resource))
otlp_exporter = OTLPSpanExporter(
    endpoint=os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://jaeger:4317')
)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Instrument requests library
RequestsInstrumentor().instrument()

tracer = trace.get_tracer(__name__)

# Load environment variables
load_dotenv()

# Load configuration
required_keys = ["EASYNET_KEY", "EASYNET_SECRET", "APIGEE_BASE_URI", "APIGEE_TOKEN_ENDPOINT", 
                 "APIGEE_EASYNET_ENDPOINT", "APIGEE_CERTIFICATE", "APIGEE_KEY"]
config_loader = ConfigLoader(required_keys=required_keys, yaml_path='settings.yaml', env="prd")
config = config_loader.get_config()

# Initialize Redis client
redis_client = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379'))

# # Initialize EasyNet client
# easynet = EasyNet(
#     apigee_base_uri=config['APIGEE_BASE_URI'],
#     apigee_token_endpoint=config['APIGEE_TOKEN_ENDPOINT'],
#     apigee_easynet_endpoint=config['APIGEE_EASYNET_ENDPOINT'],
#     apigee_certificate=config['APIGEE_CERTIFICATE'],
#     apigee_key=config['APIGEE_KEY'],
#     easynet_key=config['EASYNET_KEY'],
#     easynet_secret=config['EASYNET_SECRET'],
#     ca_requests_bundle=config.get('BNPP_CA_BUNDLE')
# )

def get_easynet_data():
    with tracer.start_as_current_span("get_easynet_data"):
        environment = os.getenv('ENVIRONMENT', 'local')
        if environment == 'production':
            print(f"I'm using Environment: {environment}")
            # Use EasyNet in production
            with tracer.start_as_current_span("easynet_production_call"):
                try:
                    easynet = EasyNet(
                        apigee_base_uri=config.get('APIGEE_BASE_URI'),
                        apigee_token_endpoint=config.get('APIGEE_TOKEN_ENDPOINT'),
                        apigee_easynet_endpoint=config.get('APIGEE_EASYNET_ENDPOINT'),
                        apigee_certificate=config.get('APIGEE_CERTIFICATE'),
                        apigee_key=config.get('APIGEE_KEY'),
                        easynet_key=config['EASYNET_KEY'],
                        easynet_secret=config['EASYNET_SECRET'],
                        ca_requests_bundle=config.get('BNPP_CA_BUNDLE')
                    )
                    return easynet.get_devices()
                except Exception as e:
                    print(f"Error getting EasyNet data in production: {e}")
                    return []
        else:
            # Use local data.json file
            with tracer.start_as_current_span("load_local_data"):
                try:
                    with open('data.json', 'r') as f:
                        return json.load(f)
                except FileNotFoundError:
                    print("Error: data.json file not found")
                    return []
                except json.JSONDecodeError:
                    print("Error: Invalid JSON in data.json")
                    return []

def store_easynet_data_in_redis(devices):
    with tracer.start_as_current_span("store_easynet_data_in_redis"):
        try:
            # Remove all existing device:* keys from Redis
            existing_keys = redis_client.keys("device:*")
            if existing_keys:
                redis_client.delete(*existing_keys)
            
            # Add new data to Redis
            for device in devices:
                redis_client.set(f"device:{device['hostname']}", json.dumps(device))
            
            print(f"Stored {len(devices)} EasyNet devices in Redis")
        except redis.RedisError as e:
            print(f"Error storing EasyNet data in Redis: {e}")

def main():
    while True:
        with tracer.start_as_current_span("easynet_worker_main_loop"):
            print("EasyNet task is running...")
            print(config)
            easynet_data = get_easynet_data()
            store_easynet_data_in_redis(easynet_data)
            time.sleep(30)  # Run every 30 seconds

if __name__ == "__main__":
    main()

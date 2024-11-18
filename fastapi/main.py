from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import redis
import json
import os
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Initialize OpenTelemetry
resource = Resource.create({"service.name": "fastapi-service"})
trace.set_tracer_provider(TracerProvider(resource=resource))
otlp_exporter = OTLPSpanExporter(
    endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instrument FastAPI
FastAPIInstrumentor.instrument_app(app)

# Initialize Redis client
redis_client = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379'))

tracer = trace.get_tracer(__name__)

@app.get("/")
async def root():
    return {"message": "FastAPI is working"}

@app.get("/get_easynet_devices")
async def get_easynet_devices():
    with tracer.start_as_current_span("get_easynet_devices"):
        try:
            keys = redis_client.keys("device:*")
            devices = []
            for key in keys:
                with tracer.start_as_current_span("process_device"):
                    device_data = redis_client.get(key)
                    if device_data:
                        devices.append(json.loads(device_data))
            
            return {"devices": devices}
        except redis.RedisError as e:
            raise HTTPException(status_code=500, detail="Redis error")
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail="JSON decode error")
        except Exception as e:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")

@app.get("/get_device/{hostname}")
async def get_device(hostname: str):
    """Get details for a single device and its backup status"""
    with tracer.start_as_current_span("get_device_details"):
        try:
            # Get device data
            device_key = f"device:{hostname}"
            device_data = redis_client.get(device_key)
            
            if not device_data:
                raise HTTPException(status_code=404, detail="Device not found")
            
            device = json.loads(device_data)
            
            # Get backup data for the device
            backup_data = redis_client.get("s3_backups")
            if backup_data:
                backups = json.loads(backup_data)
                device_backup = backups.get(hostname, {})
                
                # Combine device and backup data
                result = {
                    **device,
                    "backup_info": device_backup
                }
            else:
                result = {
                    **device,
                    "backup_info": {}
                }
            
            return result
            
        except redis.RedisError as e:
            raise HTTPException(status_code=500, detail="Redis error")
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail="JSON decode error")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_devices_backup_status")
async def get_devices_backup_status():
    with tracer.start_as_current_span("get_devices_backup_status"):
        try:
            devices_keys = redis_client.keys("device:*")
            devices = {}
            for key in devices_keys:
                device_data = redis_client.get(key)
                if device_data:
                    device = json.loads(device_data)
                    devices[device['hostname']] = device

            backups_data = redis_client.get("s3_backups")
            backups = json.loads(backups_data) if backups_data else {}

            combined_data = []
            for hostname, device in devices.items():
                backup_info = backups.get(hostname, {})
                device_data = {**device}
                device_data.update({
                    'schema': backup_info.get('schema', False),
                    'backup_json': backup_info.get('has_backup', False),
                    'backup_json_date': backup_info.get('backup.json_s3_date'),
                    'valid_schema': backup_info.get('valid_schema'),
                    'backup_files': []
                })
                
                if backup_info.get('backup_data'):
                    for backup in backup_info['backup_data'].get('backup_list', []):
                        device_data['backup_files'].append(
                            f"[{backup['type']}] {backup['date']}: {backup['backup_file']}"
                        )
                
                combined_data.append(device_data)

            return {"devices": combined_data}
        except redis.RedisError as e:
            raise HTTPException(status_code=500, detail="Redis error")
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail="JSON decode error")
        except Exception as e:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
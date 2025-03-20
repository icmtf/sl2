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
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

# Initialize OpenTelemetry
resource = Resource.create({"service.name": "fastapi-service"})

# Configure sampling - sample 10% of traces
sampler = ParentBasedTraceIdRatio(0.1)

# Initialize TracerProvider with sampler
provider = TracerProvider(
    resource=resource,
    sampler=sampler
)

otlp_exporter = OTLPSpanExporter(
    endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
)
span_processor = BatchSpanProcessor(otlp_exporter)
provider.add_span_processor(span_processor)
trace.set_tracer_provider(provider)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
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
                        device_json = json.loads(device_data)
                        # Pobierz dane z sekcji easynet lub z całego obiektu jeśli easynet nie istnieje
                        easynet_data = device_json.get("easynet", device_json)
                        devices.append(easynet_data)
            
            return {"devices": devices}
        except redis.RedisError as e:
            raise HTTPException(status_code=500, detail="Redis error")
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail="JSON decode error")
        except Exception as e:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")

@app.get("/get_devices_backup_status")
async def get_devices_backup_status():
    with tracer.start_as_current_span("get_devices_backup_status"):
        try:
            devices_keys = redis_client.keys("device:*")
            combined_data = []
            
            for key in devices_keys:
                device_data = redis_client.get(key)
                if device_data:
                    device_json = json.loads(device_data)
                    
                    # Pobierz dane z sekcji easynet (lub całego obiektu jeśli easynet nie istnieje)
                    easynet_data = device_json.get("easynet", {})
                    
                    # Pobierz dane kopii zapasowych, jeśli istnieją
                    backup_info = device_json.get("backup_data", {})
                    backup_json_data = backup_info.get("backup_json_data", {})
                    
                    # Przygotuj dane do wyświetlenia
                    device_data = {**easynet_data}
                    device_data.update({
                        'schema': backup_info.get('schema', False),
                        'backup_json': backup_json_data is not None,
                        'backup_json_date': backup_json_data.get('backup.json_s3_date'),
                        'valid_schema': backup_info.get('valid_schema'),
                        'backup_files': []
                    })
                    
                    # Dodaj listę plików kopii zapasowych, jeśli istnieją
                    if backup_json_data and 'backup_list' in backup_json_data:
                        for backup in backup_json_data['backup_list']:
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
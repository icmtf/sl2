from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import redis
import json
import os
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Initialize OpenTelemetry
trace.set_tracer_provider(TracerProvider())
jaeger_exporter = JaegerExporter(
    agent_host_name=os.getenv("OTEL_EXPORTER_JAEGER_AGENT_HOST", "localhost"),
    agent_port=int(os.getenv("OTEL_EXPORTER_JAEGER_AGENT_PORT", 6831)),
)
span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

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
            # Get all keys matching the pattern "device:*"
            keys = redis_client.keys("device:*")
            
            devices = []
            for key in keys:
                with tracer.start_as_current_span("process_device"):
                    device_data = redis_client.get(key)
                    if device_data:
                        devices.append(json.loads(device_data))
            
            return {"devices": devices}
        except redis.RedisError as e:
            with tracer.start_as_current_span("redis_error"):
                error_message = f"Redis error: {str(e)}"
                raise HTTPException(status_code=500, detail=error_message)
        except json.JSONDecodeError as e:
            with tracer.start_as_current_span("json_decode_error"):
                error_message = f"JSON decode error: {str(e)}"
                raise HTTPException(status_code=500, detail=error_message)
        except Exception as e:
            with tracer.start_as_current_span("unexpected_error"):
                error_message = f"An unexpected error occurred: {str(e)}"
                raise HTTPException(status_code=500, detail=error_message)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

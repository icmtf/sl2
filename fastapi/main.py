from fastapi import FastAPI
import redis
import json
import os

app = FastAPI()

# Initialize Redis client
redis_client = redis.Redis.from_url(os.getenv('REDIS_URL'))

@app.get("/")
async def root():
    return {"message": "FastAPI is working"}

@app.get("/get_easynet_devices")
async def get_easynet_devices():
    # Get all keys matching the pattern "device:*"
    keys = redis_client.keys("device:*")
    
    devices = []
    for key in keys:
        device_data = redis_client.get(key)
        if device_data:
            devices.append(json.loads(device_data))
    
    return {"devices": devices}
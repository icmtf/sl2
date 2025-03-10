import streamlit as st
import redis
import json
import os

REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379')
redis_client = redis.Redis.from_url(REDIS_URL)

def load_devices_data():
    try:
        devices = []
        device_keys = redis_client.keys("device:*")

        for key in device_keys:
            device_data = redis_client.get(key)
            if device_data:
                device = json.loads(device_data)
                devices.append(device)

        return devices
    except Exception as e:
        st.error(f"Error loading devices data: {str(e)}")
        return []

def load_backup_data():
    try:
        backup_data = redis_client.get("s3_backups")
        if backup_data:
            return json.loads(backup_data)
        return {}
    except Exception as e:
        st.error(f"Error loading backup data: {str(e)}")
        return {}

def load_compliance_data():
    try:
        compliance_data = {}
        validation_keys = redis_client.keys("s3_validation:*")
        
        for key in validation_keys:
            hostname = key.decode().split(':')[1]
            data = redis_client.hgetall(key)
            if data and b'validation_data' in data:
                validation_data = json.loads(data[b'validation_data'].decode())
                compliance_data[hostname] = {
                    'validation_data': validation_data,
                    'vendor': data[b'vendor'].decode() if b'vendor' in data else 'Unknown'
                }
        
        return compliance_data
    except Exception as e:
        st.error(f"Error loading compliance data: {str(e)}")
        return {}

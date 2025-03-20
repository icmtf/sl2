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
                device_json = json.loads(device_data)
                
                # Extract hostname from key if needed
                hostname_from_key = key.decode().split(':')[1]
                
                # Create a flattened device object
                device = {}
                
                # Extract data from easynet section if available
                if "easynet" in device_json and isinstance(device_json["easynet"], dict):
                    easynet_data = device_json["easynet"]
                    device.update(easynet_data)  # Add all easynet data to the device object
                
                # Ensure hostname exists
                if "hostname" not in device:
                    device["hostname"] = hostname_from_key
                
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
        device_keys = redis_client.keys("device:*")
        
        for key in device_keys:
            device_data = redis_client.get(key)
            if device_data:
                device_json = json.loads(device_data)
                
                # Get hostname from easynet or key
                hostname = None
                if "easynet" in device_json and isinstance(device_json["easynet"], dict):
                    hostname = device_json["easynet"].get("hostname")
                
                if not hostname:
                    hostname = key.decode().split(':')[1]
                
                # Extract validation data if available
                if hostname and "validation" in device_json:
                    compliance_data[hostname] = device_json["validation"]
        
        return compliance_data
    except Exception as e:
        st.error(f"Error loading compliance data: {str(e)}")
        return {}

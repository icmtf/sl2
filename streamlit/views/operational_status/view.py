import streamlit as st
import pandas as pd
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

def load_opstatus_data():
    try:
        opstatus_data = redis_client.get("s3_opstatus")
        if opstatus_data:
            return json.loads(opstatus_data)
        return {}
    except Exception as e:
        st.error(f"Error loading operational status data: {str(e)}")
        return {}

def get_operational_status(hostname, opstatus_data, status_key):
    """Get operational status for a specific key"""
    try:
        device_data = opstatus_data.get(hostname, {})
        operational_data = device_data.get('operational_status_data', {})
        return operational_data.get(status_key, {}).get('status', 'N/A')
    except Exception:
        return 'N/A'

def display_device_details(device):
    """Display only Device Details for a single device"""
    hostname = device['hostname']

    with st.expander(f"🔍 {hostname}", expanded=False):
        st.write("##### Device Details")
        st.write(f"**Hostname:** {hostname}")
        st.write(f"**IP Address:** {device.get('ip', 'N/A')}")
        st.write(f"**Country:** {device.get('country', 'N/A')}")

def compliance_status_view():
    st.title('Operational Status')
    devices = load_devices_data()
    opstatus_data = load_opstatus_data()
    
    if not devices:
        st.warning("No devices data available")
        return
        
    df = pd.DataFrame(devices)
    
    # Add operational status columns
    operational_status_columns = ['SSH_port', 'HTTPS_port', 'SNMP', 'remote_auth']
    for col in operational_status_columns:
        df[col] = df['hostname'].apply(
            lambda x: get_operational_status(x, opstatus_data, col)
        )

    display_cols = ['hostname', 'ip', 'country', 'device_class'] + operational_status_columns + ['Select']
 
    # Add Select column for details
    df['Select'] = False

    # Show data editor
    edited_df = st.data_editor(
        df[display_cols],
        column_config={
            "Select": st.column_config.CheckboxColumn(
                "Details", 
                help="Select to view device details",
                default=False
            ),
            "hostname": "Hostname",
            "ip": "IP Address", 
            "country": "Country",
            "device_class": "Device Class",
            "SSH_port": "SSH Port Status",
            "HTTPS_port": "HTTPS Port Status",
            "SNMP": "SNMP Status",
            "remote_auth": "Remote Auth Status"
        },
        hide_index=True,
        key='compliance_status_editor'
    )
    
    # Display details for selected devices
    selected_rows = edited_df[edited_df['Select']]
    if not selected_rows.empty:
        st.write("### Device Details")
        devices_dict = {device['hostname']: device for device in devices}
        for _, row in selected_rows.iterrows():
            hostname = row['hostname']
            if hostname in devices_dict:
                display_device_details(devices_dict[hostname])
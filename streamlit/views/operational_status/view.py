import streamlit as st
import pandas as pd
import redis
import json
import os
from datetime import datetime

REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379')
redis_client = redis.Redis.from_url(REDIS_URL)

def load_devices_data():
    """
    Load devices data from Redis, specifically from the 'easynet' section of 'device:hostname' keys.
    Extract only specified columns.
    
    Returns:
        list: A list of dictionaries containing device data with selected columns.
    """
    try:
        devices = []
        device_keys = redis_client.keys("device:*")
        
        for key in device_keys:
            device_data = redis_client.get(key)
            if device_data:
                device_json = json.loads(device_data)
                
                # Extract hostname from key
                hostname_from_key = key.decode().split(':')[1]
                
                # Create a device object with only specified fields
                device = {}
                
                # Extract data from easynet section if available
                if "easynet" in device_json and isinstance(device_json["easynet"], dict):
                    easynet_data = device_json["easynet"]
                    
                    # Extract only the specified fields
                    for field in ['hostname', 'ip', 'country', 'device_class', 'vendor']:
                        device[field] = easynet_data.get(field, "")  # Use empty string instead of 'N/A'
                
                # Ensure hostname exists
                if not device.get("hostname"):
                    device["hostname"] = hostname_from_key
                
                devices.append(device)
        
        return devices
    except Exception as e:
        st.error(f"Error loading devices data: {str(e)}")
        return []

def load_opstatus_data():
    """Load operational status data from the 'operational_status' section in each device"""
    try:
        opstatus_data = {}
        device_keys = redis_client.keys("device:*")
        
        for key in device_keys:
            device_data = redis_client.get(key)
            if device_data:
                device_json = json.loads(device_data)
                
                # Get hostname from easynet or from key
                hostname = None
                if "easynet" in device_json and isinstance(device_json["easynet"], dict):
                    hostname = device_json["easynet"].get("hostname")
                
                if not hostname:
                    hostname = key.decode().split(':')[1]
                
                # Extract operational_status data if available
                if hostname and "operational_status" in device_json:
                    opstatus_data[hostname] = device_json["operational_status"]
        
        return opstatus_data
    except Exception as e:
        st.error(f"Error loading operational status data: {str(e)}")
        return {}

def get_operational_status(hostname, opstatus_data, status_key):
    """Get operational status for a specific key"""
    try:
        device_data = opstatus_data.get(hostname, {})
        
        # Check data structure - may be directly in device_data or in 'operational_status'
        if 'operational_status' in device_data:
            # Structure: {'hostname': {'operational_status': {...}, ...}}
            operational_data = device_data.get('operational_status', {})
        else:
            # Structure: {'hostname': {'SSH_port': {...}, 'HTTPS_port': {...}, ...}}
            operational_data = device_data
        
        # Get status information
        if status_key in operational_data:
            status_info = operational_data.get(status_key, {})
            
            # Check status data format
            if isinstance(status_info, dict):
                status = status_info.get('status', '')  # Use empty string instead of 'N/A'
                message = status_info.get('message', '')
            else:
                # Status may be a direct value
                status = status_info if isinstance(status_info, str) else ''
                message = ''
                
            # Clean the message
            if isinstance(message, str):
                message = message.strip('"')
                if message in ['No message found', '', 'NA']:
                    message = ''
            
            return status, message
        return '', ''  # Use empty string instead of 'N/A'
    except Exception as e:
        print(f"Error in get_operational_status for {hostname}, {status_key}: {str(e)}")
        return '', ''

def get_colored_status(status):
    """Convert status to colored text"""
    if status == 'OK':
        return '🟢'  
    elif status == 'KO':
        return '🔴'  
    elif status == 'NA':
        return '⚫'  
    elif not status:  # Empty status
        return ''
    else:
        return '⚪'

def display_device_details(device, opstatus_data):
    """Display detailed device information including operational status"""
    hostname = device['hostname']
    device_opstatus = opstatus_data.get(hostname, {})

    # Replace empty values with 'N/A' only for display in details
    def display_value(value):
        return value if value else 'N/A'

    with st.expander(f"🔍 {hostname} ({display_value(device.get('ip'))})", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("##### Device Details")
            st.write(f"**Hostname:** {hostname}")
            st.write(f"**IP Address:** {display_value(device.get('ip'))}")
            st.write(f"**Country:** {display_value(device.get('country'))}")
            st.write(f"**Device Class:** {display_value(device.get('device_class'))}")
            st.write(f"**Vendor:** {display_value(device.get('vendor'))}")
        
        with col2:
            st.write("##### Operational Status Details")
            
            # Determine where the operational_status data is located
            operational_status = None
            if 'operational_status' in device_opstatus:
                operational_status = device_opstatus['operational_status']
                last_update = device_opstatus.get('date', 'N/A')
                st.write(f"**Last Updated:** {last_update}")
            else:
                # Check if data is directly in device_opstatus
                operational_keys = ['SSH_port', 'HTTPS_port', 'SNMP', 'remote_auth', 'syslog']
                if any(key in device_opstatus for key in operational_keys):
                    operational_status = device_opstatus
                    last_update = device_opstatus.get('date', 'N/A')
                    st.write(f"**Last Updated:** {last_update}")
            
            if operational_status:
                for key in ['SSH_port', 'HTTPS_port', 'SNMP', 'remote_auth', 'syslog']:
                    if key in operational_status:
                        status_info = operational_status[key]
                        
                        # Handle different data formats
                        if isinstance(status_info, dict):
                            status = status_info.get('status', '')
                            message = status_info.get('message', '')
                            if isinstance(message, str):
                                message = message.strip('"')
                                if message in ['No message found', '', 'NA']:
                                    message = 'No additional information'
                        else:
                            status = status_info if isinstance(status_info, str) else ''
                            message = 'No additional information'
                        
                        status_display = display_value(status)
                        colored_status = get_colored_status(status)
                        st.write(f"**{key}:** {colored_status} ({status_display}) _{message}_")
            else:
                st.warning("No operational status data available for this device.")

# Main view
st.title('Operational Status')

# Load data
devices = load_devices_data()
opstatus_data = load_opstatus_data()

if not devices:
    st.warning("No devices data available")
    st.stop()
    
# Create DataFrame with only selected columns
df = pd.DataFrame(devices)

# Define column order
display_cols = [
    'hostname', 
    'ip', 
    'country', 
    'device_class',
    'vendor', 
    'SSH_port', 
    'HTTPS_port', 
    'SNMP', 
    'remote_auth', 
    'syslog', 
    'Select'
]

# Sidebar filters
st.sidebar.header("Filters")

# Filter out None values from filter options
# Country filter
countries = sorted([c for c in df['country'].unique().tolist() if c])
selected_countries = st.sidebar.multiselect(
    "Select Countries",
    countries,
    default=[]
)

# Device Class filter
device_classes = sorted([d for d in df['device_class'].unique().tolist() if d])
selected_device_classes = st.sidebar.multiselect(
    "Select Device Classes",
    device_classes,
    default=[]
)

# Vendor filter
vendors = sorted([v for v in df['vendor'].unique().tolist() if v])
selected_vendors = st.sidebar.multiselect(
    "Select Vendors",
    vendors,
    default=[]
)

# Apply filters
mask = pd.Series([True] * len(df))

if selected_countries:
    mask &= df['country'].isin(selected_countries)

if selected_device_classes:
    mask &= df['device_class'].isin(selected_device_classes)

if selected_vendors:
    mask &= df['vendor'].isin(selected_vendors)
    
# Filter the DataFrame
filtered_df = df[mask].copy()

# Add operational status columns
operational_status_columns = ['SSH_port', 'HTTPS_port', 'SNMP', 'remote_auth', 'syslog']

for col in operational_status_columns:
    filtered_df[col] = filtered_df['hostname'].apply(
        lambda x: get_operational_status(x, opstatus_data, col)[0]
    )
    filtered_df[col + '_icon'] = filtered_df[col].apply(get_colored_status)
    # Only add space and status text if status is not empty
    filtered_df[col] = filtered_df.apply(
        lambda row: f"{row[col + '_icon']} {row[col]}" if row[col] else "", 
        axis=1
    )
    filtered_df = filtered_df.drop(col + '_icon', axis=1)

# Add Select column for details
filtered_df['Select'] = False

# Show data editor
edited_df = st.data_editor(
    filtered_df[display_cols],
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
        "vendor": "Vendor",
        "SSH_port": st.column_config.Column(
            "SSH Port",
            help="SSH Port Status"
        ),
        "HTTPS_port": st.column_config.Column(
            "HTTPS Port",
            help="HTTPS Port Status"
        ),
        "SNMP": st.column_config.Column(
            "SNMP",
            help="SNMP Status"
        ),
        "remote_auth": st.column_config.Column(
            "Remote Auth",
            help="Remote Authentication Status"
        ),
        "syslog": st.column_config.Column(
            "Syslog",
            help="Syslog Status"
        )
    },
    hide_index=True,
    key='operational_status_editor'
)

# Display details for selected devices
selected_rows = edited_df[edited_df['Select']]
if not selected_rows.empty:
    st.write("### Selected Device Details")
    devices_dict = {device['hostname']: device for device in devices}
    for _, row in selected_rows.iterrows():
        hostname = row['hostname']
        if hostname in devices_dict:
            display_device_details(devices_dict[hostname], opstatus_data)

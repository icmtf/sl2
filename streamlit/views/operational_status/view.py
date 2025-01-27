import streamlit as st
import pandas as pd
import redis
import json
import os
from datetime import datetime

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
    """Load operational status data with new structure"""
    try:
        opstatus_data = redis_client.get("s3_opstatus")
        if opstatus_data:
            data = json.loads(opstatus_data)
            # Convert to hostname-keyed dictionary for easier lookup
            return {item['hostname']: item for item in data} if isinstance(data, list) else data
        return {}
    except Exception as e:
        st.error(f"Error loading operational status data: {str(e)}")
        return {}

def get_operational_status(hostname, opstatus_data, status_key):
    """Get operational status for a specific key with new structure"""
    try:
        device_data = opstatus_data.get(hostname, {})
        operational_data = device_data.get('operational_status', {})
        status_info = operational_data.get(status_key, {})
        status = status_info.get('status', 'N/A')
        message = status_info.get('message', '')
        
        # Clean up message format
        message = message.strip('"')
        if message in ['No message found', '', 'NA']:
            message = ''
            
        return status, message
    except Exception:
        return 'N/A', ''

def get_colored_status(status):
    """Convert status to colored text"""
    if status == 'OK':
        return '🟢'  # Green marker
    elif status == 'KO':
        return '🔴'  # Red marker
    elif status == 'NA':
        return '⚫'  # Black marker
    else:
        return '⚪'  # Gray marker for other statuses

def display_device_details(device, opstatus_data):
    """Display detailed device information including operational status"""
    hostname = device['hostname']
    device_opstatus = opstatus_data.get(hostname, {})

    with st.expander(f"🔍 {hostname} ({device.get('ip', 'N/A')})", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("##### Device Details")
            st.write(f"**Hostname:** {hostname}")
            st.write(f"**IP Address:** {device.get('ip', 'N/A')}")
            st.write(f"**Country:** {device.get('country', 'N/A')}")
            st.write(f"**Vendor:** {device_opstatus.get('vendor', 'N/A')}")
        
        with col2:
            st.write("##### Operational Status Details")
            if 'operational_status' in device_opstatus:
                last_update = device_opstatus.get('date', 'N/A')
                st.write(f"**Last Updated:** {last_update}")
                
                for key, data in device_opstatus['operational_status'].items():
                    status = data.get('status', 'N/A')
                    message = data.get('message', '').strip('"')
                    if message in ['No message found', '', 'NA']:
                        message = 'No additional information'
                    
                    colored_status = get_colored_status(status)
                    st.write(f"**{key}:** {colored_status} ({status}) _{message}_")

def compliance_status_view():
    st.title('Operational Status')
    devices = load_devices_data()
    opstatus_data = load_opstatus_data()
    
    if not devices:
        st.warning("No devices data available")
        return
        
    df = pd.DataFrame(devices)
    
    # Add vendor from opstatus_data
    df['vendor'] = df['hostname'].apply(lambda x: opstatus_data.get(x, {}).get('vendor', 'N/A'))
    
    # Sidebar filters
    st.sidebar.header("Filters")
    
    # Country filter
    countries = sorted([c for c in df['country'].unique().tolist() if c is not None])
    selected_countries = st.sidebar.multiselect(
        "Select Countries",
        countries,
        default=[]
    )
    
    # Device Class filter
    device_classes = sorted([d for d in df['device_class'].unique().tolist() if d is not None])
    selected_device_classes = st.sidebar.multiselect(
        "Select Device Classes",
        device_classes,
        default=[]
    )
    
    # Vendor filter
    vendors = sorted([v for v in df['vendor'].unique().tolist() if v is not None])
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
        # Get both status and message
        filtered_df[col] = filtered_df['hostname'].apply(
            lambda x: get_operational_status(x, opstatus_data, col)[0]
        )
        filtered_df[col + '_icon'] = filtered_df[col].apply(get_colored_status)
        filtered_df[col] = filtered_df[col + '_icon'] + ' ' + filtered_df[col]
        filtered_df = filtered_df.drop(col + '_icon', axis=1)

    # Define column order with vendor added between device_class and SSH_port
    display_cols = [
        'hostname', 
        'ip', 
        'country', 
        'device_class',
        'vendor'
    ] + operational_status_columns + ['Select']
 
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
        key='compliance_status_editor'
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
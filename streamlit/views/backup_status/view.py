import streamlit as st
import pandas as pd
import redis
import json
import os
from views.backup_status.backup_status_column import format_backup_status_value, get_emoji_color
from views.backup_status.backup_status_pie_chart import create_backup_status_pie_chart
from views.backup_status.backup_status_bar_chart import create_backup_status_bar_chart

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

def display_device_details(device):
    """Display only Device Details for a single device"""
    hostname = device['hostname']

    with st.expander(f"🔍 {hostname}", expanded=False):
        st.write("##### Device Details")
        st.write(f"**Hostname:** {hostname}")
        st.write(f"**IP Address:** {device.get('ip', 'N/A')}")
        st.write(f"**Country:** {device.get('country', 'N/A')}")

def backup_status_view():
    st.title('Backup Status')
    devices = load_devices_data()
    backups = load_backup_data()
    
    if not devices:
        st.warning("No devices data available")
        return
    
    df = pd.DataFrame(devices)

    # Create and display charts side by side
    col1, col2 = st.columns(2)
    
    with col1:
        pie_chart = create_backup_status_pie_chart(df, backups)
        st.plotly_chart(pie_chart, use_container_width=True)
    
    with col2:
        bar_chart = create_backup_status_bar_chart(df, backups)
        st.plotly_chart(bar_chart, use_container_width=True)
    
    df['backup_status_column'] = df['hostname'].apply(lambda x: format_backup_status_value(x, backups))
    # Select columns to display
    display_cols = ['hostname', 'ip', 'country', 'device_class', 'backup_status_column', 'Select']
    
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
             "backup_status_column": st.column_config.Column(
                "Backup Status",
                help=f"{get_emoji_color(1)} more than 1 x max_age\n{get_emoji_color(2)} more than 2 x max_age\n{get_emoji_color(3)} more than 3 x max_age\n{get_emoji_color(4)} more than 4 x max_age\n{get_emoji_color(5)} more than 5 x max_age",
            ),
        },
        hide_index=True,
        key='backup_status_editor'
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
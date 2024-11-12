import streamlit as st
import pandas as pd
import redis
import json
import os
from datetime import datetime

# Initialize Redis client
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379')
redis_client = redis.Redis.from_url(REDIS_URL)

def load_devices_data():
    """Load devices data from Redis"""
    try:
        devices = []
        device_keys = redis_client.keys("device:*")
        
        for key in device_keys:
            device_data = redis_client.get(key)
            if device_data:
                device = json.loads(device_data)
                # Add selected field for checkbox
                device['selected'] = False
                devices.append(device)
        
        return devices
    except Exception as e:
        st.error(f"Error loading devices data: {str(e)}")
        return []

def get_backup_status(hostname, backups_data):
    """Get backup status for a device"""
    try:
        backup_info = backups_data.get(hostname, {})
        return "Available" if backup_info.get('has_backup', False) else "Missing"
    except Exception:
        return "Missing"

def format_date(date_str):
    """Format date string nicely"""
    try:
        if not date_str:
            return "N/A"
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%d %b %Y")
    except Exception:
        return date_str

def device_details_view():
    """Main function for Device Details view"""
    st.write("## Network Devices Details")
    
    # Load data
    devices = load_devices_data()
    if not devices:
        st.warning("No devices data available")
        return
    
    # Load backup data
    try:
        backups_data = redis_client.get("s3_backups")
        backups = json.loads(backups_data) if backups_data else {}
    except Exception:
        backups = {}
    
    # Create DataFrame with selected columns
    df = pd.DataFrame(devices)
    
    # Add filters in sidebar
    st.sidebar.write("### Filters")
    
    # Country filter
    countries = sorted(df['country'].unique())
    selected_countries = st.sidebar.multiselect(
        "Filter by Country",
        countries,
        default=[],
        key="country_filter"
    )
    
    # Device Class filter
    device_classes = sorted(df['device_class'].unique())
    selected_device_classes = st.sidebar.multiselect(
        "Filter by Device Class",
        device_classes,
        default=[],
        key="device_class_filter"
    )
    
    # Environment filter
    environments = sorted(df['environment'].unique())
    selected_environments = st.sidebar.multiselect(
        "Filter by Environment",
        environments,
        default=[],
        key="environment_filter"
    )
    
    # Apply filters
    filtered_df = df.copy()
    if selected_countries:
        filtered_df = filtered_df[filtered_df['country'].isin(selected_countries)]
    if selected_device_classes:
        filtered_df = filtered_df[filtered_df['device_class'].isin(selected_device_classes)]
    if selected_environments:
        filtered_df = filtered_df[filtered_df['environment'].isin(selected_environments)]
    
    # Add backup.json information
    def get_backup_icon(hostname):
        if hostname in backups and backups[hostname].get('has_backup', False):
            return "✅"  # Unicode checkmark
        return "❌"  # Unicode cross mark
    
    for idx, row in filtered_df.iterrows():
        filtered_df.at[idx, 'backup.json'] = get_backup_icon(row['hostname'])
    
    # Convert filtered data to display format
    display_df = filtered_df[['hostname', 'ip', 'country', 'environment', 'device_class', 'backup.json', 'selected']].copy()
    
    # Display table with checkboxes
    edited_df = st.data_editor(
        display_df,
        hide_index=True,
        column_config={
            "selected": st.column_config.CheckboxColumn(
                "Details",
                help="Select to view device details",
                width='small',
                default=False,
            ),
            "hostname": st.column_config.TextColumn(
                "Hostname",
                width="medium",
            ),
            "ip": st.column_config.TextColumn(
                "IP Address",
                width="small",
            ),
            "country": st.column_config.TextColumn(
                "Country",
                width="small",
            ),
            "environment": st.column_config.TextColumn(
                "Environment",
                width="small",
            ),
            "device_class": st.column_config.TextColumn(
                "Device Class",
                width="small",
            ),
            "backup.json": st.column_config.Column(
                "Backup",
                width="small",
                help="✅ - Backup available | ❌ - Backup missing",
            )
        },
        key="device_details_table",
        use_container_width=True,
        disabled=["hostname", "ip", "country", "environment", "device_class", "backup.json"]
    )

    # Display details for selected devices
    if edited_df is not None:
        # Create a dictionary for quick lookups
        devices_dict = {device['hostname']: device for device in devices}
        
        for idx, row in edited_df.iterrows():
            if row['selected']:
                device = devices_dict[row['hostname']]
                
                st.write("---")
                # Main sections - Device Information and Backup
                device_info_container = st.container()
                with device_info_container:
                    # Device Information section
                    st.write("## Device Information")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write("##### Device Details")
                        st.write(f"**Hostname:** {device['hostname']}")
                        st.write(f"**IP Address:** {device['ip']}")
                        st.write(f"**Country:** {device['country']}")
                    with col2:
                        st.write("##### System Details")
                        st.write(f"**Operating System:** {device.get('os', 'N/A')}")
                        st.write(f"**Version:** {device.get('version', 'N/A')}")
                        st.write(f"**Partition:** {device.get('partition', 'N/A')}")
                    with col3:
                        st.write("##### Status")
                        st.write(f"**Environment:** {device.get('environment', 'N/A')}")
                        st.write(f"**Status:** {device.get('status_name', 'N/A')}")
                        st.write(f"**Status:** {device.get('status', 'N/A')}")
                
                # Technical Details section (expandable)
                with st.expander("Technical Details"):
                    tech_col1, tech_col2 = st.columns(2)
                    with tech_col1:
                        st.write("##### Hardware Information")
                        st.write(f"**Vendor:** {device.get('vendor', 'N/A')}")
                        st.write(f"**Model:** {device.get('pid', 'N/A')}")
                        st.write(f"**Serial Number:** {device.get('serial_number', 'N/A')}")
                        st.write(f"**Device Class:** {device.get('device_class', 'N/A')}")
                    with tech_col2:
                        st.write("##### Support Details")
                        st.write(f"**Support Profile:** {device.get('support_profile', 'N/A')}")
                        st.write(f"**Last Update:** {format_date(device.get('last_update', 'N/A'))}")
                        st.write(f"**End of Support:** {format_date(device.get('ld_support', 'N/A'))}")
                        st.write(f"**End of SW Support:** {format_date(device.get('ld_sw_support', 'N/A'))}")
                
                # Backup Information section
                with st.expander("Backup Information", expanded=True):
                    if device['hostname'] in backups:
                        backup_info = backups[device['hostname']]
                        st.write("##### Backup Details")
                        st.write(f"**Last Backup Date:** {backup_info.get('backup.json_s3_date', 'N/A')}")
                        st.write(f"**Schema Valid:** {backup_info.get('valid_schema', 'N/A')}")
                        
                        # Show backup files if available
                        if backup_info.get('backup_data', {}).get('backup_list'):
                            st.write("##### Backup Files")
                            for backup in backup_info['backup_data']['backup_list']:
                                st.write(f"- [{backup['type']}] {backup['date']}: {backup['backup_file']}")
                    else:
                        st.warning("No backup information available for this device.")
if __name__ == "__main__":
    device_details_view()
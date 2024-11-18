import streamlit as st
import pandas as pd
import redis
import json
import os
from datetime import datetime
from .backup_formatter import get_backup_status, get_backup_icon

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
                devices.append(device)
        
        return devices
    except Exception as e:
        st.error(f"Error loading devices data: {str(e)}")
        return []

def format_date(date_str):
    """Format date string nicely"""
    try:
        if not date_str:
            return "N/A"
        date_obj = datetime.fromisoformat(date_str)
        return date_obj.strftime("%Y-%m-%d %H:%M:%S %z")
    except Exception:
        return date_str

def display_device_details(device, backups):
    """Display details for a single device"""
    hostname = device['hostname']
    
    st.write("---")
    # Device Information section
    st.write(f"## Device Information - {hostname}")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write("##### Device Details")
        st.write(f"**Hostname:** {hostname}")
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
    
    # Technical Details section
    with st.expander("Technical Details", expanded=True):
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
    if hostname in backups:
        with st.expander("Backup Information", expanded=True):
            backup_info = backups[hostname]
            st.write("##### Backup Details")
            st.write(f"**Schema Valid:** {backup_info.get('valid_schema', 'N/A')}")
            
            if backup_info.get('backup_data', {}).get('backup_list'):
                st.write("##### Backup Files")
                for backup in backup_info['backup_data']['backup_list']:
                    st.write(f"- [{backup['type']}] {format_date(backup['date'])}: {backup['backup_file']}")

def handle_selection_change(editor_change):
    """Handle selection changes without triggering page reload"""
    if editor_change.get('edited_rows'):
        for idx, changes in editor_change['edited_rows'].items():
            if 'selected' in changes:
                hostname = st.session_state.display_df.iloc[int(idx)]['hostname']
                if changes['selected']:
                    st.session_state.selected_devices.add(hostname)
                else:
                    st.session_state.selected_devices.discard(hostname)

def device_details_view():
    """Main function for Device Details view"""
    st.write("## Network Devices Details")
    
    # Initialize session states if not already present
    if 'selected_devices' not in st.session_state:
        st.session_state.selected_devices = set()
    if 'sort_column' not in st.session_state:
        st.session_state.sort_column = None
    if 'sort_direction' not in st.session_state:
        st.session_state.sort_direction = None
    
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
    
    # Create DataFrame
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
    
    # Add backup status and backup icon
    for idx, row in filtered_df.iterrows():
        filtered_df.at[idx, 'backup_status'] = get_backup_status(row['hostname'], backups)
        filtered_df.at[idx, 'backup'] = get_backup_icon(row['hostname'], backups)
        filtered_df.at[idx, 'selected'] = row['hostname'] in st.session_state.selected_devices
    
    # Convert filtered data to display format
    display_df = filtered_df[['hostname', 'ip', 'country', 'environment', 
                             'device_class', 'backup_status', 'backup', 'selected']].copy()
    
    # Save display DataFrame to session state
    st.session_state.display_df = display_df
    
    # Apply sorting if set
    if st.session_state.sort_column:
        ascending = st.session_state.sort_direction == 'ascending'
        display_df = display_df.sort_values(
            by=st.session_state.sort_column,
            ascending=ascending
        )
    
    # Create data editor
    editor_change = st.data_editor(
        display_df,
        hide_index=True,
        column_config={
            "selected": st.column_config.CheckboxColumn(
                "Details",
                help="Select to view device details",
                width='small',
                default=False
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
            "backup_status": st.column_config.Column(
                "Backup Status",
                width="medium",
                help="🟢 OK | 🟡 Warning | 🟠 Critical | 🔴 Error | 🟣 Severe | ⚫ Unknown",
            ),
            "backup": st.column_config.Column(
                "Backup",
                width="small",
                help="✅ - Backup available | ❌ - Backup missing",
            )
        },
        key="device_details_table",
        use_container_width=True,
        disabled=["hostname", "ip", "country", "environment", "device_class", "backup_status", "backup"],
        on_change=lambda: handle_selection_change(st.session_state.device_details_table)
    )
    
    # Handle sorting
    if 'sorted_column' in st.session_state.device_details_table:
        sort_info = st.session_state.device_details_table['sorted_column']
        if sort_info:
            st.session_state.sort_column = sort_info['column']
            st.session_state.sort_direction = sort_info['direction']
    
    # Display details for selected devices
    devices_dict = {device['hostname']: device for device in devices}
    for hostname in sorted(st.session_state.selected_devices):
        if hostname in devices_dict:
            display_device_details(devices_dict[hostname], backups)

if __name__ == "__main__":
    device_details_view()
import streamlit as st
import pandas as pd
import redis
import json
import os
import plotly.express as px
import plotly.graph_objects as go
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

def analyze_backup_status(backup_info):
    """Analyze backup status and determine if it's all green"""
    try:
        if not backup_info:
            return False
        
        backup_data = backup_info.get('backup_data', {})
        if not backup_data:
            return False
            
        backup_list = backup_data.get('backup_list', [])
        if not backup_list:
            return False
        
        for backup in backup_list:
            age_info = backup.get('age_info', {})
            if not age_info or age_info.get('status') != 'ok':
                return False
                
        return True
    except Exception as e:
        print(f"Error analyzing backup status: {e}")
        return False

def get_backup_statistics(devices_df, backups):
    """Calculate backup statistics for devices"""
    stats = {
        'total': len(devices_df),
        'green': 0,
        'red': 0,
        'by_vendor': {}
    }
    
    for _, device in devices_df.iterrows():
        hostname = device['hostname']
        vendor = device.get('vendor', 'Unknown')
        
        if vendor not in stats['by_vendor']:
            stats['by_vendor'][vendor] = {'green': 0, 'red': 0}
        
        # Check if device has all green backups
        backup_info = backups.get(hostname, {})
        if analyze_backup_status(backup_info):
            stats['green'] += 1
            stats['by_vendor'][vendor]['green'] += 1
        else:
            stats['red'] += 1
            stats['by_vendor'][vendor]['red'] += 1
    
    return stats

def create_backup_charts(stats):
    """Create pie and bar charts for backup statistics"""
    # Pie Chart
    pie_data = pd.DataFrame([
        {'Status': 'All Green', 'Count': stats['green']},
        {'Status': 'Issues', 'Count': stats['red']}
    ])
    
    pie_chart = px.pie(
        pie_data,
        values='Count',
        names='Status',
        title='Backup Status Distribution',
        color_discrete_map={'All Green': '#90EE90', 'Issues': '#FFB6C1'}
    )
    pie_chart.update_traces(textposition='inside', textinfo='percent+label')
    
    # Bar Chart
    vendor_data = []
    for vendor, counts in stats['by_vendor'].items():
        vendor_data.extend([
            {'Vendor': vendor, 'Status': 'All Green', 'Count': counts['green']},
            {'Vendor': vendor, 'Status': 'Issues', 'Count': counts['red']}
        ])
    
    bar_chart = px.bar(
        pd.DataFrame(vendor_data),
        x='Vendor',
        y='Count',
        color='Status',
        title='Backup Status by Vendor',
        color_discrete_map={'All Green': '#90EE90', 'Issues': '#FFB6C1'},
        barmode='stack'
    )
    
    return pie_chart, bar_chart

def display_device_details(device, backups):
    """Display details for a single device"""
    hostname = device['hostname']
    
    with st.expander(f"🔍 {hostname}", expanded=False):
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
            st.write(f"**Device Class:** {device.get('device_class', 'N/A')}")
            st.write(f"**Status:** {device.get('status_name', 'N/A')}")
            st.write(f"**Vendor:** {device.get('vendor', 'N/A')}")
        
        # Technical Details section
        tech_col1, tech_col2 = st.columns(2)
        with tech_col1:
            st.write("##### Hardware Information")
            st.write(f"**Model:** {device.get('pid', 'N/A')}")
            st.write(f"**Serial Number:** {device.get('serial_number', 'N/A')}")
        with tech_col2:
            st.write("##### Support Details")
            st.write(f"**Support Profile:** {device.get('support_profile', 'N/A')}")
            st.write(f"**Last Update:** {format_date(device.get('last_update', 'N/A'))}")
            st.write(f"**End of Support:** {format_date(device.get('ld_support', 'N/A'))}")
            st.write(f"**End of SW Support:** {format_date(device.get('ld_sw_support', 'N/A'))}")
        
        # Backup Information section
        if hostname in backups:
            backup_info = backups[hostname]
            st.write("##### Backup Details")
            st.write(f"**Schema Valid:** {backup_info.get('valid_schema', 'N/A')}")
            
            if backup_info.get('backup_data', {}).get('backup_list'):
                st.write("##### Backup Files")
                for backup in backup_info['backup_data']['backup_list']:
                    st.write(f"- [{backup['type']}] {format_date(backup['date'])}: {backup['backup_file']}")

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
        st.error("Error loading backup data")
        backups = {}
    
    # Create DataFrame
    df = pd.DataFrame(devices)
    
    # Add filters in sidebar
    st.sidebar.write("### Filters")
    
    # Country filter
    countries = sorted([x for x in df['country'].unique() if x is not None], key=str)
    selected_countries = st.sidebar.multiselect(
        "Filter by Country",
        countries,
        default=[],
        key="country_filter"
    )
    
    # Device Class filter
    device_classes = sorted([x for x in df['device_class'].unique() if x is not None], key=str)
    selected_device_classes = st.sidebar.multiselect(
        "Filter by Device Class",
        device_classes,
        default=[],
        key="device_class_filter"
    )
    
    # Vendor filter
    vendors = sorted([x for x in df['vendor'].unique() if x is not None], key=str)
    selected_vendors = st.sidebar.multiselect(
        "Filter by Vendor",
        vendors,
        default=[],
        key="vendor_filter"
    )
    
    # Apply filters
    filtered_df = df.copy()
    if selected_countries:
        filtered_df = filtered_df[filtered_df['country'].isin(selected_countries)]
    if selected_device_classes:
        filtered_df = filtered_df[filtered_df['device_class'].isin(selected_device_classes)]
    if selected_vendors:
        filtered_df = filtered_df[filtered_df['vendor'].isin(selected_vendors)]
    
    # Calculate and display backup statistics
    stats = get_backup_statistics(filtered_df, backups)
    
    # Create and display charts
    pie_chart, bar_chart = create_backup_charts(stats)
    
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(pie_chart, use_container_width=True)
    with col2:
        st.plotly_chart(bar_chart, use_container_width=True)
    
    # Add backup status and backup icon
    for idx, row in filtered_df.iterrows():
        filtered_df.at[idx, 'backup_status'] = get_backup_status(row['hostname'], backups)
        filtered_df.at[idx, 'backup'] = get_backup_icon(row['hostname'], backups)
    
    # Add Select column
    filtered_df['Select'] = False
    
    # Prepare display columns
    display_df = filtered_df[['hostname', 'ip', 'country', 'device_class', 
                             'backup_status', 'backup', 'Select']].copy()
    
    # Create data editor with checkboxes
    edited_df = st.data_editor(
        display_df,
        column_config={
            "Select": st.column_config.CheckboxColumn(
                "Details",
                help="Select to view device details",
                default=False,
            ),
            "hostname": st.column_config.TextColumn("Hostname"),
            "ip": st.column_config.TextColumn("IP Address"),
            "country": st.column_config.TextColumn("Country"),
            "device_class": st.column_config.TextColumn("Device Class"),
            "backup_status": st.column_config.Column(
                "Backup Status",
                help="🟢 OK | 🟡 Warning | 🟠 Critical | 🔴 Error | 🟣 Severe | ⚫ Unknown",
            ),
            "backup": st.column_config.Column(
                "Backup",
                help="✅ - Backup available | ❌ - Backup missing",
            )
        },
        disabled=["hostname", "ip", "country", "device_class", "backup_status", "backup"],
        hide_index=True,
        use_container_width=True
    )

    # Display details for selected devices
    selected_rows = edited_df[edited_df['Select']]
    if not selected_rows.empty:
        st.write("### Device Details")
        devices_dict = {device['hostname']: device for device in devices}
        for _, row in selected_rows.iterrows():
            hostname = row['hostname']
            if hostname in devices_dict:
                display_device_details(devices_dict[hostname], backups)
import streamlit as st
import pandas as pd
import redis
import json
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from typing import Dict, Any

# Initialize Redis client
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379')
redis_client = redis.Redis.from_url(REDIS_URL)

def format_backup_date(date_str):
    """Format backup date to local time with readable format"""
    try:
        # Convert ISO date string to datetime object
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        # Format date as requested
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        return date_str

def format_date(date_str):
    """Format date for display in device details"""
    if date_str == 'N/A':
        return date_str
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return date_str


def get_backup_status_info(hostname: str, backups: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get backup status information for a device with status tracking per type.
    
    Args:
        hostname: Device hostname
        backups: Dictionary containing backup information for all devices
    
    Returns:
        Dictionary containing:
        - status: Overall status (worst status among all types)
        - type_statuses: Dictionary mapping backup types to their status
        - worst_status: Worst status value found
    """
    DEFAULT_STATUS = {
        'status': 5,
        'type_statuses': {},
        'worst_status': 5
    }

    try:
        if not hostname in backups:
            return DEFAULT_STATUS
        
        backup_info = backups.get(hostname, {})
        if not backup_info:
            return DEFAULT_STATUS
            
        backup_data = backup_info.get('backup_data', {})
        if not backup_data:
            return DEFAULT_STATUS
            
        backup_list = backup_data.get('backup_list', [])
        if not backup_list:
            return DEFAULT_STATUS
        
        # Track age factors per type
        type_age_factors: Dict[str, float] = {}
        
        # Process each backup
        for backup in backup_list:
            if not isinstance(backup, dict):
                continue
                
            backup_type = backup.get('type')
            if not backup_type:
                continue
                
            age_info = backup.get('age_info', {})
            if not isinstance(age_info, dict):
                age_info = {}
                
            try:
                age_factor = float(age_info.get('age_factor', float('inf')))
            except (TypeError, ValueError):
                age_factor = float('inf')
            
            # Keep track of the worst (highest) age factor for each type
            current_worst = type_age_factors.get(backup_type, -1)
            type_age_factors[backup_type] = max(current_worst, age_factor)
        
        # If we have no valid age factors, return default status
        if not type_age_factors:
            return DEFAULT_STATUS
        
        # Convert age factors to status levels
        type_statuses = {}
        worst_overall_status = 0
        
        for backup_type, age_factor in type_age_factors.items():
            if age_factor == 0:
                status = 0  # green - current
            elif age_factor == 1:
                status = 1  # yellow - one period overdue
            else:
                status = 2  # red - multiple periods overdue
                
            type_statuses[backup_type] = status
            worst_overall_status = max(worst_overall_status, status)
        
        return {
            'status': worst_overall_status,
            'type_statuses': type_statuses,
            'worst_status': worst_overall_status
        }
        
    except Exception as e:
        print(f"Error getting backup status for {hostname}: {str(e)}")
        return DEFAULT_STATUS
    
def get_status_display(status_info):
    """Get status display info with proper color emoji and description"""
    if not status_info or 'worst_status' not in status_info:
        return "⚪ No backup.json"

    status = status_info.get('worst_status', 5)
    
    status_mapping = {
        0: ("🟢", "OK"),
        1: ("🟡", "Warning"),
        2: ("🟠", "Attention"),
        3: ("🔴", "Severe"),
        4: ("🟣", "Critical"),
        5: ("⚫", "Failure")
    }
    
    emoji, description = status_mapping.get(status, ("⚪", "No backup.json"))
    return f"{emoji} {description}"

def create_backup_charts(devices_df, backups):
    """Create pie and bar charts for backup statistics"""
    # Define status colors for charts
    color_mapping = {
        "🟢 OK": "#00FF00",
        "🟡 Warning": "#FFFF00",
        "🟠 Attention": "#FFA500",
        "🔴 Severe": "#FF0000",
        "🟣 Critical": "#800080",
        "⚫ Failure": "#000000",
        "⚪ Bad backup.json": "#808080",
        "❌ No backup.json": "#FF0000"  # Czerwony dla braku pliku
    }
    
    # Initialize counters
    status_counts = {status: 0 for status in color_mapping.keys()}
    vendor_status_counts = {}
    
    total_devices = len(devices_df)
    
    # Count devices per status and vendor
    for _, device in devices_df.iterrows():
        hostname = device['hostname']
        vendor = device.get('vendor', 'Unknown')
        
        # Get backup status
        if hostname not in backups:
            status_label = "❌ No backup.json"
        else:
            backup_info = get_backup_status_info(hostname, backups)
            if not backup_info.get('type_statuses'):
                status_label = "⚪ Empty backup"
            else:
                worst_status = backup_info.get('worst_status', 5)
                if worst_status == 0:
                    status_label = "🟢 OK"
                elif worst_status == 1:
                    status_label = "🟡 Warning"
                elif worst_status == 2:
                    status_label = "🟠 Attention"
                elif worst_status == 3:
                    status_label = "🔴 Severe"
                elif worst_status == 4:
                    status_label = "🟣 Critical"
                else:
                    status_label = "⚫ Failure"
        
        # Update global status counts
        status_counts[status_label] = status_counts.get(status_label, 0) + 1
        
        # Initialize vendor dict if needed
        if vendor not in vendor_status_counts:
            vendor_status_counts[vendor] = {status: 0 for status in color_mapping.keys()}
        
        # Update vendor status counts
        vendor_status_counts[vendor][status_label] += 1
    
    # Convert counts to DataFrames for visualization
    pie_data = []
    for status, count in status_counts.items():
        if count > 0:  # Only include statuses that have devices
            percentage = (count / total_devices * 100)
            pie_data.append({
                'Status': status,
                'Count': count,
                'Percentage': f"{percentage:.1f}%"
            })
    
    bar_data = []
    for vendor, counts in vendor_status_counts.items():
        vendor_total = sum(counts.values())
        for status, count in counts.items():
            if count > 0:  # Only include statuses that have devices
                percentage = (count / vendor_total * 100)
                bar_data.append({
                    'Vendor': vendor,
                    'Status': status,
                    'Count': count,
                    'Percentage': f"{percentage:.1f}%"
                })
    
    pie_df = pd.DataFrame(pie_data)
    bar_df = pd.DataFrame(bar_data)
    
    # Create pie chart
    pie_chart = px.pie(
        pie_df,
        values='Count',
        names='Status',
        title='Backup Status Distribution',
        hover_data=['Percentage']
    )
    pie_chart.update_traces(
        textposition='inside', 
        texttemplate='%{label}<br>%{percent:.1%}'
    )
    
    # Create bar chart
    bar_chart = px.bar(
        bar_df,
        x='Vendor',
        y='Count',
        color='Status',
        title='Backup Status by Vendor',
        barmode='stack',
        hover_data=['Percentage'],
        color_discrete_map=color_mapping
    )
    
    # Update pie chart colors
    pie_chart.update_traces(marker=dict(colors=[color_mapping[status] for status in pie_df['Status']]))
    
    # Ensure consistent legend ordering
    bar_chart.update_layout(
        showlegend=True,
        legend=dict(
            traceorder='normal',
            title_text=''
        )
    )

    return pie_chart, bar_chart



def display_device_details(device, backups):
    """Display details for a single device"""
    hostname = device['hostname']
    
    with st.expander(f"🔍 {hostname}", expanded=False):
        # Get backup status info for this device
        backup_info = backups.get(hostname, {})
        backup_data = backup_info.get('backup_data', {})
        backup_list = backup_data.get('backup_list', [])

        # Display backup files if they exist
        if backup_list:
            for backup in backup_list:
                emoji = '🔴'  # Możesz dostosować emoji w zależności od age_factor
                if backup.get('age_info', {}).get('age_factor', 0) == 0:
                    emoji = '🟢'
                elif backup.get('age_info', {}).get('age_factor', 0) == 1:
                    emoji = '🟡'
                
                formatted_date = format_backup_date(backup.get('date', 'Unknown'))
                st.markdown(
                    f"### {emoji} [{backup.get('type', 'Unknown')}] {formatted_date}: {backup.get('backup_file', 'Unknown')}"
                )
        else:
            st.markdown("### ❌ No backups available")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.write("##### Device Details")
            st.write(f"**Hostname:** {hostname}")
            st.write(f"**IP Address:** {device.get('ip', 'N/A')}")
            st.write(f"**Country:** {device.get('country', 'N/A')}")
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
        
        # Technical Details
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

def device_details_view():
    """Main function for Device Details view"""
    st.write("## Network Devices Details")
    
    # Load data
    devices = load_devices_data()
    backups = load_backup_data()
    
    if not devices:
        st.warning("No devices data available")
        return
    
    # Create DataFrame
    df = pd.DataFrame(devices)
    
    # Add filters in sidebar
    st.sidebar.write("### Filters")
    
    # Country filter
    countries = sorted([x for x in df['country'].unique() if x is not None])
    selected_countries = st.sidebar.multiselect(
        "Filter by Country",
        countries,
        default=[],
        key="country_filter"
    )
    
    # Device Class filter
    device_classes = sorted([x for x in df['device_class'].unique() if x is not None])
    selected_device_classes = st.sidebar.multiselect(
        "Filter by Device Class",
        device_classes,
        default=[],
        key="device_class_filter"
    )
    
    # Vendor filter
    vendors = sorted([x for x in df['vendor'].unique() if x is not None])
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
    
    # Create and display charts
    pie_chart, bar_chart = create_backup_charts(filtered_df, backups)
    
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(pie_chart, use_container_width=True)
    with col2:
        st.plotly_chart(bar_chart, use_container_width=True)
    
    # Get backup status for each device
    display_df = filtered_df.copy()
    
    # Get backup status for each device
    display_df['backup_display'] = display_df['hostname'].apply(
        lambda x: format_backup_display(get_backup_status_info(x, backups))
    )
    
    # Add Select column for details
    display_df['Select'] = False
    
    # Create data editor with backup status
    edited_df = st.data_editor(
        display_df[['hostname', 'ip', 'country', 'device_class', 'backup_display', 'Select']],
        column_config={
            "Select": st.column_config.CheckboxColumn(
                "Details",
                help="Select to view device details",
                default=False,
            ),
            "hostname": "Hostname",
            "ip": "IP Address",
            "country": "Country",
            "device_class": "Device Class",
            "backup_display": st.column_config.Column(
                "Backup Status",
                help="Shows backup status and file types"
            )
        },
        disabled=["hostname", "ip", "country", "device_class", "backup_display"],
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

def load_backup_data():
    """Load backup data from Redis"""
    try:
        backup_data = redis_client.get("s3_backups")
        if backup_data:
            return json.loads(backup_data)
        return {}
    except Exception as e:
        st.error(f"Error loading backup data: {str(e)}")
        return {}

def format_backup_display(status_info):
    """Format backup display string for data editor"""
    if not status_info or not status_info.get('type_statuses'):
        return "❌ No backup"

    type_statuses = status_info['type_statuses']
    formatted_parts = []

    worst_status = status_info.get('worst_status', 5)
    emoji = '🟢' if worst_status == 0 else '🟡' if worst_status == 1 else '🔴'

    types_str = ", ".join(sorted(type_statuses.keys()))
    return f"{emoji} {types_str}"
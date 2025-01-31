import streamlit as st
import pandas as pd
import redis
import json
import os
from streamlit_dynamic_filters import DynamicFilters
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
        backups = {}
        backup_keys = redis_client.keys("s3_backups:*")
        
        for key in backup_keys:
            backup_data = redis_client.hgetall(key)
            if backup_data:
                hostname = key.decode().split(':')[1]
                backup_json = json.loads(backup_data[b'backup_data'])
                backups[hostname] = backup_json
        
        return backups
    except Exception as e:
        st.error(f"Error loading backup data: {str(e)}")
        return {}

def display_device_details(device, backups):
    """Display Device Details and backup.json for a single device"""
    hostname = device['hostname']

    with st.expander(f"🔍 {hostname} ({device.get('ip', 'N/A')})", expanded=False):
        st.write("##### Device Details")
        st.write(f"**Hostname:** {hostname}")
        st.write(f"**IP Address:** {device.get('ip', 'N/A')}")
        st.write(f"**Country:** {device.get('Country', 'N/A')}")
        
        if hostname in backups:
            backup_data = backups[hostname]
            with st.popover("📄 backup.json"):
                st.json(backup_data)
        else:
            st.button("📄 backup.json", disabled=True, help="No backup.json available")

def clean_df_values(df, columns):
    """Replace None/NaN values with 'Unknown' in specified columns"""
    df = df.copy()
    for col in columns:
        df[col] = df[col].fillna('Unknown')
    return df

st.title('Backup Status')

# Load data
devices = load_devices_data()
backups = load_backup_data()

if not devices:
    st.warning("No devices data available")
    st.stop()

# Create DataFrame
df = pd.DataFrame(devices)

# Add backup status column
df['Backup Status'] = df['hostname'].apply(
    lambda x: format_backup_status_value(x, backups)
)

# Clean values first using original column names
original_cols = ["country", "vendor", "device_class", "Backup Status"]
df = clean_df_values(df, original_cols)

# Then rename columns
df = df.rename(columns={
    'device_class': 'Device Class',
    'country': 'Country',
    'vendor': 'Vendor'
})

filtering_cols = ["Country", "Vendor", "Device Class", "Backup Status"]

# Setup filters
st.sidebar.header("Filters")
dynamic_filters = DynamicFilters(df, filters=filtering_cols, filters_name="backup_status_filters")
filtered_df = dynamic_filters.filter_df()

# Display filters in sidebar
dynamic_filters.display_filters(location="sidebar")

# Create and display charts side by side
col1, col2 = st.columns(2)

with col1:
    pie_chart = create_backup_status_pie_chart(filtered_df, backups)
    st.plotly_chart(pie_chart, use_container_width=True)

with col2:
    bar_chart = create_backup_status_bar_chart(filtered_df, backups)
    st.plotly_chart(bar_chart, use_container_width=True)

# Select columns to display and their order
display_cols = [
    'hostname', 
    'ip', 
    'Country', 
    'Device Class',
    'Vendor',
    'Backup Status', 
    'Select'
]

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
        "Country": "Country",
        "Device Class": "Device Class",
        "Vendor": "Vendor",
        "Backup Status": st.column_config.Column(
            "Backup Status",
            help=f"{get_emoji_color(1)} more than 1 x max_age\n"
                 f"{get_emoji_color(2)} more than 2 x max_age\n"
                 f"{get_emoji_color(3)} more than 3 x max_age\n"
                 f"{get_emoji_color(4)} more than 4 x max_age\n"
                 f"{get_emoji_color(5)} more than 5 x max_age",
        ),
    },
    hide_index=True,
    key='backup_status_editor',
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
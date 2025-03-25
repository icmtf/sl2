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
                try:
                    device_json = json.loads(device_data)
                    
                    # Pobierz dane easynet
                    easynet_data = device_json.get("easynet", {})
                    
                    # Jeśli easynet zawiera dane, użyj ich
                    if easynet_data:
                        device_info = easynet_data.copy()
                        
                        # Dodaj referencję do backup_data
                        if "backup_data" in device_json:
                            device_info["_backup_data_ref"] = device_json["backup_data"]
                            
                        devices.append(device_info)
                except json.JSONDecodeError as e:
                    pass
        
        return devices
    except Exception as e:
        st.error(f"Error loading devices data: {str(e)}")
        return []

def load_backup_data():
    try:
        backups = {}
        device_keys = redis_client.keys("device:*")
        
        backup_count = 0
        
        for key in device_keys:
            device_data = redis_client.get(key)
            if device_data:
                try:
                    device_json = json.loads(device_data)
                    
                    # Pobierz hostname bezpośrednio z klucza
                    hostname = key.decode().split(':')[1]
                    
                    # Jeśli mamy hostname i backup, dodaj do słownika (s3_worker_new używa klucza 'backup')
                    if hostname and "backup" in device_json:
                        backups[hostname] = device_json["backup"]
                        backup_count += 1
                    elif hostname and "backup_data" in device_json:
                        # Kompatybilność wsteczna
                        backups[hostname] = device_json["backup_data"]
                        backup_count += 1
                except Exception as e:
                    pass  # Cichy błąd parsowania
        
        print(f"Loaded {backup_count} backup data entries")
        return backups
    except Exception as e:
        st.error(f"Error loading backup data: {str(e)}")
        return {}

def display_device_details(device, backups):
    """Display Device Details and backup.json for a single device"""
    hostname = device.get('hostname')
    if not hostname:
        st.error("No hostname found for device")
        return

    with st.expander(f"🔍 {hostname}", expanded=False):
        st.write("##### Device Details")
        st.write(f"**Hostname:** {hostname}")
        
        # Pokazuj pole IP
        st.write(f"**IP Address:** {device.get('ip', 'N/A')}")
        
        # Pokazuj pole Country w jednej z możliwych wersji nazwy
        if 'Country' in device:
            st.write(f"**Country:** {device['Country']}")
        elif 'country' in device:
            st.write(f"**Country:** {device['country']}")
        else:
            st.write(f"**Country:** N/A")
        
        # Wyświetl wszystkie istotne informacje, jeśli są dostępne
        for field, label in [
            ('vendor', 'Vendor'), 
            ('device_class', 'Device Class'),
            ('device_type', 'Device Type')
        ]:
            if field in device and device[field]:
                st.write(f"**{label}:** {device[field]}")
        
        if hostname in backups:
            backup_data = backups[hostname]
            # Spróbuj znaleźć właściwe dane do wyświetlenia
            display_data = backup_data
            if 'backup_json_data' in backup_data:
                display_data = backup_data.get("backup_json_data", {})
            
            with st.popover("📄 backup.json"):
                st.json(display_data)
        else:
            st.button("📄 backup.json", disabled=True, help="No backup.json available")

def clean_df_values(df, columns):
    """Replace None/NaN values with 'Unknown' in specified columns"""
    df = df.copy()
    for col in columns:
        # Upewnij się, że kolumna istnieje
        if col in df.columns:
            # Zamień NaN, None, puste stringi na 'Unknown'
            df[col] = df[col].apply(lambda x: 'Unknown' if x is None or (isinstance(x, str) and x.strip() == '') else x)
            df[col] = df[col].fillna('Unknown')
        else:
            # Jeśli kolumna nie istnieje, utwórz ją z domyślną wartością
            df[col] = 'Unknown'
    return df

st.title('Backup Status')

# Load data
devices = load_devices_data()
backups = load_backup_data()

if not devices:
    st.warning("No devices data available")
    st.stop()

# Create DataFrame
devices_list = []
for device in devices:
    # Make sure each device has a 'hostname' field
    if not device.get('hostname'):
        # If hostname is missing, skip this device
        continue
    devices_list.append(device)

if not devices_list:
    st.warning("No valid devices with hostname found")
    st.stop()
    
df = pd.DataFrame(devices_list)

# Add backup status column
df['Backup Status'] = df['hostname'].apply(
    lambda x: format_backup_status_value(x, backups) if x else None
)

# Zmień nazwy kolumn
df = df.rename(columns={
    'device_class': 'Device Class',
    'vendor': 'Vendor',
    'country': 'Country'
})

# Define columns used for filtering
filtering_cols = ["Country", "Vendor", "Device Class", "Backup Status"]

# Prepare data for filtering - replace None with empty strings for filters
for col in filtering_cols:
    if col in df.columns:
        df[col] = df[col].fillna('')  # Only for filtering purposes

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
    devices_dict = {device.get('hostname', ''): device for device in devices if device.get('hostname')}
    for _, row in selected_rows.iterrows():
        hostname = row.get('hostname')
        if hostname and hostname in devices_dict:
            display_device_details(devices_dict[hostname], backups)
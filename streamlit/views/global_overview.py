
import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
import plotly.express as px
import redis
import json
import os
from datetime import datetime

# Initialize Redis client
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379')
redis_client = redis.Redis.from_url(REDIS_URL)

@st.cache_data
def load_world_data():
    """Load world geographic data from local file"""
    try:
        geo_file_path = os.path.join(os.getcwd(), 'data', 'geo', 'countries.geojson')
        gdf = gpd.read_file(geo_file_path)
        return gdf
    except Exception as e:
        st.error(f"Error loading geographic data: {str(e)}")
        raise

def get_devices_data():
    """Get devices data from Redis"""
    try:
        devices = []
        device_keys = redis_client.keys("device:*")
        
        for key in device_keys:
            device_data = redis_client.get(key)
            if device_data:
                device = json.loads(device_data)
                if not device.get('country'):
                    device['country'] = 'Unknown'
                if not device.get('device_class'):
                    device['device_class'] = 'Unknown'
                if not device.get('vendor'):
                    device['vendor'] = 'Unknown'
                devices.append(device)
        
        return devices
    except Exception as e:
        st.error(f"Error getting devices data: {str(e)}")
        return []

def get_backup_data():
    """Get backup data from Redis"""
    try:
        backup_data = redis_client.get("s3_backups")
        if backup_data:
            return json.loads(backup_data)
        return {}
    except Exception as e:
        st.error(f"Error getting backup data: {str(e)}")
        return {}

def create_map(world_data, devices_df, selected_country):
    """Create Folium map with country highlighting"""
    try:
        m = folium.Map(location=[50.0, 10.0], zoom_start=4)
        countries_with_devices = set(devices_df['country'].unique())
        
        def style_function(feature):
            country_name = feature['properties']['NAME']
            has_devices = country_name in countries_with_devices
            
            if not has_devices:
                return {
                    'fillColor': '#d3d3d3',
                    'color': '#808080',
                    'weight': 1,
                    'fillOpacity': 0.1,
                    'opacity': 0.3,
                    'dashArray': '3'
                }
            elif country_name == selected_country:
                return {
                    'fillColor': '#ffff00',
                    'color': 'black',
                    'weight': 2,
                    'fillOpacity': 0.3,
                    'opacity': 1
                }
            else:
                return {
                    'fillColor': '#90EE90',
                    'color': 'black',
                    'weight': 1,
                    'fillOpacity': 0.2,
                    'opacity': 1
                }

        def highlight_function(feature):
            country_name = feature['properties']['NAME']
            has_devices = country_name in countries_with_devices
            if has_devices:
                return {
                    'fillColor': '#0000ff',
                    'color': 'black',
                    'weight': 3,
                    'fillOpacity': 0.3,
                    'opacity': 1
                }
            return {
                'fillColor': '#d3d3d3',
                'color': '#808080',
                'weight': 1,
                'fillOpacity': 0.1,
                'opacity': 0.3
            }

        folium.GeoJson(
            world_data.__geo_interface__,
            style_function=style_function,
            highlight_function=highlight_function,
            tooltip=folium.GeoJsonTooltip(
                fields=['NAME'],
                aliases=[''],
                style=('background-color: white; color: black; font-family: courier new; font-size: 12px; padding: 10px;'),
                sticky=True
            )
        ).add_to(m)
        
        return m
    except Exception as e:
        st.error(f"Error creating map: {str(e)}")
        return folium.Map(location=[50.0, 10.0], zoom_start=4)

def filter_devices(devices_df, device_types, vendors):
    """Filter devices based on selected criteria"""
    if not device_types and not vendors:
        return devices_df
    
    filtered = devices_df.copy()
    if device_types:
        filtered = filtered[filtered['device_class'].isin(device_types)]
    if vendors:
        filtered = filtered[filtered['vendor'].isin(vendors)]
    return filtered

def create_distribution_charts(devices_df, backups):
    """Create distribution charts for devices"""
    try:
        # Device Type Distribution
        device_counts = devices_df['device_class'].value_counts()
        device_fig = px.pie(
            values=device_counts.values,
            names=device_counts.index,
            title='Device Type Distribution'
        )
        device_fig.update_traces(textposition='inside', textinfo='percent+label')
        
        # Vendor Distribution
        vendor_counts = devices_df['vendor'].value_counts()
        vendor_fig = px.pie(
            values=vendor_counts.values,
            names=vendor_counts.index,
            title='Vendor Distribution'
        )
        vendor_fig.update_traces(textposition='inside', textinfo='percent+label')
        
        # Backup Status
        backup_status = []
        for vendor in devices_df['vendor'].unique():
            vendor_devices = devices_df[devices_df['vendor'] == vendor]
            with_backup = sum(1 for _, device in vendor_devices.iterrows() 
                             if device['hostname'] in backups)
            without_backup = len(vendor_devices) - with_backup
            backup_status.append({
                'Vendor': vendor,
                'With Backup': with_backup,
                'Without Backup': without_backup
            })
        
        backup_df = pd.DataFrame(backup_status)
        backup_fig = go.Figure(data=[
            go.Bar(name='With Backup', x=backup_df['Vendor'], y=backup_df['With Backup']),
            go.Bar(name='Without Backup', x=backup_df['Vendor'], y=backup_df['Without Backup'])
        ])
        backup_fig.update_layout(title='Device Backup Status by Vendor', barmode='stack')
        
        return device_fig, vendor_fig, backup_fig
    except Exception as e:
        st.error(f"Error creating charts: {str(e)}")
        return None, None, None

def global_overview():
    """Main function for Global Overview view"""
    st.write("## Network Devices Global Overview")
    
    # Initialization of session state
    if 'selected_country' not in st.session_state:
        st.session_state.selected_country = None
    if 'device_types' not in st.session_state:
        st.session_state.device_types = []
    if 'vendors' not in st.session_state:
        st.session_state.vendors = []
    
    try:
        # Load all data
        world_data = load_world_data()
        devices = get_devices_data()
        if not devices:
            st.warning("No device data available")
            return
        
        devices_df = pd.DataFrame(devices).fillna({
            'country': 'Unknown',
            'device_class': 'Unknown',
            'vendor': 'Unknown',
            'hostname': 'Unknown',
            'ip': 'Unknown'
        })
        
        backups = get_backup_data()
        
        # Get unique values for filters
        DEVICE_TYPES = sorted([x for x in devices_df['device_class'].unique() if x and x != 'Unknown'])
        VENDORS = sorted([x for x in devices_df['vendor'].unique() if x and x != 'Unknown'])
        
    except Exception as e:
        st.error(f"Error during data loading and processing: {str(e)}")
        return

    # Map and controls layout
    col1, col2 = st.columns([7, 3])
    
    with col1:
        m = create_map(world_data, devices_df, st.session_state.selected_country)
        map_data = st_folium(m, height=500, width=None, key="map")
    
    with col2:
        available_countries = sorted([x for x in devices_df['country'].unique() if x and x != 'Unknown'])
        if available_countries:
            selected_index = (available_countries.index(st.session_state.selected_country) 
                            if st.session_state.selected_country in available_countries 
                            else 0)
            
            selected_country = st.selectbox(
                'Select country:',
                available_countries,
                index=selected_index
            )
            
            st.write("### Filters")
            device_types = st.multiselect(
                'Device Types:',
                DEVICE_TYPES,
                default=st.session_state.device_types
            )
            
            vendors = st.multiselect(
                'Vendors:',
                VENDORS,
                default=st.session_state.vendors
            )
            
            filtered_df = filter_devices(
                devices_df[devices_df['country'] == selected_country], 
                device_types, 
                vendors
            )
            
            total_devices = len(filtered_df)
            devices_with_backup = sum(1 for _, device in filtered_df.iterrows() 
                                    if device['hostname'] in backups)
            
            st.write("### Statistics")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Devices", total_devices)
            with col2:
                st.metric("Devices with Backup", devices_with_backup)
        else:
            st.warning("No countries with devices found in the data")
    
    # Handle map click
    if map_data and map_data.get('last_active_drawing'):
        properties = map_data['last_active_drawing'].get('properties')
        if properties:
            clicked_country = properties.get('NAME')
            if clicked_country in available_countries and clicked_country != st.session_state.selected_country:
                st.session_state.selected_country = clicked_country
                st.rerun()
    
    # Display charts and table
    if len(filtered_df) > 0:
        st.write("### Device Distribution")
        col1, col2, col3 = st.columns(3)
        
        device_fig, vendor_fig, backup_fig = create_distribution_charts(filtered_df, backups)
        
        with col1:
            st.plotly_chart(device_fig, use_container_width=True)
        with col2:
            st.plotly_chart(vendor_fig, use_container_width=True)
        with col3:
            st.plotly_chart(backup_fig, use_container_width=True)
        
        # Device table with backup status
        st.write("### Device List")
        display_df = filtered_df.copy()
        display_df['backup_status'] = display_df['hostname'].apply(
            lambda x: 'Available' if x in backups else 'Missing'
        )
        st.dataframe(
            display_df[['hostname', 'ip', 'device_class', 'vendor', 'backup_status']].style.apply(
                lambda x: ['background-color: #90EE90' if v == 'Available' else 'background-color: #FFB6C1' 
                          for v in x], subset=['backup_status']
            ),
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No devices match the selected filters.")
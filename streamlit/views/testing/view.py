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

def show():
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
        # Initialize Redis client
        REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379')
        redis_client = redis.Redis.from_url(REDIS_URL)

        # Load geographic data
        try:
            geo_file_path = os.path.join(os.getcwd(), 'data', 'geo', 'countries.geojson')
            world_data = gpd.read_file(geo_file_path)
        except Exception as e:
            st.error(f"Error loading geographic data: {str(e)}")
            world_data = None

        # Get devices data
        devices = []
        device_keys = redis_client.keys("device:*")
        
        for key in device_keys:
            device_data = redis_client.get(key)
            if device_data:
                device = json.loads(device_data)
                if device.get('country') is None:
                    device['country'] = 'Unknown'
                if device.get('device_class') is None:
                    device['device_class'] = 'Unknown'
                if device.get('vendor') is None:
                    device['vendor'] = 'Unknown'
                devices.append(device)
        
        if not devices:
            st.warning("No device data available")
            return

        # Get backup data
        try:
            backup_data = redis_client.get("s3_backups")
            if backup_data:
                backups = json.loads(backup_data)
            else:
                backups = {}
        except Exception as e:
            st.error(f"Error getting backup data: {str(e)}")
            backups = {}

        # Convert to DataFrame
        devices_df = pd.DataFrame(devices)
        devices_df = devices_df.fillna({
            'country': 'Unknown',
            'device_class': 'Unknown',
            'vendor': 'Unknown',
            'hostname': 'Unknown',
            'ip': 'Unknown'
        })

        # Get unique values for filters
        device_types = sorted([x for x in devices_df['device_class'].unique() if x and x != 'Unknown'])
        vendors = sorted([x for x in devices_df['vendor'].unique() if x and x != 'Unknown'])
        available_countries = sorted([x for x in devices_df['country'].unique() if x and x != 'Unknown'])

        # Layout: Map and controls
        col1, col2 = st.columns([7, 3])
        
        with col1:
            if world_data is not None:
                m = folium.Map(location=[50.0, 10.0], zoom_start=4)
                
                def style_function(feature):
                    country_name = feature['properties']['NAME']
                    has_devices = country_name in available_countries
                    
                    if country_name == st.session_state.selected_country:
                        return {
                            'fillColor': '#ffff00',
                            'color': 'black',
                            'weight': 2,
                            'fillOpacity': 0.3
                        }
                    elif has_devices:
                        return {
                            'fillColor': '#90EE90',
                            'color': 'black',
                            'weight': 1,
                            'fillOpacity': 0.2
                        }
                    else:
                        return {
                            'fillColor': '#d3d3d3',
                            'color': '#808080',
                            'weight': 1,
                            'fillOpacity': 0.1
                        }

                folium.GeoJson(
                    world_data.__geo_interface__,
                    style_function=style_function,
                    tooltip=folium.GeoJsonTooltip(
                        fields=['NAME'],
                        aliases=[''],
                        style='background-color: white; color: black; font-family: courier new; font-size: 12px; padding: 10px;'
                    )
                ).add_to(m)
                
                map_data = st_folium(m, height=500, width=None)
                
                # Handle map click
                if map_data and map_data.get('last_active_drawing'):
                    properties = map_data['last_active_drawing'].get('properties')
                    if properties:
                        clicked_country = properties.get('NAME')
                        if clicked_country in available_countries and clicked_country != st.session_state.selected_country:
                            st.session_state.selected_country = clicked_country
                            st.rerun()

        with col2:
            if available_countries:
                selected_index = (available_countries.index(st.session_state.selected_country) 
                                if st.session_state.selected_country in available_countries 
                                else 0)
                
                selected_country = st.selectbox(
                    'Select Country:',
                    available_countries,
                    index=selected_index
                )
                
                st.write("### Filters")
                selected_types = st.multiselect(
                    'Device Type:',
                    device_types,
                    default=st.session_state.device_types
                )
                
                selected_vendors = st.multiselect(
                    'Select Vendor:',
                    vendors,
                    default=st.session_state.vendors
                )
                
                # Filter data
                filtered_df = devices_df[devices_df['country'] == selected_country]
                if selected_types:
                    filtered_df = filtered_df[filtered_df['device_class'].isin(selected_types)]
                if selected_vendors:
                    filtered_df = filtered_df[filtered_df['vendor'].isin(selected_vendors)]
                
                # Statistics
                total_devices = len(filtered_df)
                devices_with_backup = sum(1 for _, device in filtered_df.iterrows() 
                                        if device['hostname'] in backups)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Devices", total_devices)
                with col2:
                    st.metric("With Backup", devices_with_backup)

        # Distribution charts
        if len(filtered_df) > 0:
            st.write("### Device Distribution")
            col1, col2 = st.columns(2)
            
            with col1:
                # Device Type Distribution
                device_counts = filtered_df['device_class'].value_counts()
                fig = px.pie(
                    values=device_counts.values,
                    names=device_counts.index,
                    title='Device Type Distribution'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Vendor Distribution
                vendor_counts = filtered_df['vendor'].value_counts()
                fig = px.pie(
                    values=vendor_counts.values,
                    names=vendor_counts.index,
                    title='Vendor Distribution'
                )
                st.plotly_chart(fig, use_container_width=True)
            
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
                
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return
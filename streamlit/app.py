import streamlit as st
import pandas as pd
import requests
import os
import json
import redis
from datetime import datetime
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource

# Initialize OpenTelemetry
if not trace.get_tracer_provider():
    resource = Resource.create({"service.name": "streamlit-app"})
    provider = TracerProvider(resource=resource)
    otlp_exporter = OTLPSpanExporter(
        endpoint=f"{os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://jaeger:4317')}"
    )
    span_processor = BatchSpanProcessor(otlp_exporter)
    provider.add_span_processor(span_processor)
    trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)

# FastAPI endpoint URL
FASTAPI_URL = os.getenv('FASTAPI_URL', 'http://fastapi:8000')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379')

# Initialize Redis client
redis_client = redis.Redis.from_url(REDIS_URL)

st.title("EasyNet Dashboard")

# Fetch data from FastAPI
@st.cache_data(ttl=30)  # Cache the data for 30 seconds
def fetch_data():
    with tracer.start_as_current_span("fetch_data"):
        response = requests.get(f"{FASTAPI_URL}/get_easynet_devices")
        if response.status_code == 200:
            return response.json()['devices']
        else:
            st.error(f"Failed to fetch data: {response.status_code}")
            return []

# Fetch devices backup status from FastAPI
@st.cache_data(ttl=30)
def fetch_devices_backup_status():
    with tracer.start_as_current_span("fetch_devices_backup_status"):
        response = requests.get(f"{FASTAPI_URL}/get_devices_backup_status")
        if response.status_code == 200:
            return response.json()['devices']
        else:
            st.error(f"Failed to fetch data: {response.status_code}")
            return []

# Main application logic
with tracer.start_as_current_span("main_app"):
    # Sidebar for navigation
    page = st.sidebar.selectbox("Choose a page", ["EasyNet Devices", "Backup Status"])

    if page == "EasyNet Devices":
        st.header("EasyNet Devices")

        with tracer.start_as_current_span("process_easynet_devices"):
            data = fetch_data()

            if data:
                # Convert the data to a pandas DataFrame
                df = pd.DataFrame(data)

                # Display the total number of devices
                st.write(f"Total number of devices: {len(df)}")

                # Define default columns
                default_columns = ['hostname', 'ip', 'vendor', 'country', 'site', 'device_class']

                # Ensure all default columns exist in the dataframe
                default_columns = [col for col in default_columns if col in df.columns]

                # Allow users to select columns to display, with default columns pre-selected
                all_columns = df.columns.tolist()
                selected_columns = st.multiselect(
                    "Select columns to display",
                    all_columns,
                    default=default_columns
                )

                # Display the table with selected columns
                if selected_columns:
                    st.dataframe(df[selected_columns])
                else:
                    st.warning("Please select at least one column to display the data.")

                # Add filters
                st.subheader("Filters")
                
                # Filter by vendor
                vendors = sorted([v for v in df['vendor'].unique() if pd.notna(v)])
                selected_vendor = st.multiselect("Filter by vendor", vendors)
                
                # Filter by country
                countries = sorted([c for c in df['country'].unique() if pd.notna(c)])
                selected_country = st.multiselect("Filter by country", countries)

                # Apply filters
                filtered_df = df.copy()
                if selected_vendor:
                    filtered_df = filtered_df[filtered_df['vendor'].isin(selected_vendor)]
                if selected_country:
                    filtered_df = filtered_df[filtered_df['country'].isin(selected_country)]

                # Display filtered results
                st.subheader("Filtered Results")
                if selected_columns:
                    st.dataframe(filtered_df[selected_columns])
                else:
                    st.dataframe(filtered_df)

                # Add a download button for filtered results
                csv = filtered_df.to_csv(index=False)
                st.download_button(
                    label="Download filtered data as CSV",
                    data=csv,
                    file_name="filtered_easynet_devices.csv",
                    mime="text/csv",
                )

                # Display warning for missing data
                if df['vendor'].isna().any() or df['country'].isna().any():
                    st.warning("Some devices have missing vendor or country information.")
            else:
                st.write("No data available")

    elif page == "Backup Status":
        st.header("Backup Status")
        
        with tracer.start_as_current_span("process_backup_status"):
            devices_data = fetch_devices_backup_status()
            
            if devices_data:
                # Convert the data to a pandas DataFrame
                df = pd.DataFrame(devices_data)
                
                # Display the total number of devices
                st.write(f"Total number of devices: {len(df)}")
                
                # Display the table
                st.dataframe(df)
                
                # Add filters
                st.subheader("Filters")
                
                # Filter by vendor
                vendors = sorted(df['vendor'].unique())
                selected_vendor = st.multiselect("Filter by vendor", vendors)
                
                # Filter by device class
                device_classes = sorted(df['device_class'].unique())
                selected_device_class = st.multiselect("Filter by device class", device_classes)
                
                # Filter by backup status
                backup_status = st.radio("Filter by backup status", ["All", "With Backup", "Without Backup"])
                
                # Filter by schema status
                schema_status = st.radio("Filter by schema status", ["All", "Valid Schema", "Invalid Schema", "No Schema"])
                
                # Apply filters
                filtered_df = df.copy()
                if selected_vendor:
                    filtered_df = filtered_df[filtered_df['vendor'].isin(selected_vendor)]
                if selected_device_class:
                    filtered_df = filtered_df[filtered_df['device_class'].isin(selected_device_class)]
                if backup_status == "With Backup":
                    filtered_df = filtered_df[filtered_df['backup_json'] == True]
                elif backup_status == "Without Backup":
                    filtered_df = filtered_df[filtered_df['backup_json'] == False]
                if schema_status == "Valid Schema":
                    filtered_df = filtered_df[filtered_df['valid_schema'] == True]
                elif schema_status == "Invalid Schema":
                    filtered_df = filtered_df[filtered_df['valid_schema'] == False]
                elif schema_status == "No Schema":
                    filtered_df = filtered_df[filtered_df['schema'] == False]
                
                # Display filtered results
                st.subheader("Filtered Results")
                st.dataframe(filtered_df)
                
                # Add a download button for filtered results
                csv = filtered_df.to_csv(index=False)
                st.download_button(
                    label="Download filtered data as CSV",
                    data=csv,
                    file_name="filtered_devices_backup_status.csv",
                    mime="text/csv",
                )
            else:
                st.write("No data available")

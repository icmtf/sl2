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

# Fetch S3 backups data from Redis
def fetch_s3_data():
    with tracer.start_as_current_span("fetch_s3_data"):
        s3_list_data = redis_client.get("s3_list")
        if s3_list_data:
            return json.loads(s3_list_data)
        return []

# Main application logic
with tracer.start_as_current_span("main_app"):
    # Sidebar for navigation
    page = st.sidebar.selectbox("Choose a page", ["EasyNet Devices", "S3 Backups"])

    if page == "EasyNet Devices":
        st.header("EasyNet Devices")

        with tracer.start_as_current_span("process_easynet_devices"):
            data = fetch_data()
            s3_data = fetch_s3_data()

            if data:
                # Convert the data to a pandas DataFrame
                df = pd.DataFrame(data)

                # Add 'Facts' column based on S3 data
                facts_status = {
                    path['name'].split('/')[2]: True 
                    for path in s3_data 
                    if path['name'].startswith('backups/') and path['name'].endswith('facts.json')
                }
                df['Facts'] = df['hostname'].map(lambda x: facts_status.get(x, False))

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
                
                # Filter by Facts status
                facts_status = st.radio("Filter by Facts status", ["All", "With Facts", "Without Facts"])

                # Apply filters
                filtered_df = df.copy()
                if selected_vendor:
                    filtered_df = filtered_df[filtered_df['vendor'].isin(selected_vendor)]
                if selected_country:
                    filtered_df = filtered_df[filtered_df['country'].isin(selected_country)]
                if facts_status == "With Facts":
                    filtered_df = filtered_df[filtered_df['Facts'] == True]
                elif facts_status == "Without Facts":
                    filtered_df = filtered_df[filtered_df['Facts'] == False]

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

    elif page == "S3 Backups":
        st.header("S3 Backups")
        
        with tracer.start_as_current_span("process_s3_backups"):
            s3_data = fetch_s3_data()
            
            if s3_data:
                # Convert the list of dictionaries to a DataFrame
                df = pd.DataFrame(s3_data)
                
                # Display the total number of backup files
                st.write(f"Total number of backup files: {len(df)}")
                
                # Display the table
                st.dataframe(df)
                
                # Add filters
                st.subheader("Filters")
                
                # Filter by vendor (first subfolder after 'backups/')
                vendors = sorted(set(path['name'].split('/')[1] for path in s3_data if len(path['name'].split('/')) > 2))
                selected_vendor = st.selectbox("Filter by vendor", ['All'] + vendors)
                
                # Filter by device (second subfolder, if exists)
                devices = sorted(set(path['name'].split('/')[2] for path in s3_data if len(path['name'].split('/')) > 3))
                selected_device = st.selectbox("Filter by device", ['All'] + devices)
                
                # Filter by file type
                file_types = sorted(set(path['name'].split('.')[-1] for path in s3_data if '.' in path['name']))
                selected_file_type = st.selectbox("Filter by file type", ['All'] + file_types)
                
                # Apply filters
                filtered_data = s3_data
                if selected_vendor != 'All':
                    filtered_data = [path for path in filtered_data if path['name'].split('/')[1] == selected_vendor]
                if selected_device != 'All':
                    filtered_data = [path for path in filtered_data if len(path['name'].split('/')) > 3 and path['name'].split('/')[2] == selected_device]
                if selected_file_type != 'All':
                    filtered_data = [path for path in filtered_data if path['name'].endswith(f".{selected_file_type}")]
                
                # Display filtered results
                st.subheader("Filtered Results")
                filtered_df = pd.DataFrame(filtered_data)
                st.dataframe(filtered_df)
                
                # Add a download button for filtered results
                csv = filtered_df.to_csv(index=False)
                st.download_button(
                    label="Download filtered S3 backups list as CSV",
                    data=csv,
                    file_name="filtered_s3_backups.csv",
                    mime="text/csv",
                )
            else:
                st.write("No S3 backups data available")

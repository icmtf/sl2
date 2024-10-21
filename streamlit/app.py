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
from pandas.api.types import (
    is_categorical_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
    is_object_dtype,
)

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

def filter_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    modify = st.checkbox("Add filters")
    if not modify:
        return df

    df = df.copy()

    # Try to convert datetimes into a standard format (datetime, no timezone)
    for col in df.columns:
        if is_object_dtype(df[col]):
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception:
                pass
        if is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.tz_localize(None)

    modification_container = st.container()

    with modification_container:
        to_filter_columns = st.multiselect("Filter dataframe on", df.columns)
        for column in to_filter_columns:
            left, right = st.columns((1, 20))
            left.write("↳")
            # Check if the column contains lists
            if df[column].apply(lambda x: isinstance(x, list)).any():
                # For columns containing lists, we'll use a text input for filtering
                user_text_input = right.text_input(
                    f"Search in {column} (comma-separated values)",
                )
                if user_text_input:
                    search_terms = [term.strip() for term in user_text_input.split(',')]
                    df = df[df[column].apply(lambda x: any(term in str(x) for term in search_terms))]
            elif is_categorical_dtype(df[column]) or df[column].nunique() < 10:
                user_cat_input = right.multiselect(
                    f"Values for {column}",
                    df[column].unique(),
                    default=list(df[column].unique()),
                )
                df = df[df[column].isin(user_cat_input)]
            elif is_numeric_dtype(df[column]):
                _min = float(df[column].min())
                _max = float(df[column].max())
                step = (_max - _min) / 100
                user_num_input = right.slider(
                    f"Values for {column}",
                    _min,
                    _max,
                    (_min, _max),
                    step=step,
                )
                df = df[df[column].between(*user_num_input)]
            elif is_datetime64_any_dtype(df[column]):
                user_date_input = right.date_input(
                    f"Values for {column}",
                    value=(
                        df[column].min(),
                        df[column].max(),
                    ),
                )
                if len(user_date_input) == 2:
                    user_date_input = tuple(map(pd.to_datetime, user_date_input))
                    start_date, end_date = user_date_input
                    df = df.loc[df[column].between(start_date, end_date)]
            else:
                user_text_input = right.text_input(
                    f"Substring or regex in {column}",
                )
                if user_text_input:
                    df = df[df[column].astype(str).str.contains(user_text_input)]
    return df

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

                # Use the new filter_dataframe function
                filtered_df = filter_dataframe(df)

                # Display the filtered dataframe
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
                
                # Use the new filter_dataframe function
                filtered_df = filter_dataframe(df)
                
                # Display the filtered dataframe
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
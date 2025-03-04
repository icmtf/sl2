import streamlit as st
import json
import redis
import os
import pandas as pd
import plotly.express as px

def get_arp_data():
    """Get ARP data from Redis"""
    redis_client = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379'))
    data = redis_client.get("arp_data")
    if data:
        return json.loads(data)
    return []

def show():
    st.title("MAC Table")
    
    # Get data
    data = get_arp_data()
    
    if not data:
        st.warning("No ARP data available")
        return
    
    # Convert data to DataFrame
    df = pd.DataFrame(data)
    
    # Prepare data for chart - count entries for each device
    device_counts = df['device'].value_counts().reset_index()
    device_counts.columns = ['Device', 'Entries count']
    
    # Create two columns side by side
    col1, col2 = st.columns(2)
    
    with col1:
        # Create bar chart
        fig = px.bar(
            device_counts,
            x='Device',
            y='Entries count',
            title='ARP Entries per Device',
        )
        
        # Customize chart appearance
        fig.update_layout(
            xaxis_tickangle=-45,
            xaxis_title="Device",
            yaxis_title="Number of ARP entries",
            height=400,
            margin=dict(t=30, b=0)  # Reduce margins
        )
        
        # Display chart
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Number of ARP entries")
        st.dataframe(
            device_counts,
            hide_index=True,
            use_container_width=True
        )
    
    # Display main ARP table with full width
    st.markdown("### ARP Entries")
    st.dataframe(
        data=df,
        column_config={
            "device": "Device",
            "first_address": "IP/MAC",
            "second_address": "IP/MAC",
            "interface": "Interface"
        },
        hide_index=True,
        use_container_width=True
    )
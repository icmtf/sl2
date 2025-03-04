import streamlit as st
import pandas as pd
import json
import redis
import plotly.express as px
from datetime import datetime
import os

def get_remote_access_data():
    """Get data from Redis"""
    redis_client = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379'))
    data = redis_client.get("remote_access_data")
    if data:
        return json.loads(data)
    return []

def format_duration(duration_str):
    """Format session duration"""
    if duration_str is None:
        return ''
    return duration_str.replace('h:', 'h ').replace('m:', 'm ').replace('s', 's')

def create_pie_chart(df, column, title):
    """Create a pie chart for the given column showing only top 5 values"""
    value_counts = df[column].value_counts()
    
    # If we have more than 5 items, group the rest as "Others"
    if len(value_counts) > 5:
        top_5 = value_counts.head(5)
        others_sum = value_counts[5:].sum()
        
        # Create new series with top 5 and Others
        values = pd.concat([top_5, pd.Series({'Others': others_sum})])
    else:
        values = value_counts
    
    fig = px.pie(
        values=values.values,
        names=values.index,
        title=title,
        hole=0.3
    )
    
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5)
    )
    
    return fig

def get_unique_sorted_values(df, column):
    """Get unique values from column, ignoring None"""
    return sorted([x for x in df[column].unique() if x is not None])

def show():
    st.title("VPN Sessions")
    
    # Get data
    data = get_remote_access_data()
    
    if not data:
        st.warning("No remote access data available")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    # Add filtering in new order
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        policies = get_unique_sorted_values(df, 'GrpPolicy')
        selected_policy = st.multiselect('Filter by Policy', policies)
    
    with col2:
        countries = get_unique_sorted_values(df, 'Country')
        selected_country = st.multiselect('Filter by Country', countries)
        
    with col3:
        as_orgs = get_unique_sorted_values(df, 'AS_Org')
        selected_as_org = st.multiselect('Filter by AS Organization', as_orgs)
        
    with col4:
        gateways = get_unique_sorted_values(df, 'Gateway')
        selected_gateway = st.multiselect('Filter by Gateway', gateways)
    
    # Apply filters
    filtered_df = df.copy()
    if selected_policy:
        filtered_df = filtered_df[filtered_df['GrpPolicy'].isin(selected_policy)]
    if selected_country:
        filtered_df = filtered_df[filtered_df['Country'].isin(selected_country)]
    if selected_as_org:
        filtered_df = filtered_df[filtered_df['AS_Org'].isin(selected_as_org)]
    if selected_gateway:
        filtered_df = filtered_df[filtered_df['Gateway'].isin(selected_gateway)]
    
    # Display statistics
    st.subheader("Session Statistics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Active Sessions", len(filtered_df))
    col2.metric("Unique Countries", len(filtered_df['Country'].unique()))
    col3.metric("Unique ASNs", len(filtered_df['ASN'].unique()))
    col4.metric("Unique Policies", len(filtered_df['GrpPolicy'].unique()))
    
    # Add pie charts
    st.subheader("Session Distribution")
    
    # Display charts in two rows of two
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        # Chart for GrpPolicy
        st.plotly_chart(
            create_pie_chart(filtered_df, 'GrpPolicy', 'Distribution by Group Policy'),
            use_container_width=True
        )
        
        # Chart for Country
        st.plotly_chart(
            create_pie_chart(filtered_df, 'Country', 'Distribution by Country'),
            use_container_width=True
        )
        
    with chart_col2:
        # Chart for AS_Org
        st.plotly_chart(
            create_pie_chart(filtered_df, 'AS_Org', 'Distribution by AS Organization'),
            use_container_width=True
        )
        
        # Chart for Gateway
        st.plotly_chart(
            create_pie_chart(filtered_df, 'Gateway', 'Distribution by Gateway'),
            use_container_width=True
        )
    
    # Format columns
    filtered_df['Duration'] = filtered_df['Duration'].apply(format_duration)
    
    # Display table with additional columns, without AS_Org
    st.subheader("Active Sessions")
    st.dataframe(
        filtered_df[[
            'Username', 'IP_Pub', 'IP_Priv', 'GrpPolicy', 
            'Login_Time', 'Duration', 'Session_ID', 'ASN',
            'Country', 'Gateway'
        ]],
        hide_index=True
    )
import streamlit as st
import pandas as pd
import json
import redis
import plotly.express as px
from datetime import datetime
import os

def get_remote_access_data():
    """Pobierz dane z Redis"""
    redis_client = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379'))
    data = redis_client.get("remote_access_data")
    if data:
        return json.loads(data)
    return []

def format_duration(duration_str):
    """Formatuj czas trwania sesji"""
    return duration_str.replace('h:', 'h ').replace('m:', 'm ').replace('s', 's')

def create_pie_chart(df, column, title):
    """Twórz wykres kołowy dla danej kolumny"""
    value_counts = df[column].value_counts()
    fig = px.pie(
        values=value_counts.values,
        names=value_counts.index,
        title=title,
        hole=0.3
    )
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5)
    )
    return fig

def get_unique_sorted_values(df, column):
    """Pobierz unikalne wartości z kolumny, ignorując None"""
    return sorted([x for x in df[column].unique() if x is not None])

def show():
    st.title("Remote Access Status")
    
    # Pobierz dane
    data = get_remote_access_data()
    
    if not data:
        st.warning("No remote access data available")
        return
    
    # Konwertuj do DataFrame
    df = pd.DataFrame(data)
    
    # Dodaj filtrowanie w nowej kolejności
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
    
    # Zastosuj filtry
    filtered_df = df.copy()
    if selected_policy:
        filtered_df = filtered_df[filtered_df['GrpPolicy'].isin(selected_policy)]
    if selected_country:
        filtered_df = filtered_df[filtered_df['Country'].isin(selected_country)]
    if selected_as_org:
        filtered_df = filtered_df[filtered_df['AS_Org'].isin(selected_as_org)]
    if selected_gateway:
        filtered_df = filtered_df[filtered_df['Gateway'].isin(selected_gateway)]
    
    # Wyświetl statystyki
    st.subheader("Session Statistics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Active Sessions", len(filtered_df))
    col2.metric("Unique Countries", len(filtered_df['Country'].unique()))
    col3.metric("Unique ASNs", len(filtered_df['ASN'].unique()))
    col4.metric("Unique Policies", len(filtered_df['GrpPolicy'].unique()))
    
    # Dodaj wykresy kołowe
    st.subheader("Session Distribution")
    
    # Wyświetl wykresy w dwóch rzędach po dwa
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        # Wykres dla GrpPolicy
        st.plotly_chart(
            create_pie_chart(filtered_df, 'GrpPolicy', 'Distribution by Group Policy'),
            use_container_width=True
        )
        
        # Wykres dla Country
        st.plotly_chart(
            create_pie_chart(filtered_df, 'Country', 'Distribution by Country'),
            use_container_width=True
        )
        
    with chart_col2:
        # Wykres dla AS_Org
        st.plotly_chart(
            create_pie_chart(filtered_df, 'AS_Org', 'Distribution by AS Organization'),
            use_container_width=True
        )
        
        # Wykres dla Gateway
        st.plotly_chart(
            create_pie_chart(filtered_df, 'Gateway', 'Distribution by Gateway'),
            use_container_width=True
        )
    
    # Formatuj kolumny
    filtered_df['Duration'] = filtered_df['Duration'].apply(format_duration)
    
    # Wyświetl tabelę z dodatkowymi kolumnami, bez AS_Org
    st.subheader("Active Sessions")
    st.dataframe(
        filtered_df[[
            'Username', 'IP_Pub', 'IP_Priv', 'GrpPolicy', 
            'Login_Time', 'Duration', 'Session_ID', 'ASN',
            'Country', 'Gateway'
        ]],
        hide_index=True
    )
import streamlit as st
import json
import redis
import os

def get_arp_data():
    """Pobierz dane ARP z Redis"""
    redis_client = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379'))
    data = redis_client.get("arp_data")
    if data:
        return json.loads(data)
    return []

def show():
    st.title("ARP Table")
    
    # Pobierz dane
    data = get_arp_data()
    
    if not data:
        st.warning("No ARP data available")
        return
    
    # Wyświetl tabelę
    st.dataframe(
        data=data,
        column_config={
            "device": "Device",
            "first_address": "IP/MAC",
            "second_address": "IP/MAC",
            "interface": "Interface"
        },
        hide_index=True
    )
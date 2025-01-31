import streamlit as st
import redis
import json
import pandas as pd
import re

def format_validation_message(message):
    """Wyświetl wiadomość jako blok kodu"""
    try:
        # Remove quotes from message
        if isinstance(message, str):
            message = message.strip('"')
        return message
    except Exception as e:
        print(f"Error formatting message: {str(e)}")
        return message

# Main view
st.title("Fortinet Validation Status")

try:
    redis_client = redis.Redis(
        host='redis',
        port=6379,
        decode_responses=True
    )
    
    validation_keys = redis_client.keys('s3_validation:*')
    
    if not validation_keys:
        st.warning("No validation data found in Redis")
        st.stop()
        
    fortinet_data = []
    fortinet_details = {}
    
    for key in validation_keys:
        data = redis_client.hgetall(key)
        if data.get('vendor') == 'Fortinet':
            validation_data = json.loads(data.get('validation_data', '{}'))
            device_id = key.split(':')[1]
            
            row_data = {
                'Device': device_id,
                'Last Check': validation_data.get('date', '')
            }
            
            failed_checks = {}
            
            # Przetwarzanie nowej struktury danych
            config_validation = validation_data.get('config_validation', {})
            for check_name, check_data in config_validation.items():
                if isinstance(check_data, dict):
                    status = check_data.get('status')
                    if status:
                        row_data[check_name] = status
                        if status == 'KO':
                            if check_name == 'snmp':
                                # Special handling for SNMP
                                message = "Community: " + check_data.get('message_community', '').strip('"')
                                message += "\nSysinfo: " + check_data.get('message_sysinfo', '').strip('"')
                                failed_checks[check_name] = message
                            else:
                                failed_checks[check_name] = check_data.get('message', '')
            
            row_data['Details'] = False
            fortinet_data.append(row_data)
            fortinet_details[device_id] = failed_checks
    
    if not fortinet_data:
        st.warning("No Fortinet devices found in validation data")
        st.stop()
        
    df = pd.DataFrame(fortinet_data)
    
    status_columns = sorted([col for col in df.columns if col not in ['Device', 'Last Check', 'Details']])
    columns = ['Device', 'Last Check'] + status_columns + ['Details']
    df = df[columns]
    
    def color_status(val):
        if val == 'OK':
            return 'background-color: #90EE90'
        elif val == 'KO':
            return 'background-color: #FFB6C1'
        return ''
        
    styled_df = df.style.map(color_status, subset=status_columns)
        
    edited_df = st.data_editor(
        styled_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Details": st.column_config.CheckboxColumn(
                "Details",
                help="Show validation details",
                default=False,
            )
        },
        disabled=["Device", "Last Check"] + status_columns
    )
    
    # Show details for selected devices
    for index, row in edited_df.iterrows():
        if row['Details']:
            device_id = row['Device']
            failed_checks = fortinet_details[device_id]
            
            st.write(f"### Details for {device_id}")
            
            if not failed_checks:
                st.success("All validation checks for this device are OK.")
            else:
                for check_name, message in failed_checks.items():
                    st.markdown(f"## **{check_name}**")
                    st.code(format_validation_message(message))
            
            st.markdown("---")
    
except redis.ConnectionError:
    st.error("Could not connect to Redis. Please check if Redis service is running.")
except Exception as e:
    st.error(f"An error occurred: {str(e)}")

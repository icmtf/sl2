import streamlit as st
import redis
import json
import pandas as pd

def load_validation_data():
    """Load validation data from the new Redis structure"""
    try:
        checkpoint_data = []
        checkpoint_details = {}
        device_keys = redis_client.keys('device:*')
        
        if not device_keys:
            return [], {}
        
        for key in device_keys:
            device_data = redis_client.get(key)
            if device_data:
                device_json = json.loads(device_data)
                
                # Get hostname from easynet or key
                hostname = None
                if "easynet" in device_json and isinstance(device_json["easynet"], dict):
                    hostname = device_json["easynet"].get("hostname")
                
                if not hostname:
                    hostname = key.split(':')[1]
                
                # Check if device has validation data and is CheckPoint
                if "validation" in device_json:
                    validation_data = device_json["validation"]
                    if not validation_data.get('vendor') == 'CheckPoint':
                        continue
                        
                    row_data = {
                        'Device': hostname,
                        'Last Check': validation_data.get('date', '')
                    }
                    
                    failed_checks = {}
                    
                    # Process validation data
                    validation_data_obj = validation_data.get('validation_data', {})
                    config_validation = validation_data_obj.get('config_validation', {})
                    
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
                    checkpoint_data.append(row_data)
                    checkpoint_details[hostname] = failed_checks
        
        return checkpoint_data, checkpoint_details
    except Exception as e:
        st.error(f"Error loading validation data: {str(e)}")
        return [], {}

def format_validation_message(message):
    """Display message as a code block"""
    try:
        # Remove quotes from message
        if isinstance(message, str):
            message = message.strip('"')
        return message
    except Exception as e:
        print(f"Error formatting message: {str(e)}")
        return message

# Main view
st.title("CheckPoint Validation Status")

try:
    redis_client = redis.Redis(
        host='redis',
        port=6379,
        decode_responses=True
    )
    
    # Use the new load_validation_data function instead of direct Redis access
    checkpoint_data, checkpoint_details = load_validation_data()
    
    if not checkpoint_data:
        st.warning("No CheckPoint devices found in validation data")
        st.stop()
        
    df = pd.DataFrame(checkpoint_data)
    
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
            failed_checks = checkpoint_details[device_id]
            
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

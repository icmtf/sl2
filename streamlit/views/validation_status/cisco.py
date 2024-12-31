import streamlit as st
import redis
import json
import pandas as pd
import re

def format_validation_message(message):
    # Split into info lines and JSON.
    lines = message.split('\n')
    info_line = lines[0]  # "Validation errors were found."
    
    # Separate JSON from the text.
    json_matches = re.findall(r'\[(.*?)\]', message)
    if json_matches:
        try:
            # Take the first found JSON and try to parse it.
            json_str = json_matches[0]
            # Change single quotes to double quotes for valid JSON
            json_str = json_str.replace("'", '"')
            # Parse and format JSON.
            json_data = json.loads('[' + json_str + ']')
            formatted_json = json.dumps(json_data, indent=2)
            
            # Return the message with the formatted JSON.
            return f"{info_line}\n\nConfiguration:\n{formatted_json}"
        except json.JSONDecodeError:
            return message
    return message

def page1_view():
    st.title("Cisco Validation Status")
    
    try:
        redis_client = redis.Redis(
            host='redis',
            port=6379,
            decode_responses=True
        )
        
        validation_keys = redis_client.keys('s3_validation:*')
        
        if not validation_keys:
            st.warning("No validation data found in Redis")
            return
            
        cisco_data = []
        cisco_details = {}
        
        for key in validation_keys:
            data = redis_client.hgetall(key)
            if data.get('vendor') == 'Cisco':
                validation_data = json.loads(data.get('validation_data', '{}'))
                device_id = key.split(':')[1]
                
                row_data = {
                    'Device': device_id,
                    'Last Check': validation_data.get('date', '')
                }
                
                failed_checks = {}
                
                for check_name, check_data in validation_data.items():
                    if isinstance(check_data, dict):
                        if 'status' in check_data:
                            row_data[check_name] = check_data['status']
                            if check_data['status'] == 'KO':
                                failed_checks[check_name] = check_data['message']
                
                row_data['Details'] = False
                cisco_data.append(row_data)
                cisco_details[device_id] = failed_checks
        
        if not cisco_data:
            st.warning("No Cisco devices found in validation data")
            return
            
        df = pd.DataFrame(cisco_data)
        
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
                failed_checks = cisco_details[device_id]
                
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

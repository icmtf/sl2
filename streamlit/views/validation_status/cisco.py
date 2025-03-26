import streamlit as st
import redis
import json
import pandas as pd

# Constants
REDIS_HOST = 'redis'
REDIS_PORT = 6379

# Helper functions
def format_validation_message(message):
    """Format a validation message by removing extra quotes
    
    Args:
        message (str): The validation message to format
        
    Returns:
        str: Formatted message with quotes removed
    """
    try:
        if isinstance(message, str):
            message = message.strip('"')
        return message
    except Exception as e:
        print(f"Error formatting message: {str(e)}")
        return message


def color_status(val):
    """Apply color formatting to status values in the data table
    
    Args:
        val: The cell value to format
        
    Returns:
        str: CSS background-color style based on status value
    """
    if val == 'OK':
        return 'background-color: #90EE90'  # Light green
    elif val == 'KO':
        return 'background-color: #FFB6C1'  # Light red
    return ''

def load_validation_data():
    """Load validation data for Cisco devices from Redis
    
    Retrieves and processes all Cisco device validation data from Redis,
    including device details and validation results.
    
    Returns:
        tuple: (cisco_data, cisco_details, device_info)
            - cisco_data: List of device data for the table display
            - cisco_details: Dictionary of validation failures by hostname
            - device_info: Dictionary of complete device information
    """
    try:
        cisco_data = []
        cisco_details = {}
        device_info = {}  # Store full device info for expandable details
        device_keys = redis_client.keys('device:*')
        
        if not device_keys:
            return [], {}, {}
        
        for key in device_keys:
            device_data = redis_client.get(key)
            if device_data:
                device_json = json.loads(device_data)
                
                # Get hostname from easynet
                hostname = None
                if "easynet" in device_json and isinstance(device_json["easynet"], dict):
                    hostname = device_json["easynet"].get("hostname")
                    # Store full device info for later use in expander
                    device_info[hostname] = device_json["easynet"]
                
                # Skip devices with no hostname in easynet data
                if not hostname:
                    continue
                
                # Check if device has config_validation data and is Cisco
                if "config_validation" in device_json and isinstance(device_json["config_validation"], dict):
                    validation_data = device_json["config_validation"]
                    
                    # Check if it's a Cisco device
                    if validation_data.get('vendor') != 'Cisco':
                        continue
                    
                    # Store full validation data for JSON popover
                    if hostname in device_info:
                        device_info[hostname]["config_validation"] = validation_data
                    
                    row_data = {
                        'Device': hostname,
                        'Last Check': validation_data.get('date', '')
                    }
                    
                    failed_checks = {}
                    
                    # Process validation data - note the config_validation is nested one level deeper now
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
                    cisco_data.append(row_data)
                    cisco_details[hostname] = failed_checks
        
        return cisco_data, cisco_details, device_info
    except Exception as e:
        st.error(f"Error loading validation data: {str(e)}")
        return [], {}, {}
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

def display_device_details(hostname, device_info, cisco_details):
    """Display detailed device information with validation status in an expander
    
    Creates an expandable UI component showing device details, validation status,
    and a JSON viewer for the complete config validation data.
    
    Args:
        hostname (str): Device hostname to display details for
        device_info (dict): Dictionary with complete device information
        cisco_details (dict): Dictionary with validation failures by hostname
    """
    device = device_info.get(hostname, {})
    failed_checks = cisco_details.get(hostname, {})

    with st.expander(f"🔍 {hostname} ({device.get('ip', 'N/A')})", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("##### Device Details")
            st.write(f"**Hostname:** {hostname}")
            st.write(f"**IP Address:** {device.get('ip', 'N/A')}")
            st.write(f"**Country:** {device.get('country', 'N/A')}")
            st.write(f"**Device Class:** {device.get('device_class', 'N/A')}")
            st.write(f"**Vendor:** {device.get('vendor', 'N/A')}")
            
            # Add popover button for config_validation.json
            if "config_validation" in device:
                with st.popover("🧩 config_validation.json"):
                    st.json(device["config_validation"])
            else:
                st.button("🧩 config_validation.json", disabled=True, help="No config_validation.json available")
        
        with col2:
            st.write("##### Validation Status Details")
            
            if not failed_checks:
                st.success("All validation checks for this device are OK.")
            else:
                for check_name, message in failed_checks.items():
                    st.markdown(f"**{check_name}**:")
                    st.code(format_validation_message(message), language="text")
            
            # Show Last Check date if available
            if "config_validation" in device:
                last_update = device["config_validation"].get('date', 'N/A')
                st.write(f"**Last Updated:** {last_update}")


# Main view
st.title("Cisco Validation Status")

try:
    # Initialize Redis connection
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True
    )
    
    # Load and process Cisco validation data
    cisco_data, cisco_details, device_info = load_validation_data()
    
    if not cisco_data:
        st.warning("No Cisco devices found in validation data")
        st.stop()
    
    # Create DataFrame for display
    df = pd.DataFrame(cisco_data)
    
    # Configure columns for display
    status_columns = sorted([col for col in df.columns if col not in ['Device', 'Last Check', 'Details']])
    columns = ['Device', 'Last Check'] + status_columns + ['Details']
    df = df[columns]  # Reorder columns
    
    # Apply color formatting based on status
    styled_df = df.style.map(color_status, subset=status_columns)
    
    # Display the data table with editor for Details checkboxes
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
            display_device_details(device_id, device_info, cisco_details)

except redis.ConnectionError:
    st.error("Could not connect to Redis. Please check if Redis service is running.")
except Exception as e:
    st.error(f"An error occurred: {str(e)}")

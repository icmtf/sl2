import streamlit as st
from streamlit_dynamic_filters import DynamicFilters
import pandas as pd
from views.validation_status.utils.redis import load_devices_data, load_compliance_data
from views.validation_status.utils.data import get_compliance_status, get_compliance_date, get_global_status
from views.validation_status.utils.formatter import highlight_status

st.title("Compliance Status")
devices = load_devices_data()
compliance_data = load_compliance_data()

if not devices:
    st.warning("No devices data available")

else:
    # Initiating Dataframe with devices
    df = pd.DataFrame(devices)

    # Processing and adding Global Status and Date column
    compliance_items = ["AAA", "SNMP", "Syslog", "NTP"]
    for item in compliance_items:
        df[item] = df["hostname"].apply(lambda x: get_compliance_status(x, compliance_data, "validation_data", item))
    df["Global Status"] = df.apply(get_global_status, axis=1, col_list=compliance_items)
    df["date"] = df["hostname"].apply(lambda x: get_compliance_date(x, compliance_data, "validation_data"))

    # Limit the dataframe to the columns to be displayed
    compliance_items.append("Global Status")
    display_cols = ["hostname", "date", "country", "device_class", "vendor"] + compliance_items
    df = df[display_cols]
    df.fillna("No Data", inplace=True)

    # Setup the filters
    filtering_col = ["country", "device_class", "vendor"] + compliance_items
    config_dynamic_filters = DynamicFilters(df, filters=filtering_col, filters_name="config_validation_filters")

    # Register the filtered dataframe
    filtered_config_df = config_dynamic_filters.filter_df()

    # Calculate filtered sum
    device_total = len(df)
    selected = len(filtered_config_df)
    ratio = f"{selected / device_total * 100: .1f}%"
    device_OK = filtered_config_df["Global Status"].value_counts().get("OK", 0)
    device_KO = filtered_config_df["Global Status"].value_counts().get("KO", 0)
    device_NA = filtered_config_df["Global Status"].value_counts().get("NA", 0)

    # Create 2 columns: tiny one for the summary and a big one (5x) for the filter
    col1, col2 = st.columns([1,5])

    # Sum-up table in the left column
    with col1:
        df_sum = pd.DataFrame({"Status": ["OK", "KO", "NA", "Selected","Total"], "Device count": [device_OK, device_KO, device_NA, f"{selected} ({ratio})", device_total] })
        st.write("Summary")
        st.dataframe(df_sum, hide_index=True)
    # Displaying filters and the dataframe after filters are applied in the 2nd col
    with col2:
        config_dynamic_filters.display_filters(location="columns", num_columns=3)

    st.dataframe(
        filtered_config_df.style.applymap(highlight_status, subset=compliance_items),
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        key="config_row_selected",
    )

    if st.session_state["config_row_selected"]["selection"]["rows"] != []:
        row_index = st.session_state["config_row_selected"]["selection"]["rows"][0]
        host = filtered_config_df.iloc[row_index]
        hostname = host.get("hostname")
        if hostname:
            compliance_info = compliance_data.get(hostname, {})
            if "validation_data" in compliance_info:
                data = compliance_info.get("validation_data", {})
            else:
                st.warning("Cant parse compliance info")

            with st.popover("JSON config validaton results"):
                st.write(f"Device selected is {hostname}")
                st.json(data)
        else:
            st.warning("Cant find hostname in compliance result")
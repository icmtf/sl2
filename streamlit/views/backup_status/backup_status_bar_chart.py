from datetime import datetime, timezone
import plotly.express as px
import pandas as pd

def backup_status_bar_chart_value(hostname: str, backups: dict) -> int:
    """
    Get numerical backup status value for bar chart visualization
    Returns:
    -3: No backup.json
    -2: Bad backup.json (valid_schema is False or None)
    -1: Invalid date
    0: OK (age < max_age)
    1: Warning (max_age <= age < 2*max_age)
    2: Attention (2*max_age <= age < 3*max_age)
    3: Severe (3*max_age <= age < 4*max_age)
    4: Critical (4*max_age <= age < 5*max_age)
    5: Failure (age >= 5*max_age)
    """
    if hostname not in backups:
        return -3

    backup_info = backups.get(hostname, {})
    valid_schema = backup_info.get('valid_schema')
    if valid_schema is False or valid_schema is None:
        return -2

    backup_list = backup_info['backup_json_data']['backup_list']
    worst_age_status = 0

    for backup in backup_list:
        try:
            backup_date = datetime.fromisoformat(backup['date'])
            current_time = datetime.now(timezone.utc)
            age_seconds = (current_time - backup_date).total_seconds()
            age_status = int(age_seconds // backup['max_age'])
            worst_age_status = max(worst_age_status, age_status)
        except (ValueError, TypeError):
            return -1

    return min(5, worst_age_status)

def create_backup_status_bar_chart(df, backups):
    """Create a bar chart showing the distribution of backup statuses by vendor"""
    # Create a DataFrame with vendor and backup status
    data = []
    for _, row in df.iterrows():
        status = backup_status_bar_chart_value(row['hostname'], backups)
        data.append({
            'Vendor': row['vendor'],
            'Status': status
        })
    
    status_df = pd.DataFrame(data)
    
    # Create status counts by vendor
    vendor_status_counts = status_df.groupby(['Vendor', 'Status']).size().reset_index(name='Count')
    
    # Map status codes to labels
    status_labels = {
        -3: "❌ No backup.json",
        -2: "⚪ Bad backup.json",
        -1: "⏰ Invalid date",
        0: "🟢 OK",
        1: "🟡 Warning",
        2: "🟠 Attention",
        3: "🔴 Severe",
        4: "🟣 Critical",
        5: "⚫ Failure"
    }
    
    # Add status labels to DataFrame
    vendor_status_counts['Status_Label'] = vendor_status_counts['Status'].map(status_labels)
    
    # Define color scheme
    color_scheme = {
        "❌ No backup.json": "#FF0000",
        "⚪ Bad backup.json": "#CCCCCC",
        "⏰ Invalid date": "#CCCCCC",
        "🟢 OK": "#00FF00",
        "🟡 Warning": "#FFFF00",
        "🟠 Attention": "#FFA500",
        "🔴 Severe": "#FF0000",
        "🟣 Critical": "#800080",
        "⚫ Failure": "#000000"
    }
    
    # Create stacked bar chart
    fig = px.bar(
        vendor_status_counts,
        x='Vendor',
        y='Count',
        color='Status_Label',
        title='Backup Status Distribution by Vendor',
        color_discrete_map=color_scheme,
        labels={'Status_Label': 'Status'},
        category_orders={
            'Status_Label': [
                "🟢 OK",
                "🟡 Warning",
                "🟠 Attention",
                "🔴 Severe",
                "🟣 Critical",
                "⚫ Failure",
                "⏰ Invalid date",
                "⚪ Bad backup.json",
                "❌ No backup.json"
            ]
        }
    )
    
    # Update layout
    fig.update_layout(
        xaxis_title="Vendor",
        yaxis_title="Number of Devices",
        barmode='stack',
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=1.01
        )
    )
    
    return fig
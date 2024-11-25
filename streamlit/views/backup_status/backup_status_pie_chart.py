from datetime import datetime, timezone
import plotly.express as px
import pandas as pd

def backup_status_pie_chart_value(hostname: str, backups: dict) -> int:
    """
    Get numerical backup status value for pie chart visualization
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

def create_backup_status_pie_chart(df, backups):
    """Create a pie chart showing the distribution of backup statuses"""
    status_values = df['hostname'].apply(lambda x: backup_status_pie_chart_value(x, backups))
    
    status_counts = status_values.value_counts().sort_index()
    
    status_labels = {
        -3: "❌ No backup.json",
        -2: "⚪ Bad backup.json",
        -1: "⚪ Invalid date",
        0: "🟢 OK",
        1: "🟡 Warning",
        2: "🟠 Attention",
        3: "🔴 Severe",
        4: "🟣 Critical",
        5: "⚫ Failure"
    }
    
    pie_data = pd.DataFrame({
        'Status': [status_labels[status] for status in status_counts.index],
        'Count': status_counts.values
    })
    
    fig = px.pie(
        pie_data,
        values='Count',
        names='Status',
        title='Backup Status Distribution'
    )
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    return fig

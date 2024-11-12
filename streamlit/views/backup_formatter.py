from datetime import datetime, timezone
import streamlit as st
import re

def parse_iso8601(date_str):
    """Parse ISO 8601 date string with timezone offset"""
    try:
        # Handle timezone offset in format +0200
        if '+' in date_str and len(date_str.split('+')[1]) == 4:
            # Split into main part and timezone
            main_part, tz = date_str.split('+')
            # Insert colon into timezone offset (0200 -> 02:00)
            formatted_tz = f"{tz[:2]}:{tz[2:]}"
            date_str = f"{main_part}+{formatted_tz}"
        return datetime.fromisoformat(date_str)
    except Exception as e:
        print(f"Error parsing date {date_str}: {e}")
        return None

def get_backup_status_info(backup_date_str, max_age):
    """Calculate backup age and determine status color"""
    try:
        backup_date = parse_iso8601(backup_date_str)
        if not backup_date:
            return "⚫"  # Error parsing date
            
        # Convert to UTC for consistent comparison
        current_time = datetime.now(timezone.utc)
        backup_date_utc = backup_date.astimezone(timezone.utc)
        
        age = (current_time - backup_date_utc).total_seconds()
        age_factor = age / max_age
        
        if age_factor <= 1:
            return "🟢"  # Green
        elif age_factor <= 2:
            return "🟡"  # Yellow
        elif age_factor <= 3:
            return "🟠"  # Orange
        elif age_factor <= 4:
            return "🔴"  # Red
        else:
            return "🟣"  # Purple
            
    except Exception as e:
        print(f"Error in get_backup_status_info: {e}")
        return "⚫"  # Black for error

def format_backup_date(date_str):
    """Format backup date to a readable string"""
    try:
        date = parse_iso8601(date_str)
        if not date:
            return "Invalid date"
        return date.strftime("%Y-%m-%d %H:%M")
    except Exception as e:
        print(f"Error formatting date: {e}")
        return "Invalid date"

def get_backup_icon(hostname, backups_data):
    """Get backup icon for a device"""
    try:
        if hostname in backups_data and backups_data[hostname].get('has_backup', False):
            return "✅"
        return "❌"
    except Exception:
        return "❌"

def get_backup_status(hostname, backups_data):
    """Get formatted backup status for a device"""
    try:
        # Check if device has backups
        if hostname not in backups_data or not backups_data[hostname].get('has_backup', False):
            return "⚫ No backups available"
            
        backup_info = backups_data[hostname]
        if not backup_info.get('backup_data') or not backup_info['backup_data'].get('backup_list'):
            return "⚫ Backup data missing"
            
        # Process each backup file
        status_lines = []
        for backup in backup_info['backup_data']['backup_list']:
            if all(key in backup for key in ['type', 'date', 'max_age']):
                status = get_backup_status_info(backup['date'], backup['max_age'])
                date = format_backup_date(backup['date'])
                status_lines.append(f"{status} {backup['type']}: {date}")
        
        if not status_lines:
            return "⚫ Invalid backup data"
            
        # Return all status lines joined with line breaks
        return "\n".join(status_lines)
        
    except Exception as e:
        print(f"Error in get_backup_status: {e}")
        return f"⚫ Error: {str(e)}"
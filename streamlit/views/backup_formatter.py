from typing import Dict, Any
import redis
import json
import os

def get_backup_status_info(hostname: str, backups: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get backup status information for a device with status tracking per type.
    
    Status levels based on age_factor (age/max_age):
    0 - OK (age < max_age) -> 🟢
    1 - Warning (max_age <= age < 2*max_age) -> 🟡
    2 - Attention (2*max_age <= age < 3*max_age) -> 🟠
    3 - Severe (3*max_age <= age < 4*max_age) -> 🔴
    4 - Critical (4*max_age <= age < 5*max_age) -> 🟣
    5+ - Failure (age >= 5*max_age) -> ⚫
    
    Special cases:
    - No backup.json -> ❌
    - Empty/invalid backup.json -> ⚪
    """
    DEFAULT_STATUS = {
        'status': 5,  # Default to highest (worst) status
        'type_statuses': {},
        'worst_status': 5
    }

    try:
        if not hostname in backups:
            return DEFAULT_STATUS
        
        backup_info = backups.get(hostname, {})
        if not backup_info:
            return DEFAULT_STATUS
            
        backup_data = backup_info.get('backup_data', {})
        if not backup_data:
            return DEFAULT_STATUS
            
        backup_list = backup_data.get('backup_list', [])
        if not backup_list:
            return DEFAULT_STATUS
        
        # Track age factors per type
        type_age_factors: Dict[str, float] = {}
        
        # Process each backup
        for backup in backup_list:
            if not isinstance(backup, dict):
                continue
                
            backup_type = backup.get('type')
            if not backup_type:
                continue
                
            age_info = backup.get('age_info', {})
            if not isinstance(age_info, dict):
                age_info = {}
                
            try:
                age_factor = float(age_info.get('age_factor', float('inf')))
            except (TypeError, ValueError):
                age_factor = float('inf')
            
            # Keep track of the worst (highest) age factor for each type
            current_worst = type_age_factors.get(backup_type, -1)
            type_age_factors[backup_type] = max(current_worst, age_factor)
        
        # If we have no valid age factors, return default status
        if not type_age_factors:
            return DEFAULT_STATUS
        
        # Convert age factors to status levels
        type_statuses = {}
        worst_overall_status = 0
        
        for backup_type, age_factor in type_age_factors.items():
            # Status based on age_factor ranges
            if age_factor < 1:
                status = 0  # green - current
            elif age_factor < 2:
                status = 1  # yellow - warning
            elif age_factor < 3:
                status = 2  # orange - attention
            elif age_factor < 4:
                status = 3  # red - severe
            elif age_factor < 5:
                status = 4  # purple - critical
            else:
                status = 5  # black - failure
                
            type_statuses[backup_type] = status
            worst_overall_status = max(worst_overall_status, status)
        
        return {
            'status': worst_overall_status,
            'type_statuses': type_statuses,
            'worst_status': worst_overall_status
        }
        
    except Exception as e:
        print(f"Error getting backup status for {hostname}: {str(e)}")
        return DEFAULT_STATUS

def format_backup_display(status_info):
    """Format backup display string for data editor"""
    # Case 1: No backup.json at all
    if not status_info:
        return "❌ No backup.json"
    
    # Case 2: Has backup.json but no type_statuses
    if not status_info.get('type_statuses'):
        return "⚪ Empty/invalid backup.json"

    type_statuses = status_info['type_statuses']
    worst_status = status_info.get('worst_status', 5)
    
    # Map status to emoji based on age_factor ranges
    if worst_status == 0:
        emoji = '🟢'     # age < max_age
    elif worst_status == 1:
        emoji = '🟡'     # max_age <= age < 2*max_age
    elif worst_status == 2:
        emoji = '🟠'     # 2*max_age <= age < 3*max_age
    elif worst_status == 3:
        emoji = '🔴'     # 3*max_age <= age < 4*max_age
    elif worst_status == 4:
        emoji = '🟣'     # 4*max_age <= age < 5*max_age
    else:
        emoji = '⚫'     # age >= 5*max_age (Failure)

    types_str = ", ".join(sorted(type_statuses.keys()))
    return f"{emoji} {types_str}"
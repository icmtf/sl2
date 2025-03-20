from datetime import datetime, timezone

def get_backup_age_status(backup_date_str: str, max_age: int) -> int:
    try:
        backup_date = datetime.fromisoformat(backup_date_str)
        current_time = datetime.now(timezone.utc)
        age_seconds = (current_time - backup_date).total_seconds()
        return int(age_seconds // max_age)
    except Exception as e:
        # Quietly handle errors without displaying in sidebar
        return -1  # Error processing date

def get_emoji_color(backup_age_status: int) -> str:
    emoji_map = {
        0: '🟢',  # OK
        1: '🟡',  # Warning
        2: '🟠',  # Attention
        3: '🔴',  # Severe
        4: '🟣',  # Critical
        5: '⚫',  # Failure
        -1: '⏰',  # Bad date format
        -2: '⚪',  # Bad backup.json
        -3: '❌'   # No backup.json
    }
    return emoji_map.get(backup_age_status, '❓')


def format_backup_status_value(hostname: str, backups: dict) -> str:
    try:
        if not hostname:
            return f"{get_emoji_color(-3)} No hostname"
            
        if hostname not in backups:
            return f"{get_emoji_color(-3)} No backup.json"

        backup_info = backups.get(hostname, {})
        if not isinstance(backup_info, dict):
            return f"{get_emoji_color(-2)} Bad backup data type"
            
        valid_schema = backup_info.get('valid_schema', True)

        if valid_schema is False or valid_schema is None:
            return f"{get_emoji_color(-2)} Bad backup.json"

        backup_json_data = backup_info.get('backup_json_data', {})
        if not isinstance(backup_json_data, dict):
            return f"{get_emoji_color(-2)} Bad backup_json_data type"
            
        backup_list = backup_json_data.get('backup_list', [])
        if not isinstance(backup_list, list):
            return f"{get_emoji_color(-2)} Bad backup_list type"
            
        if not backup_list:
            return f"{get_emoji_color(-2)} No backups"
            
        worst_age_status = float('inf')

        for backup in backup_list:
            if not isinstance(backup, dict):
                continue
                
            try:
                if 'date' not in backup:
                    continue
                    
                age_status = get_backup_age_status(backup['date'], backup.get('max_age', 1))
                worst_age_status = min(worst_age_status, age_status)
            except ValueError as e:  # Date parsing error
                return f"{get_emoji_color(-1)} Bad date format"
            except Exception as e:
                continue

        if worst_age_status == float('inf'):
            return f"{get_emoji_color(-2)} No valid backups"
        elif worst_age_status < 1:
            return f"{get_emoji_color(0)} OK"
        elif worst_age_status < 2:
            return f"{get_emoji_color(1)} Warning"
        elif worst_age_status < 3:
            return f"{get_emoji_color(2)} Attention"
        elif worst_age_status < 4:
            return f"{get_emoji_color(3)} Severe"
        elif worst_age_status < 5:
            return f"{get_emoji_color(4)} Critical"
        else:
            return f"{get_emoji_color(5)} Failure ({worst_age_status})"
    except Exception as e:
        return f"{get_emoji_color(-3)} Error"
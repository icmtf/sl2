from datetime import datetime, timezone

def get_backup_age_status(backup_date_str: str, max_age: int) -> int:
    backup_date = datetime.fromisoformat(backup_date_str)
    current_time = datetime.now(timezone.utc)
    age_seconds = (current_time - backup_date).total_seconds()
    return int(age_seconds // max_age)

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
    if hostname not in backups:
        return f"{get_emoji_color(-3)} No backup.json"

    backup_info = backups.get(hostname, {})
    valid_schema = backup_info.get('valid_schema', True)

    if valid_schema is False or valid_schema is None:
        return f"{get_emoji_color(-2)} Bad backup.json"

    backup_list = backup_info.get('backup_json_data', {}).get('backup_list', [])
    worst_age_status = float('inf')

    for backup in backup_list:
        try:
            age_status = get_backup_age_status(backup['date'], backup['max_age'])
            worst_age_status = min(worst_age_status, age_status)
        except ValueError as e:  # Wyłapujemy błąd parsowania daty
            return f"{get_emoji_color(-1)} Bad date format"
        except Exception as e:
            st.error(f"Error processing backup: {str(e)}")
            continue

    if worst_age_status < 1:
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
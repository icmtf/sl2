from datetime import datetime, timezone

def get_compliance_status(hostname, compliance_data, compliance_type, item):
    """Get status from compliance data dict for a particular item

    Args:
        hostname (str): hostname to check
        compliance_data (dict): dict from S3 file dump
        compliance_type (str): compliance report to check : validation_data or operational_status_data
        item (str): key to check

    Returns:
        str: value of corresponding key
    """
    try:
        data_field = {"validation_data": "config_validation", "operational_status_data": "operational_status_data"}[compliance_type]
        device_data = compliance_data.get(hostname, {})
        data = device_data.get(compliance_type, {})
        
        # Przekształć item na małe litery
        item_lower = item.lower()
        
        # Wyszukaj klucz niezależnie od wielkości liter
        for key in data[data_field]:
            if key.lower() == item_lower:
                return data[data_field][key]['status']
        
        # Jeśli nie znaleziono dopasowania
        return 'N/A'
    except Exception:
        return 'N/A'

def get_compliance_date(hostname, compliance_data, compliance_type):
    """Get status from compliance data dict for a particular item

    Args:
        hostname (str): hostname to check
        compliance_data (dict): dict from S3 file dump
        compliance_type (str): compliance report to check : validation_data or operational_status_data

    Returns:
        str: date string
    """
    try:
        device_data = compliance_data.get(hostname, {})
        data = device_data.get(compliance_type, {})
        return data.get('date', 'NA')
    except Exception:
        return 'N/A'

def get_backup_age_status(backup_date_str: str, max_age: int) -> int:
    backup_date = datetime.fromisoformat(backup_date_str)
    current_time = datetime.now(timezone.utc)
    age_seconds = (current_time - backup_date).total_seconds()
    return int(age_seconds // max_age)

def get_global_status(row,col_list):
    """Check global status of a row:
        If at least one 'KO' => 'KO'
        Else if at least one 'OK' => 'OK'
        Else 'NA'

    Args:
        row (dict): row on which process the global status
        col_list (list): list of column containing individual status ('KO' or 'OK') taken into account
    """
    if "KO" in [row[x] for x in col_list]:
        return "KO"
    elif "OK" in [row[x] for x in col_list]:
        return "OK"
    else:
        return "NA"

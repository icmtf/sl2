# Backup Status View

## Data Flow
The Backup Status view directly fetches data from Redis without using FastAPI. Here's how it works:

### Data Sources
1. Device Information (`device:*`)
   - Basic device details including hostname, IP, country, and device class
   - Stored by the EasyNet worker (refreshed every 30 seconds)

2. Backup Information (`s3_backups:*`)
   - Backup data for each device including backup timestamps and validation status
   - Stored by the S3 worker (refreshed every 10 minutes)

### Implementation Details

#### Loading Device Data
```python
def load_devices_data():
    devices = []
    device_keys = redis_client.keys("device:*")
    
    for key in device_keys:
        device_data = redis_client.get(key)
        if device_data:
            device = json.loads(device_data)
            devices.append(device)
    return devices
```

#### Loading Backup Data
```python
def load_backup_data():
    backups = {}
    backup_keys = redis_client.keys("s3_backups:*")
    
    for key in backup_keys:
        backup_data = redis_client.hgetall(key)
        if backup_data:
            hostname = key.decode().split(':')[1]
            backup_json = json.loads(backup_data[b'backup_data'])
            backups[hostname] = backup_json
    return backups
```

## View Components

1. Statistical Charts
   - Pie chart showing backup status distribution
   - Bar chart showing backup status by device type

2. Device Data Table
   - Interactive table with device information
   - Color-coded backup status
   - Expandable details for each device

3. Device Details View
   - Detailed device information in expandable sections
   - Complete backup history
   - Schema validation status

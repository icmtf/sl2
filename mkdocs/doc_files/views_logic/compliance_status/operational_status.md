# Operational Status View

## Data Flow
The Operational Status view fetches data directly from Redis. It does not require FastAPI for operation.

### Data Sources
1. Device Information (`device:*`)
   - Device basic information
   - Updated by EasyNet worker every 30 seconds

2. Operational Status (`s3_opstatus`)
   - Single JSON blob containing operational status for all devices
   - Updated by S3 worker every 10 minutes

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

#### Loading Operational Status
```python
def load_opstatus_data():
    opstatus_data = redis_client.get("s3_opstatus")
    if opstatus_data:
        data = json.loads(opstatus_data)
        return {item['hostname']: item for item in data} if isinstance(data, list) else data
    return {}
```

## Status Components
The view monitors several operational aspects:
1. SSH Port Status
2. HTTPS Port Status
3. SNMP Status
4. Remote Authentication Status
5. Syslog Status

## View Components

1. Status Overview Table
   - Device information
   - Color-coded status indicators for each component
   - 🟢 OK
   - 🔴 KO
   - ⚫ NA
   - ⚪ Unknown/Other

2. Detailed Device View
   - Expandable sections for each device
   - Complete status information
   - Status messages and timestamps

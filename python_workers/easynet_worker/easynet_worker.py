import os
import time
import redis
import json
from dotenv import load_dotenv

from pyinet.common.config_loader import ConfigLoader
from pyinet.common.easynet import EasyNet

# Load environment variables
load_dotenv()

# Load configuration
required_keys = ["EASYNET_KEY", "EASYNET_SECRET"]
config_loader = ConfigLoader(required_keys=required_keys, env="prd")
config = config_loader.get_config()

# Initialize Redis client
redis_client = redis.Redis.from_url(os.getenv('REDIS_URL'))

def get_easynet_data():
    environment = os.getenv('ENVIRONMENT', 'local')
    
    if environment == 'production':
        # Use EasyNet in production
        easynet = EasyNet(
            apigee_base_uri=config.get('APIGEE_BASE_URI'),
            apigee_token_endpoint=config.get('APIGEE_TOKEN_ENDPOINT'),
            apigee_easynet_endpoint=config.get('APIGEE_EASYNET_ENDPOINT'),
            apigee_certificate=config.get('APIGEE_CERTIFICATE'),
            apigee_key=config.get('APIGEE_KEY'),
            easynet_key=config['EASYNET_KEY'],
            easynet_secret=config['EASYNET_SECRET'],
            ca_requests_bundle=config.get('BNPP_CA_BUNDLE')
        )
        return easynet.get_devices()
    else:
        # Use local data.json file
        with open('data.json', 'r') as f:
            return json.load(f)

def main():
    while True:
        print("EasyNet task is running...")
        easynet_data = get_easynet_data()
        
        # Remove all existing device:* keys from Redis
        existing_keys = redis_client.keys("device:*")
        if existing_keys:
            redis_client.delete(*existing_keys)
        
        # Add new data to Redis
        for item in easynet_data:
            redis_client.set(f"device:{item['hostname']}", json.dumps(item))
        
        print(f"Processed and stored {len(easynet_data)} EasyNet items in Redis")
        time.sleep(30)  # Run every 30 seconds

if __name__ == "__main__":
    main()
import os
import time
import redis
import json
import yaml
import boto3
import asyncio
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from pyinet.common.config_loader import ConfigLoader
from pyinet.common.easynet import EasyNet

# Load environment variables
load_dotenv()

# Load configuration
required_keys = ["EASYNET_KEY", "EASYNET_SECRET", "S3_ENDPOINT", "S3_BUCKET", "S3_KEY", "S3_SECRET"]
config_loader = ConfigLoader(required_keys=required_keys, env="prd")
config = config_loader.get_config()

# Initialize Redis client
redis_client = redis.Redis.from_url(os.getenv('REDIS_URL'))

# S3 Client Config
client_kwargs = {
    'service_name': 's3',
    'endpoint_url': config['S3_ENDPOINT'],
    'aws_access_key_id': config['S3_KEY'],
    'aws_secret_access_key': config['S3_SECRET'],
    'use_ssl': config.get('S3_USE_SSL', False),
    'verify': config.get('S3_VERIFY', False),
    'config': boto3.session.Config(
        signature_version='s3v4',
        s3={'addressing_style': 'path'}
    )
}

# Initialize S3 client
s3_client = boto3.client(**client_kwargs)

async def get_easynet_data():
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

async def get_s3_backups_list():
    try:
        response = s3_client.list_objects_v2(
            Bucket=config['S3_BUCKET'],
            Prefix='backups/'
        )
        
        # Filter results to get only filenames (without full path)
        files = []
        for obj in response.get('Contents', []):
            key = obj['Key']
            if key != 'backups/':  # Skip the directory itself
                files.append({
                    'name': key,
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat()
                })
        
        return files
    except ClientError as e:
        print(f"Error getting S3 backups list: {e}")
        return []

async def easynet_task():
    while True:
        print("EasyNet task is running...")
        easynet_data = await get_easynet_data()
        
        # Remove all existing device:* keys from Redis
        existing_keys = redis_client.keys("device:*")
        if existing_keys:
            redis_client.delete(*existing_keys)
        
        # Add new data to Redis
        for item in easynet_data:
            redis_client.set(f"device:{item['hostname']}", json.dumps(item))
        
        print(f"Processed and stored {len(easynet_data)} EasyNet items in Redis")
        await asyncio.sleep(30)  # Run every 30 seconds

async def s3_task():
    while True:
        print("S3 task is running...")
        s3_backups = await get_s3_backups_list()
        print(f"Retrieved and stored {len(s3_backups)} S3 backup files in Redis")
        await asyncio.sleep(60)  # Run every 60 seconds

async def main():
    await asyncio.gather(
        easynet_task(),
        s3_task()
    )

if __name__ == "__main__":
    asyncio.run(main())
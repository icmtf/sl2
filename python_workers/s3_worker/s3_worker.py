import os
import time
import redis
import json
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from pyinet.common.config_loader import ConfigLoader

# Load environment variables
load_dotenv()

# Load configuration
required_keys = ["S3_ENDPOINT", "S3_BUCKET", "S3_KEY", "S3_SECRET"]
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

def get_s3_backups_list():
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

def main():
    while True:
        print("S3 task is running...")
        s3_backups = get_s3_backups_list()
        redis_client.set("s3_list", json.dumps(s3_backups))
        print(f"Retrieved and stored {len(s3_backups)} S3 backup files in Redis")
        time.sleep(60)  # Run every 60 seconds

if __name__ == "__main__":
    main()

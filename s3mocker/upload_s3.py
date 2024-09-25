import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

def get_s3_client():
    # Load variables from the EnvVars (loaded from .env.s3).
    s3_endpoint = os.getenv('S3_ENDPOINT')
    s3_key = os.getenv('S3_KEY')
    s3_secret = os.getenv('S3_SECRET')
    use_ssl = os.getenv('S3_USE_SSL', 'True').lower() == 'true'
    verify = os.getenv('S3_VERIFY', 'True')
    
    # Convert "False"-string from EnvVars to a Python's Boolean False.
    if verify.lower() == 'false':
        verify = False
    
    # S3 Client Config.
    client_kwargs = {
        'service_name': 's3',
        'aws_access_key_id': s3_key,
        'aws_secret_access_key': s3_secret,
        'endpoint_url': s3_endpoint,
        'use_ssl': use_ssl,
        'verify': verify,
    }
    
    # Special Config for S3Mock.
    if not use_ssl:
        client_kwargs['config'] = boto3.session.Config(
            signature_version='s3v4',
            s3={'addressing_style': 'path'}
        )
    
    return boto3.client(**client_kwargs)

def upload_directory_to_s3(path, prefix=''):
    s3_client = get_s3_client()
    s3_bucket = os.getenv('S3_BUCKET')

    for root, dirs, files in os.walk(path):
        for file in files:
            local_path = os.path.join(root, file)
            relative_path = os.path.relpath(local_path, path)
            s3_path = os.path.join(prefix, relative_path).replace("\\", "/")

            print(f"Uploading {local_path} to {s3_path}")
            try:
                s3_client.upload_file(local_path, s3_bucket, s3_path)
                print(f"Successfully uploaded {local_path} to {s3_path}")
            except ClientError as e:
                print(f"Error uploading {local_path}: {str(e)}")

if __name__ == "__main__":
    # Load S3 variables from .env.s3
    env_file = os.getenv('ENV_FILE', '.env.s3')  # Use .env.s3 or simply override with: $ ENV_FILE=.env.name python upload_s3.py
    load_dotenv(env_file)

    local_directory = os.getenv('LOCAL_DIRECTORY', '/path/to/your/local/directory')
    s3_prefix = os.getenv('S3_PREFIX', 'backups/')

    try:
        upload_directory_to_s3(path=local_directory, prefix=s3_prefix)
        print("Upload completed successfully")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

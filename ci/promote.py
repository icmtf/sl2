import requests
import json
from dotenv import load_dotenv
import os
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Get environment variables
base_url = os.getenv('BASE_URL')
project_key = os.getenv('PROJECT_KEY')
repo_slug = os.getenv('LLE_REPO_NAME').lower()  # BitBucket requires lowercase for repo slug
token = os.getenv('TOKEN')

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

# Pull Request data
data = {
    "title": "Merge testing into master",
    "description": "Automatically created Pull Request from testing to master branch",
    "state": "OPEN",
    "open": True,
    "fromRef": {
        "id": "refs/heads/testing",
        "repository": {
            "slug": repo_slug,
            "project": {
                "key": project_key
            }
        }
    },
    "toRef": {
        "id": "refs/heads/master",
        "repository": {
            "slug": repo_slug,
            "project": {
                "key": project_key
            }
        }
    }
}

def create_pull_request():
    try:
        # Creating Pull Request
        response = requests.post(
            f"{base_url}/rest/api/1.0/projects/{project_key}/repos/{repo_slug}/pull-requests",
            headers=headers,
            data=json.dumps(data)
        )
        print("Status:", response.status_code)
        print("Response:", response.text)
        return response
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None

if __name__ == "__main__":
    create_pull_request()
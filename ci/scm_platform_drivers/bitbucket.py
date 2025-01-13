class BitbucketDriver:
    def __init__(self, workspace: str, repo_slug: str, base_url: str):
        self.workspace = workspace  # w Bitbucket Server to będzie project_key
        self.repo_slug = repo_slug
        self.base_url = base_url
        self.platform_name = "Bitbucket Server"

    def prepare_pr_payload(self, source_branch: str, target_branch: str, title: str, description: str, **kwargs):
        """
        Prepares payload for Bitbucket Server PR creation
        Documentation for Bitbucket Server 8.19.x
        """
        return {
            "title": title,
            "description": description,
            "state": "OPEN",
            "open": True,
            "fromRef": {
                "id": f"refs/heads/{source_branch}",
                "repository": {
                    "slug": self.repo_slug,
                    "project": {
                        "key": self.workspace
                    }
                }
            },
            "toRef": {
                "id": f"refs/heads/{target_branch}",
                "repository": {
                    "slug": self.repo_slug,
                    "project": {
                        "key": self.workspace
                    }
                }
            }
        }

    def prepare_api_url(self) -> str:
        """Prepares the API endpoint for PR creation for Bitbucket Server"""
        return f"rest/api/latest/projects/{self.workspace}/repos/{self.repo_slug}/pull-requests"

    def get_headers(self, token: str) -> dict:
        """Returns headers required for API calls"""
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def check_connectivity(self, token: str) -> bool:
        """
        Checks if the platform is reachable and repository is accessible
        Returns True if connection is successful, False otherwise
        """
        import requests
        try:
            url = f"{self.base_url.rstrip('/')}/rest/api/latest/projects/{self.workspace}/repos/{self.repo_slug}"
            headers = self.get_headers(token)
            response = requests.get(url, headers=headers, timeout=5)  # 5 seconds timeout
            return response.status_code == 200
        except Exception:
            return False
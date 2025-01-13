import os
import sys
import git
import json
import requests
from rich.console import Console
from rich.panel import Panel
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, List, Optional, Tuple
from scm_platform_drivers import load_scm_drivers
import time

console = Console()
load_dotenv()

class ReleaseConfig:
    def __init__(self):
        self.options = {
            "current_branch": "",
            "target_branch": "",
            "pr_title": "",
            "pr_description": "",
            "reviewers": []
        }
        self.last_menu_position = 0
        self.load_promotion_flow()
        self.initialize_git()
        self.initialize_scm_driver()
        
    def load_promotion_flow(self):
        """Load promotion flow configuration from JSON file."""
        try:
            config_path = Path(__file__).parent.parent / 'promotion_flow.json'
            with open(config_path) as f:
                config = json.load(f)
                self.environments = config['environments']
                self.promotion_rules = config['promotion_rules']
        except Exception as e:
            console.print(f"[red]Error loading promotion flow configuration: {str(e)}[/]")
            sys.exit(1)
        
    def initialize_git(self):
        try:
            self.repo = git.Repo(os.getcwd(), search_parent_directories=True)
            self.options["current_branch"] = self.repo.active_branch.name
        except git.InvalidGitRepositoryError:
            console.print("[red]Error: Not a git repository[/]")
            sys.exit(1)

    def initialize_scm_driver(self):
        """Initialize SCM platform driver"""
        drivers = load_scm_drivers()
        BitbucketDriver = drivers.get("BitbucketDriver")
        if not BitbucketDriver:
            console.print("[red]Error: Bitbucket driver not found[/]")
            sys.exit(1)
            
        workspace = os.getenv("REPO_NAMESPACE")
        repo_slug = os.getenv("LLE_REPO_NAME")
        base_url = os.getenv("BASE_URL")
        
        if not all([workspace, repo_slug, base_url]):
            console.print("[red]Error: Missing required environment variables[/]")
            sys.exit(1)
        
        self.scm_driver = BitbucketDriver(
            workspace=workspace,
            repo_slug=repo_slug,
            base_url=base_url
        )
    
    def update_option(self, key: str, value: str):
        self.options[key] = value
    
    def get_option(self, key: str) -> str:
        return self.options[key]

    def get_available_branches(self) -> List[str]:
        return [ref.name for ref in self.repo.refs if not ref.name.startswith('origin/')]

    def get_latest_tag(self) -> str:
        tags = sorted(self.repo.tags, key=lambda t: t.commit.committed_date)
        return str(tags[-1]) if tags else "v0.0.0"

    def validate_promotion_flow(self, current_branch: str, target_branch: str) -> bool:
        """Validate if the promotion flow is correct according to loaded rules."""
        for source, targets in self.promotion_rules.items():
            if current_branch == source and target_branch in targets:
                return True
        return False

    def filter_valid_target_branches(self, current_branch: str, available_branches: List[str], interactive: bool = False) -> List[str]:
        """Filter target branches based on promotion rules."""
        if interactive:
            return available_branches
            
        for source, targets in self.promotion_rules.items():
            if current_branch == source:
                return [branch for branch in available_branches if branch in targets]
        
        return []

def create_pull_request(config) -> Tuple[bool, Optional[str]]:
    with console.status("[bold green]Creating Pull Request..."):
        try:
            driver = config.scm_driver
            token = os.getenv("ACCESS_TOKEN")

            if not token:
                raise ValueError("ACCESS_TOKEN environment variable not set")

            payload = driver.prepare_pr_payload(
                source_branch=config.get_option('current_branch'),
                target_branch=config.get_option('target_branch'),
                title=config.get_option('pr_title'),
                description=config.get_option('pr_description'),
                reviewers=config.options.get('reviewers', [])
            )

            url = f"{driver.base_url.rstrip('/')}/{driver.prepare_api_url()}"
            headers = driver.get_headers(token)

            response = requests.post(
                url,
                headers=headers,
                json=payload
            )

            if 200 <= response.status_code < 300:
                pr_data = response.json()
                pr_url = pr_data.get('links', {}).get('html', {}).get('href')
                
                # Wyświetlamy wyraźne podsumowanie w ramce
                summary = f"""
[bold green]✓ Pull Request created successfully![/]

Source Branch: {config.get_option('current_branch')}
Target Branch: {config.get_option('target_branch')}
Title: {config.get_option('pr_title')}

[blue underline]PR URL: {pr_url}[/]
                """
                console.print(Panel(summary, title="Pull Request Status", border_style="green"))
                
                # Dodajemy wyraźną informację o kontynuacji
                console.print("\n[yellow]Press Enter to continue...[/]")
                input()
                return True, pr_url
            else:
                error_msg = f"""
[bold red]Error {response.status_code}![/]

Details:
{response.text}

[yellow]Press Enter to continue...[/]
                """
                console.print(Panel(error_msg, title="Error", border_style="red"))
                input()
                return False, None
            
        except Exception as e:
            error_msg = f"""
[bold red]Error creating Pull Request:[/]
{str(e)}

[yellow]Press Enter to continue...[/]
            """
            console.print(Panel(error_msg, title="Error", border_style="red"))
            input()
            return False, None
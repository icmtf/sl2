#!/usr/bin/env python3
import rich_click as click
from inquirer import List, Text, prompt
from rich.console import Console
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table
from typing import Dict, Optional, List as TypeList
import os
import sys
import requests
from dotenv import load_dotenv
import git
import semver
import json
from pathlib import Path
from scm_platform_drivers import load_scm_drivers

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
        self.last_menu_position = 0  # Dodana zmienna do zapamiętywania pozycji menu
        self.load_promotion_flow()
        self.initialize_git()
        self.initialize_scm_driver()
        
    def load_promotion_flow(self):
        """Load promotion flow configuration from JSON file."""
        try:
            config_path = Path(__file__).parent / 'promotion_flow.json'
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
            
        workspace = os.getenv("REPO_NAMESPACE")  # Zmienione z PROJECT_KEY
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

    def get_available_branches(self) -> TypeList[str]:
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

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_menu_choices(config: ReleaseConfig) -> Dict:
    clear_screen()
    menu_options = [
        ("Current branch", "current_branch"),
        ("Target branch", "target_branch"),
        ("PR Title", "pr_title"),
        ("PR Description", "pr_description"),
        ("Review", None),
        ("Exit", None)
    ]
    
    choices = []
    for display, key in menu_options:
        if key:  # Jeśli to pole konfiguracji
            value = config.get_option(key)
            choices.append(f"{display:<20} : [{value}]")
        else:  # Jeśli to akcja (Review/Exit)
            choices.append(display)
    
    questions = [
        List(
            'action',
            message='Select action',
            choices=choices,
            default=choices[config.last_menu_position]  # Używamy zapisanej pozycji
        ),
    ]
    result = prompt(questions)
    
    # Zapisujemy nową pozycję
    config.last_menu_position = choices.index(result['action'])
    
    return result

def handle_branch_choice(config: ReleaseConfig, is_target: bool = False, interactive: bool = True) -> str:
    clear_screen()
    available_branches = config.get_available_branches()
    
    if not is_target:
        rprint("[bold]Current branch selection[/]")
        questions = [
            List(
                'branch',
                message='Select current branch',
                choices=available_branches,
            ),
        ]
    else:
        current_branch = config.get_option('current_branch')
        target_branches = filter_valid_target_branches(config, current_branch, available_branches, interactive)
        
        if not target_branches and not interactive:
            console.print(f"[red]Error: No valid target branches for {current_branch} according to promotion rules[/]")
            sys.exit(1)
        
        rprint("[bold]Target branch selection[/]")
        questions = [
            List(
                'branch',
                message='Select target branch',
                choices=target_branches,
            ),
        ]
    
    return prompt(questions)['branch']

def filter_valid_target_branches(config: ReleaseConfig, current_branch: str, available_branches: TypeList[str], interactive: bool = False) -> TypeList[str]:
    """Filter target branches based on promotion rules."""
    if interactive:
        return available_branches
        
    for source, targets in config.promotion_rules.items():
        if current_branch == source:
            return [branch for branch in available_branches if branch in targets]
    
    return []

def handle_pr_title() -> str:
    clear_screen()
    questions = [
        Text('title', message='Enter PR title'),
    ]
    return prompt(questions)['title']

def handle_pr_description() -> str:
    clear_screen()
    questions = [
        Text('description', message='Enter PR description'),
    ]
    return prompt(questions)['description']

def show_review_screen(config: ReleaseConfig) -> bool:
    clear_screen()
    
    table = Table(title="Pull Request Configuration", show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    for key, value in config.options.items():
        if value:  # Only show non-empty values
            table.add_row(key.replace('_', ' ').title(), str(value))
    
    console.print(Panel.fit(table, title="Review", border_style="cyan"))
    
    # Generowanie komendy dla trybu nieinteraktywnego
    script_name = sys.argv[0]
    command_parts = [
        f"--{key.replace('_', '-')} '{value}'"
        for key, value in config.options.items()
        if value
    ]
    command = f"python {script_name} " + " ".join(command_parts) + " --no-interactive"
    
    rprint("\n[yellow]If you want to run this command in a non-interactive way, use:[/]")
    rprint(f"[green]{command}[/]")
    
    is_valid_flow = config.validate_promotion_flow(
        config.get_option('current_branch'),
        config.get_option('target_branch')
    )
    
    if not is_valid_flow:
        console.print("\n[yellow]⚠ Warning: This promotion is outside of the standard promotion flow![/]")
        console.print("[yellow]Standard flows are:[/]")
        for source, targets in config.promotion_rules.items():
            console.print(f"[yellow]  • {source} → {', '.join(targets)}[/]")
    
    questions = [
        List(
            'action',
            message='What would you like to do?',
            choices=['Confirm and Create PR', 'Simulate PR creation', 'Back to menu'],
        ),
    ]
    
    action = prompt(questions)['action']
    if action == 'Simulate PR creation':
        driver = config.scm_driver
        token = os.getenv("ACCESS_TOKEN")
        payload = driver.prepare_pr_payload(
            source_branch=config.get_option('current_branch'),
            target_branch=config.get_option('target_branch'),
            title=config.get_option('pr_title'),
            description=config.get_option('pr_description'),
            reviewers=config.options.get('reviewers', [])
        )
        
        # Display simulation results
        console.print("\n[bold cyan]PR Creation Simulation:[/]")
        console.print(f"[bold]SCM Driver:[/] {driver.platform_name}")
        
        # Sprawdzenie połączenia z platformą SCM
        try:
            check_url = f"{driver.base_url.rstrip('/')}/rest/api/latest/projects/{driver.workspace}/repos/{driver.repo_slug}"
            headers = driver.get_headers(token)
            response = requests.get(check_url, headers=headers, timeout=5)
            is_reachable = response.status_code == 200
            console.print(f"[bold]SCM Platform connectivity:[/] {'[green]Reachable[/]' if is_reachable else '[red]Unreachable[/]'}")
        except Exception as e:
            console.print("[bold]SCM Platform connectivity:[/] [red]Unreachable[/]")
        
        # Nowy format wyświetlania API call
        base_url = driver.base_url.rstrip('/')
        endpoint = driver.prepare_api_url()
        console.print(f"[bold]SCM Platform API call:[/] [red]{base_url}[/]{f'/{endpoint}' if not endpoint.startswith('/') else endpoint}")
        
        console.print("[bold]SCM Platform Headers:[/]")
        console.print(json.dumps(driver.get_headers(token), indent=2))
        console.print("[bold]SCM Platform Payload:[/]")
        console.print(json.dumps(payload, indent=2))
                
        input("\nPress Enter to continue...")
        return False
        
    return action.startswith('Confirm')

def create_pull_request(config: ReleaseConfig) -> bool:
    with console.status("[bold green]Creating Pull Request..."):
        try:
            driver = config.scm_driver
            token = os.getenv("ACCESS_TOKEN")  # Zmienione z TOKEN

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

            if response.status_code not in (200, 201):
                raise Exception(f"Failed to create PR. Status: {response.status_code}, Response: {response.text}")

            rprint("[bold green]✓[/] Pull Request created successfully!")
            return True
            
        except Exception as e:
            rprint(f"[bold red]Error creating Pull Request: {str(e)}[/]")
            return False

@click.command()
@click.option('--current-branch', type=str, help='Current branch name')
@click.option('--target-branch', type=str, help='Target branch for promotion')
@click.option('--pr-title', type=str, help='Pull Request title')
@click.option('--pr-description', type=str, help='Pull Request description')
@click.option('--interactive/--no-interactive', default=True, help='Run in interactive mode')
def main(current_branch: Optional[str], target_branch: Optional[str],
         pr_title: Optional[str], pr_description: Optional[str], interactive: bool):
    """Release management and promotion tool"""
    
    config = ReleaseConfig()
    
    if not interactive:
        if current_branch:
            config.update_option('current_branch', current_branch)
        if target_branch:
            config.update_option('target_branch', target_branch)
        if pr_title:
            config.update_option('pr_title', pr_title)
        if pr_description:
            config.update_option('pr_description', pr_description)
            
        # Walidacja tylko w trybie nieinteraktywnym
        if not config.validate_promotion_flow(config.get_option('current_branch'),
                                         config.get_option('target_branch')):
            rprint("[red]Error: Invalid promotion flow according to rules![/]")
            sys.exit(1)
        create_pull_request(config)
        return

    while True:
        choice = get_menu_choices(config)
        action = choice['action'].split(' : [')[0].strip()
        
        if action == 'Current branch':
            config.update_option('current_branch', handle_branch_choice(config, is_target=False, interactive=True))
        elif action == 'Target branch':
            config.update_option('target_branch', handle_branch_choice(config, is_target=True, interactive=True))
        elif action == 'PR Title':
            config.update_option('pr_title', handle_pr_title())
        elif action == 'PR Description':
            config.update_option('pr_description', handle_pr_description())
        elif action == 'Review':
            if show_review_screen(config):
                if create_pull_request(config):
                    break
        else:  # Exit
            break

if __name__ == '__main__':
    main()
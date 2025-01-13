from inquirer import List, Text, prompt
from rich.console import Console
from rich import print as rprint
from rich.panel import Panel
from rich.table import Table
import os
import json
import sys
import requests
from typing import Dict

console = Console()

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_menu_choices(config) -> Dict:
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
        if key:  # If this is a configuration field
            value = config.get_option(key)
            choices.append(f"{display:<20} : [{value}]")
        else:  # If this is an action (Review/Exit)
            choices.append(display)
    
    questions = [
        List(
            'action',
            message='Select action',
            choices=choices,
            default=choices[config.last_menu_position]
        ),
    ]
    result = prompt(questions)
    
    config.last_menu_position = choices.index(result['action'])
    return result

def handle_branch_choice(config, is_target: bool = False, interactive: bool = True) -> str:
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
        target_branches = config.filter_valid_target_branches(current_branch, available_branches, interactive)
        
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

def handle_pr_title() -> str:
    clear_screen()
    questions = [Text('title', message='Enter PR title')]
    return prompt(questions)['title']

def handle_pr_description() -> str:
    clear_screen()
    questions = [Text('description', message='Enter PR description')]
    return prompt(questions)['description']

def show_simulation_results(config):
    driver = config.scm_driver
    token = os.getenv("ACCESS_TOKEN")
    payload = driver.prepare_pr_payload(
        source_branch=config.get_option('current_branch'),
        target_branch=config.get_option('target_branch'),
        title=config.get_option('pr_title'),
        description=config.get_option('pr_description'),
        reviewers=config.options.get('reviewers', [])
    )
    
    console.print("\n[bold cyan]PR Creation Simulation:[/]")
    console.print(f"[bold]SCM Driver:[/] {driver.platform_name}")
    
    try:
        check_url = f"{driver.base_url.rstrip('/')}/rest/api/latest/projects/{driver.workspace}/repos/{driver.repo_slug}"
        headers = driver.get_headers(token)
        response = requests.get(check_url, headers=headers, timeout=5)
        is_reachable = response.status_code == 200
        console.print(f"[bold]SCM Platform connectivity:[/] {'[green]Reachable[/]' if is_reachable else '[red]Unreachable[/]'}")
    except Exception:
        console.print("[bold]SCM Platform connectivity:[/] [red]Unreachable[/]")
    
    base_url = driver.base_url.rstrip('/')
    endpoint = driver.prepare_api_url()
    console.print(f"[bold]SCM Platform API call:[/] [red]{base_url}[/]{f'/{endpoint}' if not endpoint.startswith('/') else endpoint}")
    
    console.print("[bold]SCM Platform Headers:[/]")
    console.print(json.dumps(driver.get_headers(token), indent=2))
    console.print("[bold]SCM Platform Payload:[/]")
    console.print(json.dumps(payload, indent=2))
            
    input("\nPress Enter to continue...")

def show_pr_creation_summary(pr_url: str) -> str:
    clear_screen()
    console.print("[bold green]✓ Pull Request created successfully![/]")
    console.print(f"\nPR URL: [blue underline]{pr_url}[/]")
    
    input("\nPress Enter to continue...")
    
    questions = [
        List(
            'action',
            message='What would you like to do?',
            choices=['Create another PR', 'Exit'],
        ),
    ]
    
    result = prompt(questions)
    return result['action']

def show_review_screen(config) -> bool:
    clear_screen()
    
    table = Table(title="Pull Request Configuration", show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    for key, value in config.options.items():
        if value:  # Only show non-empty values
            table.add_row(key.replace('_', ' ').title(), str(value))
    
    console.print(Panel.fit(table, title="Review", border_style="cyan"))
    
    # Generate command for non-interactive mode
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
        show_simulation_results(config)
        
        # Ask what to do next after simulation
        post_sim_questions = [
            List(
                'next_action',
                message='What would you like to do next?',
                choices=['Create PR', 'Back to menu', 'Exit'],
            ),
        ]
        next_action = prompt(post_sim_questions)['next_action']
        
        if next_action == 'Create PR':
            return True
        elif next_action == 'Exit':
            sys.exit(0)
        return False
        
    return action.startswith('Confirm')
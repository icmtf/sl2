#!/usr/bin/env python3
import rich_click as click
import sys
from typing import Optional
from inc.repo_ops import ReleaseConfig, create_pull_request
from inc.menu import (
    get_menu_choices, 
    handle_branch_choice, 
    handle_pr_title, 
    handle_pr_description,
    show_review_screen,
    show_pr_creation_summary
)
from rich import print as rprint

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
            
        if not config.validate_promotion_flow(config.get_option('current_branch'),
                                           config.get_option('target_branch')):
            rprint("[red]Error: Invalid promotion flow according to rules![/]")
            sys.exit(1)
            
        success, pr_url = create_pull_request(config)
        if not success:
            sys.exit(1)
        if pr_url:
            rprint(f"\nPR URL: [blue underline]{pr_url}[/]")
        sys.exit(0)

    while True:
        choice = get_menu_choices(config)
        action = choice['action'].split(' : [')[0].strip()
        
        if action == 'Current branch':
            config.update_option('current_branch', 
                               handle_branch_choice(config, is_target=False, interactive=True))
        elif action == 'Target branch':
            config.update_option('target_branch', 
                               handle_branch_choice(config, is_target=True, interactive=True))
        elif action == 'PR Title':
            config.update_option('pr_title', handle_pr_title())
        elif action == 'PR Description':
            config.update_option('pr_description', handle_pr_description())
        elif action == 'Review':
            if show_review_screen(config):
                success, pr_url = create_pull_request(config)
                if success and pr_url:
                    next_action = show_pr_creation_summary(pr_url)
                    if next_action == 'Exit':
                        break
                    # for 'Create another PR' continue the loop
        else:  # Exit
            break

if __name__ == '__main__':
    main()
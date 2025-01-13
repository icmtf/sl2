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

# [pozostała część pliku bez zmian, nie znaleziono polskich komentarzy] ...
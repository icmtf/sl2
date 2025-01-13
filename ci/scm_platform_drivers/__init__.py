import importlib
import os
import inspect

def load_scm_drivers():
    """Loads all available SCM platform drivers"""
    drivers = {}
    current_dir = os.path.dirname(__file__)
    
    # Get all .py files in the current directory
    for file in os.listdir(current_dir):
        if file.endswith('.py') and not file.startswith('__'):
            module_name = file[:-3]  # Remove .py extension
            module = importlib.import_module(f".{module_name}", package=__package__)
            
            # Find driver class in the module
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and name.endswith('Driver'):
                    drivers[name] = obj
    
    return drivers
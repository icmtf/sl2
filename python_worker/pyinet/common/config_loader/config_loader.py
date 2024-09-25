import os
import yaml
import logging
import sys
from dotenv import load_dotenv

class ConfigLoader:
    def __init__(self, required_keys, defaults=None, yaml_path='settings.yaml', env='dev'):
        if defaults is None:
            defaults = {}

        self.required_keys = [key.upper() for key in required_keys]
        self.defaults = defaults
        self.yaml_path = yaml_path
        self.env = env
        self.config = {}  # Init empty config dict.
        self.env_file_settings = {}
        self.env_file_keys = set()

        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

        try:
            self.load_yaml_settings()
            self.load_and_parse_env_settings()
            self.load_env_vars()
            self.apply_defaults()
            self.verify_config()
        except ValueError as e:
            self.logger.critical(f'Critical error: {e}')
            sys.exit(1)

    def load_yaml_settings(self):
        try:
            with open(self.yaml_path, 'r') as file:
                settings = yaml.safe_load(file)
                if settings:
                    filtered_settings = {}
                    for key, value in settings.items():
                        if isinstance(value, dict):
                            filtered_settings[key.upper()] = value.get(self.env.upper())
                        else:
                            filtered_settings[key.upper()] = value

                    # We log only keys as comma-separated-values.
                    keys = ', '.join(filtered_settings.keys())
                    self.config.update(filtered_settings)
                    self.logger.debug(f'Loaded values from YAML. Keys: {keys}')
        except FileNotFoundError:
            self.logger.debug(f'File {self.yaml_path} does not exist.')

    def load_and_parse_env_settings(self):
        env_file = f'.env.{self.env}'
        if os.path.exists(env_file):
            # We need to manually open the dotenv-file first and build keys defined as comma-separated-values.
            # Cause after load_dotenv they become Env Vars and it's too late to distinguish which one is which.
            with open(env_file, 'r') as file:
                for line in file:
                    if line.strip() and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        self.env_file_keys.add(key.upper())

            # We log keys from .env
            self.logger.debug(f'File .env.{self.env} contains keys: {", ".join(self.env_file_keys)}')

            # Now we can load .env
            load_dotenv(env_file)

            # Get the keys from .env and save them as dict.
            self.env_file_settings = {key.upper(): os.getenv(key) for key in self.env_file_keys}

            # Filter new settings that are in .env but they aren't in our config dict yet.
            new_settings = {key: self.env_file_settings[key] for key in self.env_file_settings if key not in self.config and self.env_file_settings[key] is not None}

            if new_settings:
                # We add new settingso into config dict.
                self.config.update(new_settings)
                keys_str = ', '.join(new_settings.keys())
                self.logger.debug(f'Loaded values from file .env.{self.env}. Keys: {keys_str}')
        else:
            self.logger.debug(f'File {env_file} does not exist.')
            example_file = '.env.example'
            if os.path.exists(example_file):
                self.logger.info(f'File {example_file} exist. Consider using this as a template and name it as {env_file}.')

    def load_env_vars(self):
        # Read the EnvVars and convert EnvVar keys to upper letters.
        env_vars = {key.upper(): os.getenv(key) for key in self.required_keys}

        # Filter new settings that are in EnvVars but they aren't in our config dict yet.
        new_settings = {key: env_vars[key] for key in env_vars if key not in self.config and env_vars[key] is not None}

        if new_settings:
            #  We add new settingso into config dict.
            self.config.update(new_settings)
            keys_str = ', '.join(new_settings.keys())
            self.logger.debug(f'Loaded values from EnvVars. Keys: {keys_str}')
        else:
            self.logger.debug('EnvVars does not contain any new config keys.')

    def apply_defaults(self):
        # Add DEFAULTS values but only if they are new to config.
        defaults_to_apply = {key: self.defaults[key] for key in self.defaults if key not in self.config}

        if defaults_to_apply:
            self.config.update(defaults_to_apply)
            keys_str = ', '.join(defaults_to_apply.keys())
            self.logger.debug(f'Applied values from DEFAULTS. Keys: {keys_str}')

    def verify_config(self):
        missing_keys = [key for key in self.required_keys if key not in self.config or self.config[key] is None]
        if missing_keys:
            error_message = f'Missing following keys in configuration: {", ".join(missing_keys)}'
            raise ValueError(error_message)

    def get_config(self):
        return self.config

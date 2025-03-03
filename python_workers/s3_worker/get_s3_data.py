#!/usr/bin/env python3

import os
import sys
import json
import boto3
import argparse
from dotenv import load_dotenv
import logging

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pobierz ścieżkę do pliku konfiguracyjnego
script_dir = os.path.dirname(os.path.abspath(__file__))
settings_yaml_path = os.path.join(script_dir, 'settings.yaml')

def load_config():
    """Ładuje konfigurację z pliku settings.yaml i zmiennych środowiskowych"""
    # Załaduj zmienne środowiskowe z pliku .env, jeśli istnieje
    load_dotenv()
    
    # Spróbuj załadować config_loader z projektu
    try:
        from pyinet.common.config_loader import ConfigLoader
        required_keys = [
            "S3_ENDPOINT", "S3_BUCKET", "S3_KEY", "S3_SECRET"
        ]
        config_loader = ConfigLoader(required_keys=required_keys, yaml_path=settings_yaml_path, env="prd")
        return config_loader.get_config()
    except ImportError:
        # Jeśli nie można załadować ConfigLoader, stwórz własny słownik konfiguracyjny
        logger.warning("Nie można załadować ConfigLoader, używam wartości z środowiska")
        return {
            "S3_ENDPOINT": os.getenv("S3_ENDPOINT"),
            "S3_BUCKET": os.getenv("S3_BUCKET"),
            "S3_KEY": os.getenv("S3_KEY"),
            "S3_SECRET": os.getenv("S3_SECRET"),
            "S3_USE_SSL": os.getenv("S3_USE_SSL", "False").lower() == "true",
            "S3_VERIFY": os.getenv("S3_VERIFY", "False").lower() == "true"
        }

def get_s3_client(config):
    """Inicjalizuje i zwraca klienta S3 na podstawie konfiguracji"""
    client_kwargs = {
        'service_name': 's3',
        'endpoint_url': config['S3_ENDPOINT'],
        'aws_access_key_id': config['S3_KEY'],
        'aws_secret_access_key': config['S3_SECRET'],
        'use_ssl': config.get('S3_USE_SSL', False),
        'verify': config.get('S3_VERIFY', False),
        'config': boto3.session.Config(
            signature_version='s3v4',
            s3={'addressing_style': 'path'}
        )
    }
    
    logger.info(f"Inicjalizacja klienta S3 z endpoint: {config['S3_ENDPOINT']}")
    return boto3.client(**client_kwargs)

def get_s3_file_content(s3_client, bucket, key):
    """Pobiera zawartość pliku z S3"""
    try:
        logger.info(f"Próba pobrania pliku: {key} z bucket: {bucket}")
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read().decode('utf-8')
        logger.info(f"Plik pobrany pomyślnie, rozmiar: {len(content)} bajtów")
        
        # Spróbuj sparsować jako JSON
        try:
            return json.loads(content), content
        except json.JSONDecodeError:
            logger.warning("Plik nie jest poprawnym JSON")
            return None, content
    except Exception as e:
        logger.error(f"Błąd pobierania pliku: {str(e)}")
        return None, None

def list_s3_objects(s3_client, bucket, prefix):
    """Listuje obiekty w S3 z danym prefiksem"""
    try:
        logger.info(f"Listowanie obiektów z prefiksem: {prefix}")
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix
        )
        
        objects = [obj['Key'] for obj in response.get('Contents', [])]
        logger.info(f"Znaleziono {len(objects)} obiektów")
        return objects
    except Exception as e:
        logger.error(f"Błąd listowania obiektów: {str(e)}")
        return []

def main():
    parser = argparse.ArgumentParser(description='Pobieranie plików z S3')
    parser.add_argument('key', help='Ścieżka do pliku w S3, np. "inetportalNG/Firewall/Fortinet/template.json"')
    parser.add_argument('--list', action='store_true', help='Listuj obiekty z danym prefiksem zamiast pobierać plik')
    parser.add_argument('--output', '-o', help='Ścieżka do pliku wyjściowego (domyślnie: wyświetl na stdout)')
    
    args = parser.parse_args()
    
    # Załaduj konfigurację
    config = load_config()
    
    if not config["S3_ENDPOINT"] or not config["S3_BUCKET"]:
        logger.error("Nie znaleziono konfiguracji S3. Sprawdź settings.yaml lub zmienne środowiskowe.")
        sys.exit(1)
    
    # Inicjalizuj klienta S3
    s3_client = get_s3_client(config)
    
    if args.list:
        # Tryb listowania obiektów
        objects = list_s3_objects(s3_client, config['S3_BUCKET'], args.key)
        print("\nZnalezione obiekty:")
        for obj in objects:
            print(f" - {obj}")
    else:
        # Tryb pobierania pliku
        parsed_json, content = get_s3_file_content(s3_client, config['S3_BUCKET'], args.key)
        
        if content:
            if args.output:
                # Zapisz do pliku
                with open(args.output, 'w') as f:
                    f.write(content)
                logger.info(f"Zapisano dane do pliku: {args.output}")
            else:
                # Wyświetl na stdout
                print("\nZawartość pliku:")
                print("-" * 80)
                print(content)
                print("-" * 80)
                
                if parsed_json:
                    print("\nParsowanie JSON: Poprawne")
                else:
                    print("\nParsowanie JSON: Niepoprawne (plik nie jest poprawnym JSON)")
        else:
            logger.error("Nie udało się pobrać pliku")
            sys.exit(1)

if __name__ == "__main__":
    main()
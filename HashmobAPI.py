from configparser import ConfigParser
from pathlib import Path
import logging
import requests
import os
import argparse
import time

CONFIG_PATH = 'hashmob_config.ini'
API_ENDPOINT = 'https://hashmob.net/api/v2/submit'


def setup():
    parser = argparse.ArgumentParser(
        prog='HashMob API Submit',
        description='Repeatedly submits the given potfile after a set delay.'
    )

    parser.add_argument('potfile')
    parser.add_argument('-c', '--config')
    parser.add_argument('-d', '--debug', action='store_true')

    return parser.parse_args()


def upload_to_api(data, api_endpoint, api_key):
    headers = {
        'Content-Type': 'application/json',
        'API-Key': api_key
    }

    response = requests.post(api_endpoint, json=data, headers=headers)
    logging.debug('POST request sent.')
    return response


def parse_potfile(potfile_path, previous_size):
    results = []
    logging.debug(f'Opening potfile')
    with open(potfile_path, encoding='utf8') as file:
        logging.debug(f'Seeking to position {previous_size}')
        file.seek(previous_size)
        for line in file:
            results.append(line.strip())

    return results


def main():
    args = setup()
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(format='[%(asctime)s]\t%(levelname)s: %(message)s', datefmt='%m/%d/%Y %H:%M:%S', level=log_level)
    
    # Check for config file and create parser
    config_path = Path(args.config or CONFIG_PATH)
    config = ConfigParser()
    config.read(config_path)

    # Validate that the path given exists and is a file
    potfile_path = Path(args.potfile)
    if not potfile_path.exists() or not potfile_path.is_file():
        print('Please provide a valid file for your potfile path!')
        exit(1)

    # Retrieve the given potfile's size or set to 0
    try:
        previous_size = int(config[potfile_path.name]['previous_size'])
    except KeyError:
        previous_size = 0
        config.add_section(potfile_path.name)
        config[potfile_path.name]['full_path'] = str(potfile_path.resolve())
        config[potfile_path.name]['previous_size'] = str(previous_size)

    # Use defined config or ask for defaults on first time
    try:
        api_key = config['API']['api_key']
        resubmission_delay = int(config['API']['resubmission_delay'])
    except KeyError:
        config.add_section('API')
        
        api_key = input("Enter your API key: ")
        config['API']['api_key'] = api_key

        while not (resubmission_delay := input("Enter the delay between resubmissions in seconds: ")).isdigit():
            print('Please provide an integer for the delay!')
            
        config['API']['resubmission_delay'] = resubmission_delay
        resubmission_delay = int(resubmission_delay)

    with config_path.open('w') as file:
        config.write(file)

    logging.info('Config loaded')
    algorithm = input("Enter the value for algorithm: ")
    print('\033[F\033[K\033[F')
    while True:
        # Check current size and see if it has changed. If it hasn't, wait resubmit delay
        while not os.path.getsize(potfile_path) > previous_size:
            logging.debug(f'Waiting for {resubmission_delay} seconds')
            time.sleep(resubmission_delay)
            
        # Update the config with the previous size before parsing
        config[potfile_path.name]['previous_size'] = str(previous_size)
        with config_path.open('w') as file:
            config.write(file)

        # Convert potfile to JSON
        results = parse_potfile(potfile_path, previous_size)
        
        # Prepare data for API upload
        data = {
            "algorithm": algorithm,
            "founds": results
        }

        # Upload data to API
        try:
            response = upload_to_api(data, API_ENDPOINT, api_key)
            if response.status_code == 200:
                logging.info('Successfully sent new finds!')
                previous_size = os.path.getsize(potfile_path)

                config[potfile_path.name]['previous_size'] = str(previous_size)
                logging.debug(f'Updating previous_size to {previous_size}')
                with config_path.open('w') as file:
                    config.write(file)
            else:
                logging.error(f'Failed to send new finds! We were given a status code of {response.status_code}. '
                               'Retrying after resubmission delay...')
                time.sleep(resubmission_delay)
        except Exception as e:
            logging.error(f'Error encountered when trying to send new finds: {e}')


if __name__ == "__main__":
    main()

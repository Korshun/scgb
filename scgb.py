#!/usr/bin/python3

from scgb.main import bot_init, check_comments
from scgb.database import Database
from scgb.client import SoundcloudClient

import imp
import os
import sys
import logging

def load_config():
    # Init config
    if len(sys.argv) > 1:
        config = imp.load_source('scgb_config', sys.argv[1])
    elif os.path.exists('config.py'):
        config = imp.load_source('scgb_config', os.path.join(os.getcwd(), 'config.py'))
    else:
        logging.critical('Please, rename config.py.template to config.py and edit it.\nOr specify a config to load on the command line: py scgb.py <config file>')
        sys.exit(1)

    # Init config defaults to simplify mass configuration
    try:
        defaults = imp.load_source('scgb_defaults', os.path.join(os.getcwd(), 'defaults.py'))
    except ImportError:
        pass
    else:
        for key in defaults.defaults.keys():
            if not hasattr(config, key):
                setattr(config, key, defaults[key])
        
    return config

def load_banlist(path):
    # create banlist if it doesn't exist
    if not os.path.exists(path):
        open(path, 'ab').close()

    banlist = {
        'user': {},
        'track': {},
        'playlist': {},
    }
        
    with open(path, 'r') as file:
        for line in file:
            line = line.strip()
            if line == '' or line.startswith('//'):
                continue # skip empty lines and comments

            values = line.split(None, 2)

            what = values[0]
            if what not in ['user', 'track', 'playlist']:
                logging.warning('Banlist error: unknown ban type: %s', what)
                continue

            try:
                id = int(values[1])
            except ValueError:
                logging.warning('Banlist error: %d is not a %s id number', id, what)
                continue

            if len(values) > 2:
                banlist[what][id] = values[2]
            else:
                banlist[what][id] = "No reason given."
                
    return banlist
    
if __name__ == '__main__':
    # Init log
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, datefmt='[%Y-%m-%d %H:%M:%S]', format='%(asctime)s %(levelname)s %(message)s')
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
	
	# Init config
    config = load_config()
    db = Database(config.stats_database)
    banlist = load_banlist(config.banlistfile)
    
    # Init API
    try:
        soundcloud = SoundcloudClient(config.client_id, config.client_secret, config.username, config.password, config.token_cache)
    except BadCredentialsError:
        logging.critical('Incorrect API key, login or password. Please, edit config.py.')
        sys.exit(1)
                
    bot_init(soundcloud, db, config, banlist)
    check_comments()

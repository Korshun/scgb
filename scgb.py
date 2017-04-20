#!/usr/bin/python3

from scgb.main import bot_init, check_comments
    
import imp
import os
import sys
import logging
	
if __name__ == '__main__':
    # Init log
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, datefmt='[%Y-%m-%d %H:%M:%S]', format='%(asctime)s %(levelname)s %(message)s')
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
	
	# Init config
    if len(sys.argv) > 1:
        config = imp.load_source('scgb_config', sys.argv[1])
    elif os.path.exists('config.py'):
        config = imp.load_source('scgb_config', os.path.join(os.getcwd(), 'config.py'))
    else:
        logging.critical('Please, rename config.py.template to config.py and edit it.\nOr specify a config to load on the command line: py scgb.py <config file>')
        sys.exit(1)
	
    bot_init(config)
    check_comments()

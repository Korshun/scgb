#!/usr/bin/python3

from scgb.main import bot_init, check_comments
    
import sys
import logging
	
if __name__ == '__main__':
    # Init log
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, datefmt='[%Y-%m-%d %H:%M:%S]', format='%(asctime)s %(levelname)s %(message)s')
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
	
    bot_init()
    check_comments()

#!/usr/bin/python

# SC Group Monitor by Korshun

import re
import urllib2
from datetime import datetime
import csv
import sys
import os

def update_stats(link, filename):
    response = urllib2.urlopen(link)
    html = response.read()

    def get(regex):
        return int(re.search(regex, html).group(1))
        
    with open(filename, 'ab') as file:
        if os.stat(filename).st_size == 0:
            file.write('timestamp,followers,posts,tracks,playlists,plays,likes,reposts\n')
        row = [
            datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            get('"followers_count":(\d+)'),
            get('Total posts:\s*(\d+)'),
            get('Tracks posted:\s*(\d+)'),
            get('Playlists posted:\s*(\d+)'),
            get('"playback_count":(\d+)'),
            get('"likes_count":(\d+),"permalink"'),
            get('"reposts_count":(\d+),"secret_token"'),
        ]
        
        print(row)
        file.write(','.join(map(str, row)) + '\n')
        
if __name__ == '__main__':
    if len(sys.argv) != 3:
        print 'Usage: groupmonitor.py <track url> <output>'
        sys.exit(2)
        
    print 'Retrieving:', 
    update_stats(sys.argv[1], sys.argv[2])

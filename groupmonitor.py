#!/usr/bin/python

# SC Group Monitor by Korshun

import re
import urllib2
from datetime import datetime
import csv
import sys
import os
from scgb.database import Database

def update_stats(link, databasename, filename):
    response = urllib2.urlopen(link)
    html = response.read()

    def get(regex):
        return int(re.search(regex, html).group(1))
        
    with open(filename, 'ab') as file:
        if os.stat(filename).st_size == 0:
            file.write('timestamp,followers,posts,tracks,playlists,plays,likes,reposts,users\n')

        db = Database(databasename, readonly=True)
        track_count = db.track_count
        playlist_count = db.playlist_count
        user_count = db.user_count
        
        row = [
            datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            get('"followers_count":(\d+)'),
            track_count + playlist_count,
            track_count,
            playlist_count,
            get('"playback_count":(\d+)'),
            get('"likes_count":(\d+),"permalink"') or None,
            get('"reposts_count":(\d+),"secret_token"'),
            user_count,
        ]
        
        print(row)
        file.write(','.join(map(str, row)) + '\n')
        
if __name__ == '__main__':
    if len(sys.argv) != 4:
        print 'Usage: groupmonitor.py <group track url> <group database> <output>'
        sys.exit(2)
        
    print 'Retrieving:', 
    update_stats(sys.argv[1], sys.argv[2], sys.argv[3])

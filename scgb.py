#!/usr/bin/python

# By Monsterovich
# This script reposts user's track from the comments

import soundcloud
import requests
import time
import sqlite3
from urlparse import urlparse
from time import gmtime, strftime
import config

bot_version = '1.2.3'

client = soundcloud.Client(
    client_id=config.client_id,
    client_secret=config.client_secret,
    username=config.username,
    password=config.password
)

banlist = {}

def db_get_value(name):
    return db.execute('SELECT value FROM SCGB WHERE name=?', (name,)).fetchone()[0]

def db_set_value(name, value):
    db.execute('INSERT OR REPLACE INTO SCGB (name, value) VALUES (?, ?)', (name, value))

def db_value_exists(name):
    return db.execute('SELECT COUNT(*) FROM SCGB WHERE name=?', (name,)).fetchone()[0] == 1

def db_delete_value(name):
    db.execute('DELETE FROM SCGB WHERE name=?', name)

def db_setup():
    global db
    db = sqlite3.connect(config.stats_database)
    db.execute('''
CREATE TABLE IF NOT EXISTS SCGB
(
    name TEXT PRIMARY KEY,
    value
);
''')
    if not db_value_exists('track_count'):
        db_set_value('track_count', 0)
    if not db_value_exists('playlist_count'):
        db_set_value('playlist_count', 0)

def bot_load_banlist():
    # create banlist if not exists
    if not os.path.exists('banlist.txt'):
        open(config.banlistfile, 'ab').close()
  
    with open(config.banlistfile, 'r') as file:
        for line in file:
            line = line.strip()
            if line == '' or line.startswith('//'):
                continue # skip empty lines and comments
   
            id, reason = line.split(None, 1)

            try:
                id = int(id)
            except ValueError:
                print('Banlist error: {} is not a user id number'.format(id))
                continue
    
            banlist[id] = reason

def bot_track_exists(playlist, track_id):
    try:
        if playlist:
            client.get('/e1/me/playlist_reposts/'+str(track_id))
        else:
            client.get('/e1/me/track_reposts/'+str(track_id))
        return True
    except requests.exceptions.HTTPError:
        return False

def bot_update_description():
    if not config.use_advanced_description:
        return

    desc = config.description_template.strip()
    desc = desc.replace(config.keyword_tag + 'last_update' + config.keyword_tag, strftime("%Y-%m-%d %H:%M:%S", gmtime()))
    desc = desc.replace(config.keyword_tag + 'bot_version' + config.keyword_tag, bot_version)
    track_count = db_get_value('track_count')
    desc = desc.replace(config.keyword_tag + 'track_count' + config.keyword_tag, str(track_count))
    playlist_count = db_get_value('playlist_count')
    desc = desc.replace(config.keyword_tag + 'playlist_count' + config.keyword_tag, str(playlist_count))

    client.put('/me', **{ 'user[description]': desc })

def bot_repost(track_url, comment_owner):
    delete = False
    playlist = False

    if not track_url:
        print 'Empty URL detected.'
        return False

    if comment_owner in banlist:
        print 'Banned user id: ' + str(comment_owner)
        return False

    if track_url[0] == '!':
        delete = True
        track_url = track_url[1:]

    test_url = urlparse(track_url).path.split('/')
    if len(test_url) == 4 and test_url[2] == 'sets':
        playlist = True

    if playlist and not config.allow_playlists:
        print 'Playlists are not allowed. Skipping.'
        return False

    try:
        track = client.get('/resolve', url=track_url)
    except requests.exceptions.HTTPError:
        print 'Wrong URL: ' + track_url
        return False

    # ignore non-artists
    if config.only_artist_tracks and comment_owner != track.user_id:
        print 'Not an owner of: ' + track_url
        return False

    if config.only_artist_tracks and config.allow_delete and delete:
        if not bot_track_exists(playlist, track.id):
            return False
        print 'Removing repost: ' + track_url
        if playlist:
            client.delete('/e1/me/playlist_reposts/'+str(track.id))
            db_set_value('playlist_count', db_get_value('playlist_count')-1)
            db.commit()
        else:
            client.delete('/e1/me/track_reposts/'+str(track.id))
            db_set_value('track_count', db_get_value('track_count')-1)
            db.commit()
        return True

    if bot_track_exists(playlist, track.id):
        return False
    print 'Reposting: ' + track_url
    if playlist:
        client.put('/e1/me/playlist_reposts/'+str(track.id))
        db_set_value('playlist_count', db_get_value('playlist_count')+1)
        db.commit()
    else:
        client.put('/e1/me/track_reposts/'+str(track.id))
        db_set_value('track_count', db_get_value('track_count')+1)
        db.commit()
    return True

def bot_check():
    update_desc = 0
    # get track from authenticated user
    try:
        track = client.get('/me/tracks')[config.post_track_id]
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print 'Cannot find a track with id ' + str(config.post_track_id) + ' Please, fix post_track_id in config.py'
        else:
            print 'Cannot load track with id ' + str(config.post_track_id)
            print e
        return

    if not track:
        print 'Error: group track does not exist!'
        return

    # get a list of comments of the track
    comments = client.get('/tracks/%d/comments' % track.id)

    if not comments:
        print 'Nothing found...'
        return

    # process each comment and delete it
    for comment in reversed(comments):
        url = comment.body
        print 'Processing: ' + url
        update_desc += bot_repost(url, comment.user_id)
        try:
            client.delete('/tracks/' + str(track.id) + '/comments/' + str(comment.id))
        except requests.exceptions.HTTPError:
            print 'Nothing to delete: ' + url
            continue

    if update_desc > 0:
        bot_update_description()

if __name__ == '__main__':
    bot_load_banlist()
    db_setup()
    print strftime("[%Y-%m-%d %H:%M:%S]", gmtime()) + ' Reposting songs from the comments.'
    bot_check()

#EOF

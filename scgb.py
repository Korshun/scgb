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

bot_version = '1.2.2'

client = soundcloud.Client(
    client_id=config.client_id,
    client_secret=config.client_secret,
    username=config.username,
    password=config.password
)

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
        return

    if track_url[0] == '!':
        delete = True
        track_url = track_url[1:]

    test_url = urlparse(track_url).path.split('/')
    if len(test_url) == 4 and test_url[2] == 'sets':
        playlist = True

    if playlist and not config.allow_playlists:
        print 'Playlists are not allowed. Skipping.'
        return

    try:
        track = client.get('/resolve', url=track_url)
    except requests.exceptions.HTTPError:
        print 'Wrong URL: ' + track_url
        return

    # ignore non-artists
    if config.only_artist_tracks and comment_owner != track.user_id:
        print 'Not an owner of: ' + track_url
        return

    if config.only_artist_tracks and config.allow_delete and delete:
        if not bot_track_exists(playlist, track.id):
            return
        print 'Removing repost: ' + track_url
        if playlist:
            client.delete('/e1/me/playlist_reposts/'+str(track.id))
            db_set_value('playlist_count', db_get_value('playlist_count')-1)
        else:
            client.delete('/e1/me/track_reposts/'+str(track.id))
            db_set_value('track_count', db_get_value('track_count')-1)
        return

    if bot_track_exists(playlist, track.id):
        return
    print 'Reposting: ' + track_url
    if playlist:
        client.put('/e1/me/playlist_reposts/'+str(track.id))
        db_set_value('playlist_count', db_get_value('playlist_count')+1)
    else:
        client.put('/e1/me/track_reposts/'+str(track.id))
        db_set_value('track_count', db_get_value('track_count')+1)

def bot_check():
    # get track from authenticated user
    try:
        track = client.get('/me/tracks')[config.post_track_id]
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print 'Cannot find a track with id ' + str(config.post_track_id) + ' Please, fix post_track_id in config.py'
        else:
            print 'Cannot load comments for track with id ' + str(config.post_track_id)
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
        bot_repost(url, comment.user_id)
        try:
            client.delete('/tracks/' + str(track.id) + '/comments/' + str(comment.id))
        except requests.exceptions.HTTPError:
            print 'Nothing to delete: ' + url
            continue

    bot_update_description()
    db.commit()

if __name__ == '__main__':
    db_setup()
    print strftime("[%Y-%m-%d %H:%M:%S]", gmtime()) + ' Reposting songs from the comments.'
    try:
        bot_check()
    except:
        db.commit()
        raise

#EOF

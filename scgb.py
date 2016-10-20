#!/usr/bin/python

# By Monsterovich
# This script reposts user's track from the comments

import soundcloud
import requests
import time
import datetime
import os
import sys
import imp
import sqlite3
from urlparse import urlparse
from time import gmtime, strftime, time

bot_version = '1.2.9'

def bot_init():
    global config
    global client

    if len(sys.argv) > 1:
        config = imp.load_source('scgb_config', sys.argv[1])
    else:
        config = imp.load_source('scgb_config', os.path.join(os.getcwd(), 'config.py'))

    client = soundcloud.Client(
        client_id=config.client_id,
        client_secret=config.client_secret,
        username=config.username,
        password=config.password
    )
    

banlist = {
    'user': {},
    'track': {},
    'playlist': {},
}

def db_get_value(name):
    return db.execute('SELECT value FROM SCGB WHERE name=?', (name,)).fetchone()[0]

def db_set_value(name, value):
    db.execute('INSERT OR REPLACE INTO SCGB (name, value) VALUES (?, ?)', (name, value))

def db_value_exists(name):
    return db.execute('SELECT COUNT(*) FROM SCGB WHERE name=?', (name,)).fetchone()[0] == 1

def db_delete_value(name):
    db.execute('DELETE FROM SCGB WHERE name=?', name)

def db_increment_value(name):
    db.execute('UPDATE SCGB SET value=value + 1 WHERE name=?', (name,))

def db_decrement_value(name):
    db.execute('UPDATE SCGB SET value=value - 1 WHERE name=?', (name,))

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
    if not os.path.exists(config.banlistfile):
        open(config.banlistfile, 'ab').close()

    with open(config.banlistfile, 'r') as file:
        for line in file:
            line = line.strip()
            if line == '' or line.startswith('//'):
                continue # skip empty lines and comments

            values = line.split(None, 2)

            what = values[0]
            if what not in ['user', 'track', 'playlist']:
                print('Banlist error: unknown ban type: {}'.format(what))
                continue

            try:
                id = int(values[1])
            except ValueError:
                print('Banlist error: {} is not a {} id number'.format(id, what))
                continue

            if len(values) > 2:
                banlist[what][id] = values[2]
            else:
                banlist[what][id] = "No reason given."

def bot_repost_exists(what, id):
    try:
        client.get('/e1/me/{}_reposts/{}'.format(what, id))
        return True
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return False
        else:
            raise

def bot_track_spam_check(what, track_id):
    repost_time_name = what + '_' + str(track_id) + '_repost_time'

    if db_value_exists(repost_time_name):
        current_time = db_get_value(repost_time_name) + config.max_repost_interval - int(time());
        if current_time <= 0:
            db_set_value(repost_time_name, int(time()))
            return True
        else:
            print 'Cannot repost track: ' + str(datetime.timedelta(seconds=current_time)) + ' left.'
            return False
    else:
        db_set_value(repost_time_name, int(time()))
        return True

def bot_update_description():
    if not config.use_advanced_description:
        return

    track_count = db_get_value('track_count')
    playlist_count = db_get_value('playlist_count')
    
    keywords = {
        'last_update': strftime("%Y-%m-%d %H:%M:%S", gmtime()),
        'bot_version': bot_version,
        'track_count': track_count,
        'playlist_count': playlist_count,
        'post_count': track_count + playlist_count
    }
        
    desc = config.description_template.strip()
    for keyword, value in keywords.items():
        desc = desc.replace(config.keyword_tag + keyword + config.keyword_tag, str(value))

    if config.use_advanced_description == 1:
        client.put('/me', **{ 'user[description]': desc })
    elif config.use_advanced_description == 2:
        original = client.get('/me').description
        if not original:
            return
        new_desc, _ = original.split(config.stats_keyword, 1)
        new_desc += '\n' + config.stats_keyword + '\n'
        new_desc += desc
        client.put('/me', **{ 'user[description]': new_desc })

def bot_do_repost(object, what, url, refresh=False):
    if config.allowed_genres is not None:
        genres_lowercase = [ genre.lower() for genre in config.allowed_genres ]
        if object.genre.lower() not in genres_lowercase:
            print 'Genere not allowed: {}'.format(object.genre)
            return False
    if not refresh and not bot_track_spam_check(what, object.id):
        return False

    print 'Reposting: ' + url
    client.put('/e1/me/' + what + '_reposts/' + str(object.id))
    db_increment_value('{}_count'.format(what))
    return True

def bot_do_delete(object, what, url, refresh=False):
    if refresh and not bot_track_spam_check(what, object.id):
        return False
    print 'Removing repost: ' + url
    client.delete('/e1/me/' + what + '_reposts/' + str(object.id))
    db_decrement_value('{}_count'.format(what))
    return True

def bot_repost(url, comment_owner):
    what = 'track'
    action = 'repost'

    if not url:
        print 'Empty URL detected.'
        return False

    if comment_owner in banlist['user']:
        print 'Banned user id: ' + str(comment_owner)
        return False

    if url.startswith('!'):
        if not config.only_artist_tracks:
            print 'Deleting is not allowed when only_artist_tracks = False. Skipping.'
        elif not config.allow_delete:
            print 'Deleting is not allowed. Skipping.'
            return False
        else:
            action = 'delete'
            url = url[1:]
    elif url.startswith('^'):
        if not config.only_artist_tracks:
            print 'Refreshing is not allowed when only_artist_tracks = False. Skipping.'
        elif not config.allow_delete:
            print 'Refreshing is not allowed when allow_delete = False. Skipping.'
            return False
        else:
            action = 'refresh'
            url = url[1:]

    parsed_url = urlparse(url).path.split('/')
    if len(parsed_url) == 4 and parsed_url[2] == 'sets':
        if config.allow_playlists:
            what = 'playlist'
        else:
            print 'Playlists are not allowed. Skipping.'
            return False

    try:
        object = client.get('/resolve', url=url)
        if not hasattr(object, "user_id"):
            print("Not a track or playlist!")
            return False
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print 'Not found URL: ' + url
            return False
        else:
            raise

    if object.id in banlist[what]:
        print 'Banned {} id: {} (user id: {})'.format(what, object.user_id, comment_owner)
        return False

    # ignore non-artists
    if config.only_artist_tracks and comment_owner != object.user_id:
        print 'Not an owner of: ' + url
        return False

    want_to_repost = action == 'repost'
    is_reposted = bot_repost_exists(what, object.id)
    if action == 'refresh' and not is_reposted:
        print 'Track is not posted. Could not refresh: {}'.format(url)
        return False
    elif want_to_repost == is_reposted:
        print 'Already {}ed: {}'.format(action, url)
        return False

    if action == 'repost':
        if not bot_do_repost(object, what, url):
            return False
    elif action == 'delete':
        if not bot_do_delete(object, what, url):
            return False
    elif action == 'refresh':
        if not bot_do_delete(object, what, url, refresh=True):
            return False
        if not bot_do_repost(object, what, url, refresh=True):
            return False

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
    bot_init()
    bot_load_banlist()
    db_setup()
    print strftime("[%Y-%m-%d %H:%M:%S]", gmtime()) + ' Reposting songs from the comments.'
    bot_check()

#EOF

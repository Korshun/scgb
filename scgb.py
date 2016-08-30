#!/usr/bin/python

# By Monsterovich
# Version: v1.1
# This script reposts user's track from the comments

import soundcloud
import requests
import time
from urlparse import urlparse
from time import gmtime, strftime
import config

client = soundcloud.Client(
    client_id=config.client_id,
    client_secret=config.client_secret,
    username=config.username,
    password=config.password
)

def bot_repost(track_url, comment_owner):
    delete = False
    playlist = False

    if not track_url:
        print 'Empty URL detected.'
        return

    if track_url[0] == '!':
        delete = True
        track_url = track_url[1:]

    test_url = urlparse(link).path.split('/')
    if len(test_url) == 4 and test_url[2] == 'sets':
        playlist = True

    try:
        r = requests.get(track_url)
        if r.status_code == 404:
            print 'Not found URL: ' + track_url
            return
    except requests.exceptions.MissingSchema:
        print 'Invalid URL: ' + track_url
        return

    if playlist and not config.allow_playlists:
        print 'Playlists are not allowed. Skipping.'
        return

    track = client.get('/resolve', url=track_url)

    # ignore non-artists
    if config.only_artist_tracks and comment_owner != track.user_id:
        print 'Not an owner of: ' + track_url
        return

    if config.only_artist_tracks and config.allow_delete and delete:
        print 'Removing repost: ' + track_url
        try:
            if playlist:
                client.delete('/e1/me/playlist_reposts/'+str(track.id))
            else:
                client.delete('/e1/me/track_reposts/'+str(track.id))
        except requests.exceptions.HTTPError:
            print 'Repost does not exist: ' + track_url
        return

    print 'Reposting: ' + track_url
    if playlist:
        client.put('/e1/me/playlist_reposts/'+str(track.id))
    else:
        client.put('/e1/me/track_reposts/'+str(track.id))

def bot_check():
    # get the first track from authenticated user
    track = client.get('/me/tracks')[0]

    # get a list of comments of the track
    comments = client.get('/tracks/%d/comments' % track.id)

    if not comments:
        print 'Nothing found...'
        return

    # process each comment and delete it
    for comment in comments:
        url = comment.body
        print 'Processing: ' + url
        bot_repost(url, comment.user_id)
        try:
            client.delete('/tracks/' + str(track.id) + '/comments/' + str(comment.id))
        except requests.exceptions.HTTPError:
            print 'Nothing to delete: ' + url
            continue

print strftime("[%Y-%m-%d %H:%M:%S]", gmtime()) + ' Reposting songs from the comments.'
bot_check()

#EOF

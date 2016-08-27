
# By Monsterovich
# Version: v1
# This script reposts user's track from the comments

import soundcloud
import requests
import time
from time import gmtime, strftime

client = soundcloud.Client(
    client_id='',
    client_secret='',
    username='',
    password=''
)

def bot_repost(track_url):
    try:
        r = requests.get(track_url)
        if r.status_code == 404:
            print 'Not found URL: ' + track_url
            return
    except requests.exceptions.MissingSchema:
        print 'Invalid URL: ' + track_url
        return

    track = client.get('/resolve', url=track_url)
    print 'Reposting: ' + track_url
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
        bot_repost(url)
        try:
            client.delete('/tracks/' + str(track.id) + '/comments/' + str(comment.id))
        except requests.exceptions.HTTPError:
            print 'Nothing to delete: ' + url
            continue

print strftime("[%Y-%m-%d %H:%M:%S]", gmtime()) + ' Reposting songs from the comments.'
bot_check()

#EOF

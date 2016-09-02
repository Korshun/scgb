
client_id=''
client_secret=''
username=''
password=''

only_artist_tracks = True
allow_delete = True
allow_playlists = True

stats_database='scgb-stats.db'
banlistfile='banlist.txt'

# WARNING IF YOU POST MORE THAN ONE TRACK:
# posting a new original track will increase every other track's id by one.
# So you need to increase post_track_id by 1 after posting a new original track from the group's account.
post_track_id=0

use_advanced_description = True
keyword_tag='$'
description_template = '''
Last update: $last_update$
This group uses scgb bot v$bot_version$
Total tracks: $track_count$
Total playlists: $playlist_count$
'''

#EOF

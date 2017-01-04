
# Common configuration for using multiple groups
defaults = {
'client_id' : '',
'client_secret' : '',
'debug_mode' : False,
'allow_playlists' : True,
'allow_bumps' : False,
'min_bump_interval' : 60 * 60 * 24 * 7,
'post_limit_interval' : 60 * 60 * 24,
'post_limit' : 3,
'stats_database' : 'scgb-stats.db',
'token_cache' : 'token-cache.json.secret',
'banlistfile' : 'banlist.txt',
'allowed_genres' : None,
'post_track_id' : 0,
'keyword_tag': '$',
'stats_keyword' : 'Stats:',
'use_advanced_description' : 2,
'description_template': '''
Last update: $last_update$ (UTC)
This group is using scgb v$bot_version$.
$user_count$ users have made $post_count$ posts ($track_count$ tracks and $playlist_count$ playlists)
'''
}

#EOF

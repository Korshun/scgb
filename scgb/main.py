# By Monsterovich
# This script reposts user's track from the comments

from requests import HTTPError
from time import strftime, time, gmtime

import logging
import os
import sys
import imp

from scgb.database import Database
from scgb.client import SoundcloudClient, BadCredentialsError

BOT_VERSION = '1.3.3'

config = None
db = None
soundcloud = None

should_update_description = False


def bot_init(input_soundcloud, input_db, input_config, input_banlist):
    global soundcloud
    global db
    global config
    global banlist
    soundcloud = input_soundcloud
    db = input_db
    config = input_config
    banlist = input_banlist
    

def check_comments():
    """Download all comments and process them."""

    # Get the id of the group track
    try:
        group_track = soundcloud.get('/me/tracks')[config.post_track_id]
    except HTTPError as e:
        if e.response.status_code == 404:
            logging.critical('Cannot find a track with id %d. Please, fix post_track_id in config.py', config.post_track_id)
            sys.exit(1)
        else:
            raise

    # Get the comment list for the group track
    comments = soundcloud.get('/tracks/%d/comments' % group_track.id)
    if not comments:
        logging.info('Nothing found...')
        return
        
    # Process each comment and delete it
    for comment in reversed(comments):    
        logging.info('Processing a comment by user %d (%s): %s', comment.user_id, comment.user['username'], comment.body)
        response = None
        
        # Try to process the comment
        try:
            response = process_comment(comment)
        except HTTPError as e:
            if e.response.status_code == 429:
                logging.exception('Failed to repost track: too many requests:')
                return
            elif e.response.status_code // 100 == 4:
                logging.exception('Failed to process comment due to a client request error:')
            else:
                raise
        except Exception as e: # Program crash
            logging.exception('Failed to process comment:')
        else:
            if response:
                logging.info('The comment would have this response: %s', response) 
            else:
                logging.info('Comment processed successfully')
            
        # Delete the processed comment
        try:
            soundcloud.delete('/tracks/' + str(group_track.id) + '/comments/' + str(comment.id))
        except HTTPError as e:
            if e.response.status_code == 404:
                logging.warning('Comment already deleted')
            else:
                raise

    if config.use_advanced_description and should_update_description:
        update_description()
                
def process_comment(comment):
    """Process a single comment."""
    
    if not comment.body:
        logging.info('Empty URL detected.')
        return 'Your comment is empty.'

    if comment.user_id in banlist['user']:
        logging.info('Banned user id: %d', comment.user_id)
        return 'You are banned from this group.'

    url = comment.body
    action = 'repost'
    if url.startswith('!'):
        action = 'delete'
        url = url[1:]

    # Resolve the resource to repost
    resource = resolve_resource(url)
    if resource:
        logging.info('Resolved: %s %d', resource.kind, resource.id)
        if resource.kind == 'playlist' and not config.allow_playlists:
            logging.info('Playlists are not allowed. Skipping.')
            return 'Playlists are not allowed in this group.'
    else:
        logging.info('Not found')
            
    if not resource or resource.kind not in ('track', 'playlist'):
        if config.allow_playlists:
            return 'The provided link does not lead to a track or playlist.'
        else:
            return 'The provided link does not lead to a track.'
    
    resource_type = resource.kind

    # Check for ownership
    if not config.debug_mode and comment.user_id != resource.user_id:
        logging.info('Not the author of the resource')
        return 'You must be the author of the {} to post it in this group.'.format(resource_type)
            
    # Is the resource banned?
    if resource.id in banlist[resource_type]:
        reason = banlist[resource_type][resource.id];
        logging.info('This resource is banned: %s', reason)
        return 'This track or playlist is banned from this group: ' + reason

    # Repost/delete if needed
    is_reposted = check_repost_exists(resource_type, resource.id)
    if action == 'repost':
        # Genre filter
        if config.allowed_genres is not None:
            genres_lowercase = [ genre.lower() for genre in config.allowed_genres ]
            if resource.genre.lower() not in genres_lowercase:
                logging.info('Genre not allowed: %s', resource.genre)
            return 'This genre is not allowed in this group. Allowed genres are: ' + ', '.join(config.allowed_genres)
    
        # Disable bumps if needed
        if not config.allow_bumps and db.has_ever_been_posted(resource_type, resource.id):
            logging.info('Bumping is disabled and this resource is present in the database.')
            return 'Bumping is not allowed in this group.'
    
        # Enforce minimum bump interval
        last_reposted = db.last_repost_time(resource_type, resource.id)
        if last_reposted is not None and last_reposted > int(time()) - config.min_bump_interval:
            logging.info('This %s was posted %d seconds ago, but minimum bump interval is %d.', resource_type, int(time()) - last_reposted, config.min_bump_interval)
            return 'This {} is posted to the group too frequently. Try again later.'.format(resource_type)
            
        # Enforce max posts
        last_post_count = db.user_last_posts_count(comment.user_id, config.post_limit_interval)
        if last_post_count >= config.post_limit:
            logging.info('The user has already made %d reposts.', last_post_count)
            return 'You have already made {} posts.'.format(config.post_limit)
            
        # Execute the command
        if is_reposted:
            logging.info('Bumping:')
            group_delete(comment.user_id, resource_type, resource.id)
            group_repost(comment.user_id, resource_type, resource.id)
        else:
            group_repost(comment.user_id, resource_type, resource.id)
        
        request_description_update()
            
    elif action == 'delete':
        if is_reposted:
            group_delete(comment.user_id, resource_type, resource.id)
            request_description_update()
        else:
            logging.info('Resource already deleted')
    
    else:
        assert False, 'Unknown action: ' + repr(action)
            
def resolve_resource(url):
    """Return the resource object downloaded from url, or None, if not found."""
    try:
        resource = soundcloud.get('/resolve', url=url)
    except HTTPError as e:
        if e.response.status_code == 404:
            return None
        else:
            raise
            
    return resource

def check_repost_exists(type, id):
    """Return true if the respost exists, according to soundcloud.
    
    Also update the database if a repost is already deleted
    on soundcloud, but is not marked as deleted in the db."""
    
    try:
        soundcloud.get('/e1/me/{}_reposts/{}'.format(type, id))
        return True
    except HTTPError as e:
        if e.response.status_code == 404:
            db.mark_as_deleted(type, id)
            return False
        else:
            raise
    
    
def group_repost(user_id, resource_type, resource_id):
    """Repost a resource into the group and update the database."""
    logging.info('Reposting %s %d...', resource_type, resource_id)
    soundcloud.put('/e1/me/{}_reposts/{}'.format(resource_type, resource_id))
    db.record_repost(user_id, resource_type, resource_id)
    db.commit()

def group_delete(user_id, resource_type, resource_id):
    """Delete a resource from the group and update the database."""
    logging.info('Deleting %s %d...', resource_type, resource_id)
    soundcloud.delete('/e1/me/{}_reposts/{}'.format(resource_type, resource_id))
    db.record_deletion(user_id, resource_type, resource_id)
    db.commit()

    
def request_description_update():
    """Set a flag to update the description once all comments are processed."""
    global should_update_description
    should_update_description = True
    
def update_description():
    """Update group description."""
    
    track_count = db.track_count
    playlist_count = db.playlist_count
    
    keywords = {
        'last_update': strftime("%Y-%m-%d %H:%M:%S", gmtime()),
        'bot_version': BOT_VERSION,
        'track_count': track_count,
        'playlist_count': playlist_count,
        'user_count': db.user_count,
        'post_count': track_count + playlist_count
    }
        
    desc = config.description_template.strip()
    for keyword, value in keywords.items():
        desc = desc.replace(config.keyword_tag + keyword + config.keyword_tag, str(value))

    if config.use_advanced_description == 1:
        soundcloud.put('/me', **{ 'user[description]': desc })
        
    elif config.use_advanced_description == 2:
        original = soundcloud.get('/me').description
        if not original:
            return

        if config.stats_keyword not in original:
            logging.warning('No stats keyword found in the description. Ignoring.')
            return
        new_desc, _ = original.split(config.stats_keyword, 1)
        new_desc += config.stats_keyword + '\n'
        new_desc += desc
        soundcloud.put('/me', **{ 'user[description]': new_desc })
    else:
        logging.warning('Unknown value %d for use_advanced_description', config.use_advanced_description)
        return

    global should_update_description
    should_update_description = False
    logging.info('Description updated')

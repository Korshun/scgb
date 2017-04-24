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

from datetime import datetime, timezone
def parse_sc_datetime(sc_datetime):
    dt = datetime.strptime(sc_datetime, '%Y/%m/%d %H:%M:%S %z')
    return dt.replace(tzinfo=timezone.utc).timestamp()
    
BOT_VERSION = '1.3.3'

class GroupBot():
    def __init__(self, soundcloud, db, config, banlist):
        self._soundcloud = soundcloud
        self._db = db
        self._config = config
        self._banlist = banlist
        self._should_update_description = False
        
        # Get the group's user id
        self._group_user_id = self._soundcloud.get('/me').id
        
        # Get the id of the group track
        try:
            self._group_track_id = self._soundcloud.get('/me/tracks')[self._config.post_track_id].id
        except HTTPError as e:
            if e.response.status_code == 404:
                logging.critical('Cannot find a track with id %d. Please, fix post_track_id in self._config.py', self._config.post_track_id)
                sys.exit(1)
            else:
                raise

    def check_comments(self):
        """Download all comments and process them."""

        # Get new comments
        comments = self._get_new_comments()
        if not comments:
            logging.info('Nothing found...')
            return
            
        # Process each comment and delete it
        for comment in reversed(comments):    
            logging.info('Processing a comment by user %d (%s): %s', comment.user_id, comment.user['username'], comment.body)
            response = None
            
            # Try to process the comment
            try:
                response = self._process_comment(comment)
            except HTTPError as e:
                if e.response.status_code == 429:
                    logging.exception('Failed to repost track: too many requests:')
                    return
                elif e.response.status_code // 100 == 4:
                    logging.exception('Failed to process comment due to a client request error:')
                    response = 'An error happened while processing your comment. We are investigating.'
                else:
                    raise
            except Exception as e: # Program crash
                logging.exception('Failed to process comment:')
                response = 'An error happened while processing your comment. We are investigating.'
            
            # Record last processed comment's date to avoid processing earlier comments
            self._db['last_processed_comment_date'] = parse_sc_datetime(comment.created_at)
            self._db.commit()
            
            # Respond to comment
            if response:
                try:
                    response = '@%s %s' % (comment.user['permalink'], response)
                    logging.info('Responding: %s', response)
                    response = {
                        'body': response
                    }
                    if hasattr(comment, 'timestamp'):
                        response['timestamp'] = comment.timestamp
                    self._soundcloud.post('/tracks/%d/comments' % self._group_track_id, comment=response)
                except Exception as e:
                    logging.exception('Failed to respond to comment')

            logging.info('Comment processed successfully')

        if self._config.use_advanced_description and self._should_update_description:
            self._update_description()
                    
    def _get_new_comments(self):
        """Return new comments in the order they were posted in"""
                
        # Get the comment list for the group track
        comments = self._soundcloud.get('/tracks/%d/comments' % self._group_track_id, order='created_at')

        # Remove comments made by the group account and already processed comments
        last_processed_comment_date = self._db.get('last_processed_comment_date')
        def should_ignore_comment(comment):
            if comment.user_id == self._group_user_id:
                return True
            if last_processed_comment_date is not None and parse_sc_datetime(comment.created_at) <= last_processed_comment_date:
                return True
            return False
       
        return [comment for comment in comments if not should_ignore_comment(comment)]
                    
    def _process_comment(self, comment):
        """Process a single comment."""
        
        if not comment.body:
            logging.info('Empty URL detected.')
            return 'Your comment is empty.'

        if comment.user_id in self._banlist['user']:
            logging.info('Banned user id: %d', comment.user_id)
            return 'You are banned from this group.'

        url = comment.body
        action = 'repost'
        if url.startswith('!'):
            action = 'delete'
            url = url[1:]

        # Resolve the resource to repost
        resource = self._resolve_resource(url)
        if resource:
            logging.info('Resolved: %s %d', resource.kind, resource.id)
            if resource.kind == 'playlist' and not self._config.allow_playlists:
                logging.info('Playlists are not allowed. Skipping.')
                return 'Playlists are not allowed in this group.'
        else:
            logging.info('Not found')
                
        if not resource or resource.kind not in ('track', 'playlist'):
            if self._config.allow_playlists:
                return 'The provided link does not lead to a track or playlist.'
            else:
                return 'The provided link does not lead to a track.'
        
        resource_type = resource.kind

        # Check for ownership
        if not self._config.debug_mode and comment.user_id != resource.user_id:
            logging.info('Not the author of the resource')
            return 'You must be the author of the {} to post it in this group.'.format(resource_type)
                
        # Is the resource banned?
        if resource.id in self._banlist[resource_type]:
            reason = self._banlist[resource_type][resource.id];
            logging.info('This resource is banned: %s', reason)
            return 'This track or playlist is banned from this group: ' + reason

        # Repost/delete if needed
        is_reposted = self._check_repost_exists(resource_type, resource.id)
        if action == 'repost':
            # Genre filter
            if self._config.allowed_genres is not None:
                genres_lowercase = [ genre.lower() for genre in self._config.allowed_genres ]
                if resource.genre.lower() not in genres_lowercase:
                    logging.info('Genre not allowed: %s', resource.genre)
                return 'This genre is not allowed in this group. Allowed genres are: ' + ', '.join(self._config.allowed_genres)
        
            # Disable bumps if needed
            if not self._config.allow_bumps and self._db.has_ever_been_posted(resource_type, resource.id):
                logging.info('Bumping is disabled and this resource is present in the database.')
                return 'Bumping is not allowed in this group.'
        
            # Enforce minimum bump interval
            last_reposted = self._db.last_repost_time(resource_type, resource.id)
            if last_reposted is not None and last_reposted > int(time()) - self._config.min_bump_interval:
                logging.info('This %s was posted %d seconds ago, but minimum bump interval is %d.', resource_type, int(time()) - last_reposted, self._config.min_bump_interval)
                return 'This {} is posted to the group too frequently. Try again later.'.format(resource_type)
                
            # Enforce max posts
            last_post_count = self._db.user_last_posts_count(comment.user_id, self._config.post_limit_interval)
            if last_post_count >= self._config.post_limit:
                logging.info('The user has already made %d reposts.', last_post_count)
                return 'You have already made {} posts.'.format(self._config.post_limit)
                
            # Execute the command
            if is_reposted:
                logging.info('Bumping:')
                self._group_delete(comment.user_id, resource_type, resource.id)
                self._group_repost(comment.user_id, resource_type, resource.id)
                return 'Bumped!'
            else:
                self._group_repost(comment.user_id, resource_type, resource.id)
                self._should_update_description = True
                return 'Reposted!'
                
        elif action == 'delete':
            if is_reposted:
                self._group_delete(comment.user_id, resource_type, resource.id)
                self._should_update_description = True
                return 'Deleted!'
            else:
                logging.info('Resource already deleted')
        
        else:
            assert False, 'Unknown action: ' + repr(action)
                
    def _resolve_resource(self, url):
        """Return the resource object downloaded from url, or None, if not found."""
        try:
            resource = self._soundcloud.get('/resolve', url=url)
        except HTTPError as e:
            if e.response.status_code == 404:
                return None
            else:
                raise
                
        return resource

    def _check_repost_exists(self, type, id):
        """Return true if the repost exists, according to soundcloud.
        
        Also update the database if a repost is already deleted
        on self._soundcloud, but is not marked as deleted in the db."""
        
        try:
            self._soundcloud.get('/e1/me/{}_reposts/{}'.format(type, id))
            return True
        except HTTPError as e:
            if e.response.status_code == 404:
                self._db.mark_as_deleted(type, id)
                return False
            else:
                raise
        
        
    def _group_repost(self, user_id, resource_type, resource_id):
        """Repost a resource into the group and update the database."""
        logging.info('Reposting %s %d...', resource_type, resource_id)
        self._soundcloud.put('/e1/me/{}_reposts/{}'.format(resource_type, resource_id))
        self._db.record_repost(user_id, resource_type, resource_id)
        self._db.commit()

    def _group_delete(self, user_id, resource_type, resource_id):
        """Delete a resource from the group and update the database."""
        logging.info('Deleting %s %d...', resource_type, resource_id)
        self._soundcloud.delete('/e1/me/{}_reposts/{}'.format(resource_type, resource_id))
        self._db.record_deletion(user_id, resource_type, resource_id)
        self._db.commit()

    def _update_description(self):
        """Update group description."""
        
        track_count = self._db.track_count
        playlist_count = self._db.playlist_count
        
        keywords = {
            'last_update': strftime("%Y-%m-%d %H:%M:%S", gmtime()),
            'bot_version': BOT_VERSION,
            'track_count': track_count,
            'playlist_count': playlist_count,
            'user_count': self._db.user_count,
            'post_count': track_count + playlist_count
        }
            
        desc = self._config.description_template.strip()
        for keyword, value in keywords.items():
            desc = desc.replace(self._config.keyword_tag + keyword + self._config.keyword_tag, str(value))

        if self._config.use_advanced_description == 1:
            self._soundcloud.put('/me', **{ 'user[description]': desc })
            
        elif self._config.use_advanced_description == 2:
            original = self._soundcloud.get('/me').description
            if not original:
                return

            if self._config.stats_keyword not in original:
                logging.warning('No stats keyword found in the description. Ignoring.')
                return
            new_desc, _ = original.split(self._config.stats_keyword, 1)
            new_desc += self._config.stats_keyword + '\n'
            new_desc += desc
            self._soundcloud.put('/me', **{ 'user[description]': new_desc })
        else:
            logging.warning('Unknown value %d for use_advanced_description', self._config.use_advanced_description)
            return

        self._should_update_description = False
        logging.info('Description updated')

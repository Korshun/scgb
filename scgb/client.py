from soundcloud import Client as Soundcloud
from requests import HTTPError
from functools import partial

import json
import logging

class BadCredentialsError(ValueError):
    pass

    
SECRETS_VERSION = 2

class SoundcloudClient:
    def __init__(self, client_id, client_secret, username, password, secrets_path):
        self._secrets_path = secrets_path
        self._client_id = client_id
        self._client_secret = client_secret
        self._username = username
        self._password = password
        
        secrets = self._load_secrets()
        if secrets:
            self._api = self._init_with_secrets(secrets)
        else:
            self._api = self._init_from_scratch()
                        
    def _init_from_scratch(self):
        logging.info('Getting a new access token')
        try:
            soundcloud = Soundcloud(
                client_id=self._client_id,
                client_secret=self._client_secret,
                username=self._username,
                password=self._password
            )
        except HTTPError as e:
            if e.response.status_code == 401:
                raise BadCredentialsError from e
            else:
                raise
                
        self._save_secrets(soundcloud.access_token)
        return soundcloud
        
    def _save_secrets(self, access_token):
        secrets = {
            'version': SECRETS_VERSION,
            'username': self._username,
            'access_token': access_token,
        }
        
        try:
            with open(self._secrets_path, 'w', encoding='utf-8') as f:
                json.dump(secrets, f, indent='\t', ensure_ascii=False)
        except IOError as e:
            logging.error('Failed to write secrets file to %s: %s', self._secrets_path, e)
        
    def _load_secrets(self):
        try:
            with open(self._secrets_path, 'r', encoding='utf-8') as f:
                secrets = json.load(f)
        except FileNotFoundError:
            logging.info('Secrets file not found')
            return None
                    
        if secrets:
            if secrets.get('version') != SECRETS_VERSION:
                logging.info('Secrets file is from a different version. Ignoring')
                return None
                
            if secrets.get('username') != self._username:
                logging.info('Secrets file pertains to a different username (%s). Ignoring', secrets.get('username'))
                return None
                
            if not secrets.get('access_token'):
                logging.info('Secrets file does not have an access token. Ignoring')
                return None
            
            return secrets

    def _init_with_secrets(self, secrets):
        return Soundcloud(
            client_id=self._client_id,
            client_secret=self._client_secret,
            access_token=secrets['access_token']
        )
        
    def _request(self, type, *args, **kwargs):
        try:
            return getattr(self._api, type)(*args, **kwargs)
        except HTTPError as e:
            if e.response.status_code == 401: # FIXME: how to check for expired access token?
                logging.info('Access token expired or a 401 error happened')
                self._api = self._init_from_scratch()
                logging.info('Retrying request')
                return getattr(self._api, type)(*args, **kwargs)
            else:
                raise
                
    def __getattr__(self, name, *args, **kwargs):
        """Translate an HTTP verb into a request method."""
        if name not in ('get', 'post', 'put', 'head', 'delete'):
            raise AttributeError
        return partial(self._request, name, *args, **kwargs)
        

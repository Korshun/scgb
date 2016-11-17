_schema = """

CREATE TABLE Reposts
( 
    resource_type TEXT, -- 'track' or 'playlist'
    resource_id INTEGER, -- soundcloud id
    last_reposted_at INTEGER, -- last repost time in seconds
    deleted INTEGER, -- 1 if the repost has been deleted (can get desynced)
    user_id INTEGER, -- the user who made the repost
    
    PRIMARY KEY(resource_type, resource_id)
); 

CREATE INDEX idx_RepostsByTime ON Reposts (last_reposted_at);
CREATE INDEX idx_RepostsByUser ON Reposts (user_id, last_reposted_at);

"""
    
import sqlite3
import os
from time import time

import shutil
import logging
    
_APPLICATION_ID = (ord('S')<<24) + (ord('C')<<16) + (ord('G')<<8) + ord('B')
_DB_VERSION = 2

class Database(object):
    """An SCGB database."""

    def __init__(self, filename, readonly=False):
        """Create or open a database."""
        if os.path.exists(filename):
            self.sqlite = sqlite3.connect(filename)
            appid = self.sqlite.execute("PRAGMA application_id").fetchone()[0]
            dbversion = self.sqlite.execute("PRAGMA user_version").fetchone()[0]
            
            if appid != _APPLICATION_ID:
                raise ValueError(filename + ' is not a Soundcloud Group Bot database')
            if dbversion > _DB_VERSION:
                raise ValueError(filename + ' is from a newer version of Soundcloud Group Bot')
                
            # Upgrade the database if needed:
            if dbversion < _DB_VERSION and readonly:
                raise ValueError(filename + 'needs upgrading, but database is opened read-only')
            
            while dbversion < _DB_VERSION:
                # Make a backup
                backupname = filename + '.version{}'.format(dbversion)
                logging.info('Making a backup of the database to %s', backupname)
                shutil.copy(filename, backupname)
                
                # Upgrade the database
                logging.info('Upgrading the database to version %d...', dbversion + 1)
                self._upgrade_db(dbversion)
                dbversion += 1
                self.sqlite.execute('PRAGMA user_version=' + str(dbversion))
                logging.info('Database upgraded')
        else:
            self.sqlite = sqlite3.connect(filename)
            logging.info('Initializing a new database...')
            self.sqlite.executescript(_schema)
            self.sqlite.execute("PRAGMA application_id=" + str(_APPLICATION_ID))
            self.sqlite.execute("PRAGMA user_version=" + str(_DB_VERSION))
            self.sqlite.commit()
            logging.info('Database initialized')
            
    def _upgrade_db(self, dbversion):
        """Given the current database version, upgrade it to the next version."""
        if dbversion == 1:
            self.sqlite.execute("DROP TABLE RepostCounts")
        else:
            assert False, 'Unknown database version {}'.format(dbversion)
    
    @property
    def track_count(self):
        """The amount of tracks ever posted to the group."""
        return self.sqlite.execute("SELECT COUNT(*) FROM Reposts WHERE resource_type='track'").fetchone()[0]
        
    @property
    def playlist_count(self):
        """The amount of playlists ever posted to the group."""
        return self.sqlite.execute("SELECT COUNT(*) FROM Reposts WHERE resource_type='playlist'").fetchone()[0]
        
    @property
    def user_count(self):
        """The amount of users who have ever posted anything to the group."""
        # FIXME: this number will be wrong in groups where users can repost other users' tracks
        return self.sqlite.execute("SELECT COUNT(DISTINCT user_id) FROM Reposts").fetchone()[0]
        
    def record_repost(self, user_id, resource_type, resource_id):
        """Record a repost to the database."""
        self.sqlite.execute("""
            INSERT OR REPLACE INTO Reposts 
            (resource_type, resource_id, last_reposted_at, deleted, user_id)
            VALUES (?, ?, ?, ?, ?)""",
            (resource_type, resource_id, int(time()), False, user_id))
            
    def record_deletion(self, user_id, resource_type, resource_id):
        """Record a deletion to the database."""
        self.sqlite.execute("""
            UPDATE Reposts 
            SET deleted=1
            WHERE resource_type=? AND resource_id=?""",
            (resource_type, resource_id))
            
    def mark_as_deleted(self, resource_type, resource_id):
        """Mark a resource as not reposted.
        
        Use this to delete reposts if they are marked as reposted in the database,
        but are not reported as reposted by Soundcloud.
        """
        
        self.sqlite.execute("""
            UPDATE Reposts 
            SET deleted=1
            WHERE resource_type=? AND resource_id=?""",
            (resource_type, resource_id))
        
    def is_reposted(self, resource_type, resource_id):
        """Return True if the resource is reposted, according to the database."""
        
        self.sqlite.execute("""
            SELECT COUNT(*) FROM Reposts
            WHERE deleted=0 AND resource_type=? AND resource_id=?""",
            (resource_type, resource_id)).fetchone()[0]
            
    def last_repost_time(self, resource_type, resource_id):
        """Return a resource's last repost time, or None if the resource
        hasn't ever been reposted."""
        
        result = self.sqlite.execute("""
            SELECT last_reposted_at FROM Reposts
            WHERE resource_type=? AND resource_id=?""",
            (resource_type, resource_id)).fetchone()
            
        if result:
            return result[0]
            
    def user_last_reposts_count(self, user_id, interval):
        """Return the amount of resources posted by a user in the last interval seconds."""
        
        return self.sqlite.execute("""
            SELECT COUNT(*) FROM Reposts
            WHERE user_id=? AND deleted=0 AND last_reposted_at > ?""",
            (user_id, int(time()) - interval)).fetchone()[0]
            
    def commit(self):
        """Shorthand for self.sqlite.commit()."""
        return self.sqlite.commit()

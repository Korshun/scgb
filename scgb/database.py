_schema = """

PRAGMA application_id={application_id};
PRAGMA user_version={user_version};

CREATE TABLE ResourceCounts
(
    resource_type TEXT,
	count INTEGER NOT NULL,
	
	PRIMARY KEY(resource_type)
);

INSERT INTO ResourceCounts (resource_type, count) VALUES
('track', 0),
('playlist', 0);

CREATE TABLE Reposts
( 
	resource_type TEXT, 
	resource_id INTEGER, 
	last_reposted_at INTEGER NOT NULL, 
	deleted INTEGER NOT NULL, 
	user_id INTEGER NOT NULL,
	
	PRIMARY KEY(resource_type, resource_id)
); 

CREATE INDEX idx_RepostsByTime ON Reposts (last_reposted_at);
CREATE INDEX idx_RepostsByUser ON Reposts (user_id, last_reposted_at);

"""
	
import sqlite3
import os
from time import time
	
_APPLICATION_ID = (ord('S')<<24) + (ord('C')<<16) + (ord('G')<<8) + ord('B')
_DB_VERSION = 1

class Database:
	"""An SCGB database."""

	def __init__(self, filename):
		"""Create or open a database."""
		if os.path.exists(filename):
			self.sqlite = sqlite3.connect(filename)
			appid = self.sqlite.execute("PRAGMA application_id").fetchone()[0]
			dbversion = self.sqlite.execute("PRAGMA user_version").fetchone()[0]
			
			if appid != _APPLICATION_ID:
				raise ValueError(filename + ' is not a Soundcloud Group Bot database')
			if dbversion > _DB_VERSION:
				raise ValueError(filename + ' is from a newer version of Soundcloud Group Bot')
		else:
			self.sqlite = sqlite3.connect(filename)
			self.sqlite.executescript(_schema.format(application_id=_APPLICATION_ID, user_version=_DB_VERSION))
			self.sqlite.execute("PRAGMA application_id=" + str(_APPLICATION_ID))
			self.sqlite.execute("PRAGMA user_version=" + str(_DB_VERSION))
			self.sqlite.commit()
	
	@property
	def track_count(self):
		return self.sqlite.execute("SELECT count FROM ResourceCounts WHERE resource_type='track'").fetchone()[0]
		
	@property
	def playlist_count(self):
		return self.sqlite.execute("SELECT count FROM ResourceCounts WHERE resource_type='playlist'").fetchone()[0]
		
	def log_action(self, user_id, action, resource_type, resource_id):
		"""Record a successful user action to the database."""

		if action == 'repost':
			self.sqlite.execute("""
				INSERT OR REPLACE INTO Reposts 
				(resource_type, resource_id, last_reposted_at, deleted, user_id)
				VALUES (?, ?, ?, ?, ?)""",
				(resource_type, resource_id, int(time()), False, user_id))
			change = 1
		elif action == 'delete':
			self.sqlite.execute("""
				UPDATE Reposts 
				SET deleted=1
				WHERE resource_type=? AND resource_id=?""",
				(resource_type, resource_id))
			change = -1
		else:
			raise ValueError('Unknown action ' + repr(action))
			
		self.sqlite.execute("""
			UPDATE ResourceCounts SET count=count + ? WHERE resource_type=?""",
			(change, resource_type))
			
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

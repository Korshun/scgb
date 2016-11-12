#!/usr/bin/python

import sqlite3
import os

from sys import argv, exit
from scgb.database import Database

def convert_db(inputfile, outputfile):
	input = sqlite3.connect(inputfile)
	if os.path.exists(outputfile):
		print('Output database already exists')
		exit(1)
		
	db = Database(outputfile)
	
	track_count = input.execute("SELECT value FROM SCGB WHERE name='track_count'").fetchone()[0]
	playlist_count = input.execute("SELECT value FROM SCGB WHERE name='playlist_count'").fetchone()[0]
	
	db.sqlite.execute("UPDATE RepostCounts SET count=? WHERE resource_type='track'", (track_count,))
	db.sqlite.execute("UPDATE RepostCounts SET count=? WHERE resource_type='playlist'", (playlist_count,))
	db.commit()
	
	
if __name__ == '__main__':
	if len(argv) != 3:
		print('Usage: convert-db.py <input database> <output database>')
	
	convert_db(argv[1], argv[2])

import argparse
parser = argparse.ArgumentParser( description='Settings' )
parser.add_argument("--unknown", "-U", dest="unknown", action="store_true", help="scans all processes instead of only relying on the filename")
args = parser.parse_args()

import notitg
import time
import os
import configparser
import hashlib

NotITG = notitg.NotITG()

# Find NotITG
while not NotITG.Scan( args.unknown ):
	print("NotITG not found, retrying in 5 seconds...")
	time.sleep( 5 )

NOTITG_PATH = os.path.normpath( NotITG.GetDetails()["Process"].exe() + "/../../" )

# Grab ini file
stepmania = configparser.ConfigParser()
stepmania.read(NOTITG_PATH + "/Data/Stepmania.ini")

if not "Options" in stepmania:
	print("Could not read options! Probably fucked up directory.")
	print( "Guessed NotITG Path: " + NOTITG_PATH )
	print( stepmania )
	exit( 0 )

# Grab all song folders
song_folders = stepmania["Options"]["AdditionalSongFolders"].split(',')
if "Songs" in os.listdir(NOTITG_PATH): song_folders.append( os.path.join(NOTITG_PATH,"Songs") )
for dir in stepmania["Options"]["AdditionalFolders"].split(','):
	if dir.strip():
		if "Songs" in os.listdir(dir): song_folders.append( os.path.join(dir,"Songs") )

song_folders = list( filter(None, song_folders) )

hashes = list()

# Traverse all song folders
for folders in song_folders:
	for group in os.listdir(folders):
		group_path = os.path.join( folders, group )
		for song in os.listdir(group_path):
			song_path = os.path.join( group_path, song )
			if os.path.isdir( song_path ):
				files = os.listdir( song_path )
				simfile = next((file for file in files if file.endswith(".sm")), None)
				if simfile:
					# Do dat hash
					p = ("/Songs/%s/%s/" % (group, song)).encode("utf-8")
					hashes.append( hashlib.md5( p ).hexdigest() )

with open("index.cache", "w") as f:
	f.write("\n".join(hashes))
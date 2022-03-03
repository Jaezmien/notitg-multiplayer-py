from asyncio.transports import WriteTransport
import os
if not os.path.isfile("index.cache"):
	print("⚠ You're missing the cache, please run the cache.py script.")
	exit( 0 )
song_cache = list()
with open("index.cache", "r") as f: song_cache = f.read().split("\n")

import argparse
parser = argparse.ArgumentParser( description='Settings' )
parser.add_argument("--unknown", "-U", dest="unknown", action="store_true", help="scans all processes instead of only relying on the filename")
parser.add_argument("--pid", dest="pid", action="store", type=int, help="get a specific NotITG process from id")
parser.add_argument("--connect", dest="connect", action="store", default="http://localhost:8080", help="connect to a host")
parser.add_argument("--username", dest="username", action="store", type=str, help="your username", required=True)
args = parser.parse_args()

HOST_LINK = args.connect

import json
import asyncio
import socketio
import hashlib
sio = socketio.AsyncClient( reconnection=False )
users = dict()

# Program ID
APP_ID = 2

# 0 = Program
# 1 = Lobby
# 2 = Gameplay
# 3 = Users

# A connection to NotITG is made
def on_connect():
	pass

# NotITG disconnects/exits
def on_disconnect():
	exit( 0 )

# Receiving a (partial) buffer
def on_read(buffer, setType):
	pass

async def set_new_song( song_name: str, difficulty: int ):
	global sio
	await sio.call("setSong", data={
		"name": song_name,
		"hash": hashlib.md5( song_name.encode("utf-8") ).hexdigest(),
		"difficulty": difficulty
	})

# Receiving full buffers
def on_buffer_read(buffer):
	type = buffer.pop( 0 )
	if type == 0:
		pass
	else:
		decoded_buffer = decode_buffer(buffer)
		data = dict()
		try:
			data = json.loads( decoded_buffer )
		except:
			print('An error has occured while trying to parse the buffer')
			print(decoded_buffer)
			return
		loop = asyncio.get_event_loop()
		if type == 1:
			if data["action"] == "setSong":
				difficulty = data["difficulty"]
				songdir = data["songdir"]
				loop.create_task( set_new_song(songdir, difficulty) )
			elif data["action"] == "ready":
				loop.create_task( sio.call('lobbyReady') )
			elif data["action"] == "start":
				loop.create_task( sio.call("lobbyStart") )
		elif type == 2:
			if data["action"] == "ready":
				loop.create_task( sio.call("lobbyScreenReady") )
			elif data["action"] == "score":
				loop.create_task( sio.call("gameplayScore", data={ "score": data["score"] }) )
			elif data["action"] == "finished":
				loop.create_task( sio.call("gameplayFinished") )
	pass

has_fully_disconnected = False
# On successful buffer write
def on_write(buffer, setType):
	if buffer[0] == 0 and buffer[1] == 2:
		global has_fully_disconnected
		has_fully_disconnected = True

# Program is exiting
async def on_exit():
	if sio.connected: await sio.disconnect()
	write_to_notitg([0, 2])
	while not has_fully_disconnected:
		await asyncio.sleep(0.1)

#region Client Websocket

# CONNECTING

@sio.event
async def connect():
	print("🔃 Logging in...")
	await sio.call("auth", { "username": args.username })

@sio.event
async def auth(data):
	if not data["successful"]:
		print("💥 An error has occured while trying to authenticate!")
		print(data["message"])
		exit( 0 )

	write_to_notitg([0, 1]) # Send connected status

	# Lobby data

	lobby = dict()
	lobby["action"] = "init"
	lobby["currentHost"] = data["currentHost"] # Is host?
	lobby["isPlaying"] = data["isPlaying"] # Is lobby currently playing?
	if data["currentSong"] != None:
		owns_song = data["currentSong"]["hash"] in song_cache # Owns currently playing song?
		lobby["ownsSong"] = owns_song 
		if owns_song:
			lobby["lobbySong"] = data["currentSong"]
	if len(data["users"]) > 0: # Load users
		otherUsers = list()
		for user in data["users"]:
			otherUsers.append({ "uuid": user["uuid"], "username": user["username"] })
			if user["username"] == args.username:
				lobby["currentUser"] = user["uuid"]
		if len(otherUsers) > 0:
			lobby["users"] = otherUsers
	if data["isPlaying"]: # Send playing users uuids
		lobby["playingUUIDS"] = data["playingUsers"]
	# write_to_notitg([1]) # Update

	write_to_notitg( [1] + encode_string(json.dumps(lobby)) )

@sio.event
async def connected(data):
	act = dict()
	act["action"] = "add"
	act["uuid"] = data["uuid"]
	act["username"] = data["username"]

	write_to_notitg( [3] + encode_string(json.dumps(act)) )
@sio.event
async def disconnected(data):
	act = dict()
	act["action"] = "delete"
	act["uuid"] = data["uuid"]

	write_to_notitg( [3] + encode_string(json.dumps(act)) )

# LOBBY

@sio.event
async def setSong(data):
	act = dict()
	act["action"] = "setSong"
	act["hasSong"] = data["hash"] in song_cache
	if data["hash"] in song_cache:
		act["difficulty"] = data["difficulty"]
		act["name"] = data["name"]
	write_to_notitg( [1] + encode_string(json.dumps(act)) )

@sio.event
async def lobbyCleanup():
	act = dict()
	act["action"] = "cleanup"
	write_to_notitg( [1] + encode_string(json.dumps(act)) )

@sio.event
async def owner(data):
	act = dict()
	act["action"] = "host"
	act["uuid"] = data["uuid"]
	write_to_notitg( [1] + encode_string(json.dumps(act)) )
	if data["username"] == args.username:
		print("🎩 You are now the owner of the room!")
	else:
		print("🎩 %s is now the owner of the room!" % data["username"])

@sio.event
async def lobbyReady(data):
	act = dict()
	act["action"] = "ready"
	act["uuid"] = data["uuid"]
	act["state"] = data["state"]
	write_to_notitg( [1] + encode_string(json.dumps(act)) )
	# user = users[ data["uuid"] ]
	# print("🙋‍♂️ User %s is %s!" % (user["username"], "ready" if data["state"] else "not ready"))

# GAMEPLAY

@sio.event
async def gameplayWaiting():
	# print("⏸  Waiting for gameplay screen to finish...")
	act = dict()
	act["action"] = "gameplay"
	write_to_notitg( [1] + encode_string(json.dumps(act)) )

@sio.event
async def gameplay():
	# print("🐎 Go!")
	act = dict()
	act["action"] = "start"
	write_to_notitg( [2] + encode_string(json.dumps(act)) )

@sio.event
async def gameplayScore(data):
	# print("User %s got score %d" % (data["uuid"], data["score"]))
	act = dict()
	act["action"] = "score"
	act["uuid"] = data["uuid"]
	act["score"] = data["score"]
	write_to_notitg( [2] + encode_string(json.dumps(act)) )
	pass

# DISCONNECTING

@sio.event
async def disconnect():
	print("🌋 Disconnected from the server!")

@sio.event
async def message(data):
	pass

async def main():
	print("🔃 Connecting to server...")
	await sio.connect(args.connect)
	sio.start_background_task( update )
	await sio.wait()

#endregion


"""
------------------------------------------------------------------------
--------------------------DON'T TOUCH IT KIDDO--------------------------
------------------------------------------------------------------------
"""


#region Helpers
_ENCODE_GUIDE = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 \n'\"~!@#$%^&*()<>/-=_+[]:;.,`{}"
def encode_string(str):
	return list(map( lambda x: _ENCODE_GUIDE.find(x)+1, [x for x in str] ))
def decode_buffer(buff):
	return "".join( list(map( lambda x: _ENCODE_GUIDE[x-1], buff )) )

def chunks(lst, n):
	for i in range(0, len(lst), n): yield lst[i:i + n]
def write_to_notitg(buffer):
	global _notitg_write_buffer

	if len( buffer ) <= 26:
		_notitg_write_buffer.append({ "buffer": buffer, "set": 0, })
	else:
		buffer_chunks = list( chunks(buffer, 26) )
		for i in range(len(buffer_chunks)):
			_notitg_write_buffer.append({ "buffer": buffer_chunks[i], "set": 2 if len(buffer_chunks) == (i+1) else 1 })
#endregion

#region NotITG Handling
import notitg
import time
import signal
NotITG = notitg.NotITG()

_notitg_read_buffer = []
_notitg_write_buffer = []

_heartbeat_status = 0
_external_initialized = False
_initialize_warning = False
def tick_notitg():
	global _initialize_warning
	global _external_initialized

	if not NotITG.Heartbeat():
		global _heartbeat_status

		if (args.pid and NotITG.FromProcessId(args.pid)) or NotITG.Scan( args.unknown ):
			if NotITG.GetDetails()[ "Version" ] in ["V1", "V2"]:
				print("⚠ Unsupported NotITG version! Expected V3 or higher, got " + NotITG.GetDetails()[ "Version" ])
				NotITG.Disconnect()
				return
			_heartbeat_status = 2
			_details = NotITG.GetDetails()
			print("> -------------------------------")
			print("✔️  Found NotITG!")
			print(">> Version: " + _details[ "Version" ] )
			print(">> Build Date: " + str(_details[ "BuildDate" ]) )
			print("> -------------------------------")
		elif _heartbeat_status == 0:
			_heartbeat_status = 1
			print("❌ Could not find a version of NotITG!")
		elif _heartbeat_status == 2:
			_heartbeat_status = 0
			_external_initialized = False
			_initialize_warning = False
			print("❓ NotITG has exited")
			on_disconnect()

	else:
		if NotITG.GetExternal(60) == 0:
			if not _initialize_warning:
				_initialize_warning = True
				print( "⏳ NotITG is initializing..." )
			return
		elif not _external_initialized:
			print( "🏁 NotITG has initialized!" )
			on_connect()
			_external_initialized = True

		global _notitg_write_buffer
		global _notitg_read_buffer

		if NotITG.GetExternal(57) == 1 and NotITG.GetExternal( 59 ) == APP_ID:
			read_buffer = []

			for index in range( 28, 28 + NotITG.GetExternal(54) ):
				read_buffer.append( NotITG.GetExternal(index) )
				NotITG.SetExternal( index, 0 )

			SET_STATUS = NotITG.GetExternal(55)
			on_read( read_buffer, SET_STATUS )
			if SET_STATUS == 0: on_buffer_read( read_buffer )
			else:
				_notitg_read_buffer.extend( read_buffer )
				if SET_STATUS == 2:
					on_buffer_read( _notitg_read_buffer )
					_notitg_read_buffer.clear()

			NotITG.SetExternal( 54, 0 )
			NotITG.SetExternal( 55, 0 )
			NotITG.SetExternal( 59, 0 )
			NotITG.SetExternal( 57, 0 )

		if len( _notitg_write_buffer ) > 0 and NotITG.GetExternal( 56 ) == 0:
			NotITG.SetExternal( 56, 1 )
			write_buffer = _notitg_write_buffer.pop( 0 )

			for index, value in enumerate( write_buffer["buffer"] ): NotITG.SetExternal( index, value )
			NotITG.SetExternal( 26, len(write_buffer["buffer"]) )
			NotITG.SetExternal( 27, write_buffer["set"] )
			NotITG.SetExternal( 56, 2 )
			NotITG.SetExternal( 58, APP_ID )
			on_write( write_buffer["buffer"], write_buffer["set"] )

async def update():
	while True:
		tick_notitg()
		await sio.sleep( 0.005 )

if __name__ == "__main__":
	loop = asyncio.get_event_loop()
	try:
		loop.run_until_complete( main() )
	except KeyboardInterrupt:
		loop.run_until_complete( on_exit() ) # what the fuck
#endregion
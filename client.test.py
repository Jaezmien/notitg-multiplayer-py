import argparse

from socketio import client
parser = argparse.ArgumentParser( description='Settings' )
parser.add_argument("--connect", dest="connect", action="store", default="http://localhost:8080", help="connect to a host")
parser.add_argument("--username", dest="username", action="store", type=str, help="your username", required=True)
args = parser.parse_args()

import os
if not os.path.isfile("index.cache"):
	print("⚠ You're missing the cache, please run the cache.py script.")
	exit( 0 )

song_cache = list()
with open("index.cache", "r") as f: song_cache = f.read().split("\n")

import asyncio
import socketio
sio = socketio.AsyncClient( reconnection=False )
users = dict()
host_uuid = ''
client_uuid = ''

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
		return

	print("👍 Logged in!")
	print("Is lobby playing? %s" % data["isPlaying"])

	global client_uuid
	if len(data["users"]) > 1: # List other users
		print("🙎‍♂️ Other people in the lobby:")
		for user in data["users"]:
			if user["username"] != args.username:
				print( "🙋‍♂️ %s" % user["username"])
				users[ user["uuid"] ] = user;
			else:
				client_uuid = user["uuid"]

	# Acknowledge host
	global host_uuid
	host_uuid = data['currentHost']
	if host_uuid == client_uuid: print("🎩 You are the host of this room!")

	if len(data["playingUsers"]) > 1:
		print("▶ People who are currently playing:")
		for uuid in data["playingUsers"]:
			print( "🏃‍♂️ %s" % users[uuid]["username"] )
	if data["currentSong"] != None:
		if data["currentSong"]["hash"] in song_cache:
			print("👍 You have the song!")
		else:
			print("👎 You dont have the song!")

@sio.event
async def connected(data):
	print("👋 User %s has connected!" % data["username"])
	users[ data["uuid"] ] = data;
@sio.event
async def disconnected(data):
	print("👋 User %s has disconnected!" % data["username"])
	del users[ data["uuid"] ]

# LOBBY

@sio.event
async def setSong(data):
	print("Host has changed the song! Hash: " + data["hash"])
	if data["hash"] in song_cache:
		print("👍 You have the file!")
		print("📕 File name: " + data["name"])
	else:
		print("👎 You don't have the file!")

@sio.event
async def lobbyCleanup():
	print("🧹 Lobby has been cleaned up!")
	print("Is lobby playing? False") # Force false
	pass

@sio.event
async def owner(data):
	global host_uuid
	host_uuid = data["uuid"]
	if host_uuid == client_uuid:
		print("🎩 You are now the owner of the room!")
	else:
		print("🎩 %s is now the owner of the room!" % data["username"])

@sio.event
async def lobbyReady(data):
	user = users[ data["uuid"] ]
	print("🙋‍♂️ User %s is %s!" % (user["username"], "ready" if data["state"] else "not ready"))

# GAMEPLAY

@sio.event
async def gameplayWaiting():
	print("⏸  Waiting for gameplay screen to finish...")

@sio.event
async def gameplay():
	print("🐎 Go!")

@sio.event
async def gameplayScore(data):
	print("User %s got score %d" % (data["uuid"], data["score"]))
	pass

# DISCONNECTING

@sio.event
async def disconnect():
	print("🌋 Disconnected from the server!")

@sio.event
async def message(data):
	pass

import msvcrt # DEBUG ONLY

async def main():
	print("🔃 Connecting to server...")
	await sio.connect('http://localhost:8080')
	sio.start_background_task( debug )
	await sio.wait()
async def debug():
	while sio.connected:
		if msvcrt.kbhit():
			key = msvcrt.getch().decode()
			
			if key == "r": # Ready
				await sio.call("lobbyReady")
			elif key == "h": # Host pressing start
				await sio.call("lobbyStart")
			elif key == "u": # (Simulated) ScreenGameplay is ready
				await sio.call("lobbyScreenReady")
			elif key == "p": # (Simulated) ScreenEvaluation OnCommand
				await sio.call("gameplayFinished")
			elif key == "s": # (Simulated) User selects song 1 [Everyone has]
				# Get directory from GAMESTATE:GetCurrentSong():GetSongDir and hash it using MD5
				await sio.call("setSong", data={
					"name": "test",
					"hash": song_cache[0]
				})
			elif key == "d": # (Simulated) User selects song 2 [Not everyone has]
				await sio.call("setSong", data={
					"name": "dummy",
					"hash": "dummy"
				})
			else:
				print( key )
		await sio.sleep(0.01)

async def on_exit():
	if sio.connected: await sio.disconnect()

# asyncio.run(main())
if __name__ == "__main__":
	loop = asyncio.get_event_loop()
	try:
		loop.run_until_complete( main() )
	except KeyboardInterrupt:
		loop.run_until_complete( on_exit() ) # what the fuck
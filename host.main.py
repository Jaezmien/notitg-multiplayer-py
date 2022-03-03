import argparse
from logging import exception
from posixpath import join
parser = argparse.ArgumentParser( description='Settings' )
parser.add_argument("--port", dest="port", action="store", type=int, default=8080, help="set the port (default: 8080)")
args = parser.parse_args()

from aiohttp import web
import sys
import socketio
import random
import uuid
from datetime import datetime, timedelta

sio = socketio.AsyncServer()
app = web.Application( )
# runner = web.AppRunner( app )
sio.attach( app )

# VARIABLES

joined_users = dict() # session id -> username + uuid
uuid_dict = dict() # user uuid -> session id
host_user = '' # uuid or ''
is_playing = False
current_song = None

# CONNECTING

@sio.event
async def connect(sid, environ):
	# print("🚪 A user has connected!")
	pass

def check_username(u):
	if not u: return False
	if type(u) != str: return False
	if len(str(u).strip()) < 3: return False
	if any(user["username"] == u for user in joined_users.values()): return False
	return True
@sio.event
async def auth(sid, data):
	if sid in joined_users:
		return await sio.call("auth", data={ "successful": False, "message": "Client is already authed" }, sid=sid)
	
	if not "username" in data or not check_username(data["username"]):
		return await sio.call("auth", data={ "successful": False, "message": "Invalid username" }, sid=sid)

	print("👋 User %s has successfully connected!" % data["username"])

	user_uuid = str(uuid.uuid4())

	if len(joined_users.values()) == 0:
		global host_user
		host_user = user_uuid;
		print("🎩 User %s is now the host!" % data["username"])

	user = {
		"username": data["username"],
		"uuid": user_uuid
	}
	joined_users[ sid ] = user
	uuid_dict[ user_uuid ] = sid

	await sio.call("auth", data={
		"successful": True,
		"isPlaying": is_playing,
		"playingUsers": list(map(lambda x: joined_users[x][ "uuid" ], lobby_ready_users)),
		"users": list(joined_users.values()),
		"currentSong": current_song,
		"currentHost": joined_users[uuid_dict[host_user]] if host_user else ''
	}, sid=sid)
	await sio.emit("connected", data=user, skip_sid=sid)
	sio.enter_room(sid, "lobby")

# LOBBY

def is_host(sid):
	return host_user and sid in joined_users and joined_users[sid]["uuid"] == host_user

has_song = False
@sio.event
async def setSong(sid, data):
	if is_playing: return
	if not is_host(sid): return
	if not "name" in data or not "hash" in data or not "difficulty" in data:
		await sio.emit("error", "Invalid setSong parameters", to=sid)
		return
	global current_song
	lobby_ready_users.clear()
	current_song = {
		"name": "/".join( list(filter(None,data["name"].split("/")))[1:] ),
		"hash": data["hash"],
		"difficulty": data["difficulty"],
	}
	global has_song
	has_song = True
	await sio.emit("setSong", data=current_song, room="lobby", skip_sid=sid)

@sio.event
async def hasSong(sid):
	await sio.emit("hasSong", data=joined_users[sid]["uuid"], skip_sid=sid)

lobby_status = 0
# 0 = Idle
# 1 = Preparing
# 2 = Ingame

lobby_ready_users = list()
@sio.event
async def lobbyReady(sid):
	if is_playing: return
	if not has_song: return

	IS_READY = sid in lobby_ready_users

	if not IS_READY: lobby_ready_users.append( sid )
	else: lobby_ready_users.remove( sid )

	await sio.emit("lobbyReady", room="lobby", data={
		"uuid": joined_users[sid]["uuid"],
		"state": not IS_READY
	}, skip_sid=sid)

	if len(lobby_ready_users) != len(joined_users.values()):
		print( "🙋‍♂️ %s is %s!" % (joined_users[sid]["username"], "ready" if not IS_READY else "not ready") )
	elif len(lobby_ready_users) > 1:
		print( "👐 All users are ready! Waiting for host to start..." )
		# await sio.emit("lobbyWait", data={ "time": datetime.now().timestamp() + timedelta(0, 5) }, room="lobby")

@sio.event
async def lobbyStart(sid):
	if not is_host(sid): return
	if sid not in lobby_ready_users: return
	if len(lobby_ready_users) != len(joined_users.values()): return
	if len(lobby_ready_users) < 2: return

	print( "🎉 Host has started the lobby! Moving screens..." )

	global is_playing
	global lobby_status
	is_playing = True
	lobby_status = 1
	for user_sid in lobby_ready_users:
		sio.leave_room(user_sid, "lobby")
		sio.enter_room(user_sid, "gameplay")
	await sio.emit("gameplayWaiting", room="gameplay")

lobby_screen_ready_users = list()
@sio.event
async def lobbyScreenReady(sid):
	if sid not in lobby_ready_users: return
	if sid in lobby_screen_ready_users: return
	if len(lobby_screen_ready_users) == len(lobby_ready_users): return

	lobby_screen_ready_users.append( sid )
	print("🔃 A user has finished loading!")

	if len(lobby_screen_ready_users) == len(lobby_ready_users):
		lobby_screen_ready_users.clear()
		global lobby_status
		lobby_status = 2
		await sio.emit("gameplay", room="gameplay")

@sio.event
async def gameplayScore(sid, data):
	if sid not in lobby_ready_users: return
	if lobby_status != 2: return
	if not "score" in data or not (type(data["score"]) == int or type(data["score"]) == float): return 

	await sio.emit("gameplayScore", data={
		"uuid": joined_users[sid]["uuid"],
		"score": data["score"]
	}, room="gameplay")

gameplay_finished_users = list()
@sio.event
async def gameplayFinished(sid):
	global lobby_status
	if sid not in lobby_ready_users: return
	if lobby_status != 2: return
	if len(gameplay_finished_users) == len(lobby_ready_users): return

	gameplay_finished_users.append( sid )

	if len(gameplay_finished_users) == len(lobby_ready_users):
		print("▶ All users have finished playing!")
		for user_sid in lobby_ready_users:
			sio.leave_room(user_sid, "gameplay")
			sio.enter_room(user_sid, "lobby")
		lobby_status = 0
		gameplay_finished_users.clear()
		lobby_ready_users.clear()
		await sio.emit("lobbyCleanup", room="lobby")
		global is_playing
		is_playing = False
	else:
		print("▶ A user has finished playing!")


# DISCONNECTING

@sio.event
async def disconnect(sid):
	global joined_users

	if sid in joined_users:
		global is_playing
		global host_user

		user = joined_users[sid]
		print("👋 User %s has disconnected!" % user["username"])
		del joined_users[sid]
		if sid in lobby_ready_users: lobby_ready_users.remove(sid)
		if sid in lobby_screen_ready_users: lobby_screen_ready_users.remove(sid)
		del uuid_dict[user["uuid"]]

		global lobby_status
		if len(lobby_ready_users) < 1 and lobby_status != 0: # All "playing" users have left
			print("💥 All playing users left the room! Returning the lobby to idle state")
			lobby_status = 0
			is_playing = False
			await sio.emit("lobbyCleanup", room="lobby")

		if len(joined_users.values()) < 1: # __All__ users have left
			print("💥 All users left the room!")
			return

		if user["uuid"] == host_user: # If user that left is owner...
			new_host_sid = random.choice( list(joined_users.keys()) )
			host_user = joined_users[ new_host_sid ][ "uuid" ]
			await sio.emit("owner", room="lobby", data=joined_users[ new_host_sid ]) # Broadcast new owner

		await sio.emit("disconnected", data=user)
	else:
		# print("👋 A user has disconnected!")
		pass

@sio.event
async def message(sid, data):
	pass



async def index(request):
	"""Serve the client-side application."""
	return web.Response(text="Wrong way", content_type='text/html')
app.router.add_get("/", index)

# TODO: Much better way than this
try:
	web.run_app( app, port=int(args.port) )
except SystemExit as e:
	sys.exit( e )

"""
async def main():
	await runner.setup()
	site = web.TCPSite( runner, 'localhost', int(args.port) )
	await site.start()
	while True:
		await asyncio.sleep(3600)
"""

"""
if __name__ == "__main__":
	loop = asyncio.get_event_loop()
	try:
		loop.run_until_complete( main() )
	except KeyboardInterrupt:
		pass
"""
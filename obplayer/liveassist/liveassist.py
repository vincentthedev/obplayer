#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Copyright 2012-2015 OpenBroadcaster, Inc.

This file is part of OpenBroadcaster Player.

OpenBroadcaster Player is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

OpenBroadcaster Player is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with OpenBroadcaster Player.  If not, see <http://www.gnu.org/licenses/>.
"""

import obplayer

import socket
import os
import sys
import time

import json

import OpenSSL
import SocketServer
import BaseHTTPServer

from obplayer.httpadmin.httpserver import ObHTTPRequestHandler

class ObLiveAssist(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):

    def __init__(self):
	self.root = 'obplayer/liveassist/http'
	self.username = None

        server_address = ('', obplayer.Config.setting('live_assist_port'))  # (address, port)

	BaseHTTPServer.HTTPServer.__init__(self, server_address, ObHTTPRequestHandler)
        sa = self.socket.getsockname()
        self.log('serving live assist http on port ' + str(sa[1]))

    def log(self, message):
        obplayer.Log.log(message, 'debug')

    def handle_post(self, path, postvars, access):
	#if not access:
	#    return { 'status' : False, 'error' : "You don't have permission to do that.  You are current logged in as a guest" }

	if path == '/info/current_time':
            return { 'value' : str(time.time()) }

	elif path == '/info/show_name':
            return { 'value' : obplayer.Scheduler.get_show_name() }

	elif path == '/info/show_end':
            return { 'value' : str(obplayer.Scheduler.get_show_end()) }

	elif path == '/info/playlist':
	    playlist = obplayer.Scheduler.get_current_playlist()
	    return playlist

	elif path == '/info/liveassist_groups':
	    groups = obplayer.Scheduler.get_current_groups()
	    return groups

	elif path == '/info/play_status':
            return obplayer.Scheduler.get_now_playing()

	elif path == '/command/play':
	    if obplayer.Scheduler.unpause_show() == True:
		return '{"status": True}'
	    return { 'status' : False }

	elif path == '/command/pause':
	    if obplayer.Scheduler.pause_show() == True:
		return '{"status": True}'
	    return { 'status' : False }

	elif path == '/command/play_group_item':
	    try:
		group_num = int(postvars['group_num'][0])
		group_item_num = int(postvars['group_item_num'][0])
		position = float(postvars['position'][0])
	    except AttributeError as e:
		return { 'status' : False, 'error': "invalid request, missing " + e.args[0] + "." }

	    if obplayer.Scheduler.play_group_item(group_num, group_item_num, position):
		return { 'status' : True }
	    else:
		return { 'status' : False }

	elif path == '/command/playlist_seek':
	    try:
		track_num = int(postvars['track_num'][0])
		position = float(postvars['position'][0])
	    except AttributeError as e:
		return { 'status' : False, 'error': "invalid request, missing " + e.args[0] + "." }

	    if obplayer.Scheduler.playlist_seek(track_num, position):
		return { 'status' : True }
	    else:
		return { 'status' : False }



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
import signal

import OpenSSL
import SocketServer
import BaseHTTPServer

from obplayer.httpadmin.httpserver import ObHTTPRequestHandler


#class ObHTTPAdmin(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
class ObHTTPAdmin(BaseHTTPServer.HTTPServer):

    def __init__(self):
	self.root = 'obplayer/httpadmin/http'

        self.username = obplayer.Config.setting('http_admin_username')
        self.password = obplayer.Config.setting('http_admin_password')
        self.title = obplayer.Config.setting('http_admin_title')

        sslenable = obplayer.Config.setting('http_admin_secure')
        sslcert = obplayer.Config.setting('http_admin_sslcert')

        server_address = ('', obplayer.Config.setting('http_admin_port'))  # (address, port)

	BaseHTTPServer.HTTPServer.__init__(self, server_address, ObHTTPRequestHandler)
	if sslenable:
	    self.socket = OpenSSL.SSL.wrap_socket(self.socket, certfile=sslcert, server_side=True)

        sa = self.socket.getsockname()
        obplayer.Log.log('serving http(s) on port ' + str(sa[1]), 'admin')

    def log(self, message):
	if not "POST /status_info" in message and not "POST /alerts/list" in message:
            obplayer.Log.log(message, 'debug')

    def form_item_selected(self, setting, value):
        if obplayer.Config.setting(setting, True) == value:
            return ' selected="selected"'
        else:
            return ''

    def form_item_checked(self, setting):
        if obplayer.Config.setting(setting, True):
            return ' checked="checked"'
        else:
            return ''

    def fullscreen_status(self):
	if obplayer.Config.headless:
	    return 'N/A'
	elif obplayer.Gui.gui_window_fullscreen:
	    return 'On'
	else:
	    return 'Off'

    def command_restart(self):
	os.kill(os.getpid(), signal.SIGINT)
	return { 'status' : True }

    def command_fstoggle(self):
	if obplayer.Config.headless:
	    return { 'status' : False, 'fullscreen' : 'N/A' }
	else:
	    obplayer.Gui.fullscreen_toggle(None)
	    return { 'status' : True, 'fullscreen' : 'On' if obplayer.Gui.gui_window_fullscreen else 'Off' }

    def handle_post(self, path, postvars):
        error = None

	if path == "/save":
	    # run through each setting and make sure it's valid. if not, complain.
	    for key in postvars:
		setting_name = key
		setting_value = postvars[key][0]

		error = obplayer.Config.validate_setting(setting_name, setting_value)

		if error != None:
		    return { 'status' : False, 'error' : error }

	    # we didn't get an errors on validate, so update each setting now.
	    for key in postvars:
		setting_name = key
		setting_value = postvars[key][0]
		obplayer.Config.set(setting_name, setting_value)

	    return { 'status' : True }

	elif path == "/status_info":
	    requests = obplayer.Player.get_requests()
	    select_keys = [ 'media_type', 'end_time', 'filename', 'duration', 'media_id', 'order_num', 'artist', 'title' ]

	    data = { }
	    data['time'] = time.time()
	    for stream in requests.keys():
		data[stream] = { key: requests[stream][key] for key in requests[stream].keys() if key in select_keys }
	    data['audio_levels'] = obplayer.Player.get_audio_levels()
	    if hasattr(obplayer, 'scheduler'):
		data['show'] = obplayer.Scheduler.get_show_info()
	    data['logs'] = obplayer.Log.get_log()
	    return data

	elif path == "/alerts/inject_test":
	    if hasattr(obplayer, 'alerts'):
		obplayer.alerts.Processor.inject_alert(postvars['alert'][0])
		return { 'status' : True }
	    return { 'status' : False }

	elif path == "/alerts/cancel":
	    if hasattr(obplayer, 'alerts'):
		for identifier in postvars['identifier[]']:
		    obplayer.alerts.Processor.cancel_alert(identifier)
		return { 'status' : True }
	    return { 'status' : False }

	elif path == "/alerts/list":
	    if hasattr(obplayer, 'alerts'):
		return obplayer.alerts.Processor.get_alerts()
	    return { 'status' : False }


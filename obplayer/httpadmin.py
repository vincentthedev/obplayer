#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Copyright 2012-2013 OpenBroadcaster, Inc.

This file is part of OpenBroadcaster Remote.

OpenBroadcaster Remote is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

OpenBroadcaster Remote is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with OpenBroadcaster Remote.  If not, see <http://www.gnu.org/licenses/>.
"""

import obplayer

import socket
import os
import sys
import signal

from OpenSSL import SSL
from BaseHTTPServer import HTTPServer
from httpserver import ObHTTPRequestHandler


class ObHTTPAdmin(HTTPServer):

    def __init__(self):
	self.root = 'admin'

        self.username = obplayer.Config.setting('http_admin_username')
        self.password = obplayer.Config.setting('http_admin_password')

        sslenable = obplayer.Config.setting('http_admin_secure')
        sslcert = obplayer.Config.setting('http_admin_sslcert')

        server_address = ('', obplayer.Config.setting('http_admin_port'))  # (address, port)

	HTTPServer.__init__(self, server_address, ObHTTPRequestHandler)
	if sslenable:
	    self.socket = ssl.wrap_socket(self.socket, certfile=sslcert, server_side=True)

        sa = self.socket.getsockname()
        obplayer.Log.log('serving http(s) on port ' + str(sa[1]), 'http')

    def log(self, message):
        obplayer.Log.log(message, 'admin')

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
	if(obplayer.Gui.gui_window_fullscreen):
		return 'On'
	else:
		return 'Off'

    def command_restart(self):
	os.kill(os.getpid(), signal.SIGINT)
	return { 'status' : True }

    def command_fstoggle(self):
	obplayer.Gui.fullscreen_toggle(None)
	return { 'status' : True, 'fullscreen' : obplayer.Gui.gui_window_fullscreen }  # + str(not self.Gui.gui_window_fullscreen).lower() + ' }'

    def handle_post(self, path, postvars):
        error = None

	# run through each setting and make sure it's valid. if not, complain.
        for key in postvars:
            settingName = key
            settingValue = postvars[key][0]

            error = obplayer.Config.validateSetting(settingName, settingValue)

            if error != None:
                return { 'status' : False, 'error' : error }

	# we didn't get an errors on validate, so update each setting now.
        for key in postvars:
            settingName = key
            settingValue = postvars[key][0]
            obplayer.Config.set(settingName, settingValue)

        return { 'status' : True }


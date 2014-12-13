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

import os
import sys
import traceback

from BaseHTTPServer import HTTPServer
from BaseHTTPServer import BaseHTTPRequestHandler

from sys import version as python_version
from cgi import parse_header, parse_multipart

import json

if python_version.startswith('3'):
    from urllib.parse import parse_qs
else:
    from urlparse import parse_qs


class ObHTTPRequestHandler(BaseHTTPRequestHandler):
    server_version = "OpenBroadcasterHTTP/0.1"

    extensions = {
	'css' : 'text/css',
	'html' : 'text/html',
	'js' : 'application/javascript',
	'svg' : 'image/svg+xml'
    }

    def log_message(self, format, *args):
        self.server.log(self.address_string() + ' ' + format % args)
        #obplayer.Log.log(self.address_string() + ' ' + format % args, 'http')

    def parse(self, data):

	ret = ''
        while data != '':
            first = data.partition('<%')
	    ret += first[0]
            second = first[2].partition('%>')

	    try:
		if second[0]:
		    ret += str(eval(second[0]))
	    except Exception as e:
		#ret += '<b>Eval Error</b>: ' + '(line ' + str(ret.count('\n') + 1) + ') ' + e.__class__.__name__ + ': ' + e.args[0] + '<br>\n'
		ret += '<b>Eval Error</b>: ' + '(line ' + str(ret.count('\n') + 1) + ') ' + repr(e) + '<br>\n'

	    data = second[2]

        return ret

    def check_authorization(self):

	if not self.server.username:
	    return True

	self.authenticated = False

        authdata = self.headers.getheader('Authorization')
        if type(authdata).__name__ == 'str':
            authdata = authdata.split(' ')[-1].decode('base64')
            username = authdata.split(':')[0]
            password = authdata.split(':')[1]

            if username == self.server.username and password == self.server.password:
                self.authenticated = True

        return self.authenticated

    def send_404(self):
        self.send_response(404)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write('404 Not Found')

    def send_json_headers(self):
	self.send_response(200)
	self.send_header('Content-type', 'application/json')
	self.end_headers()

    def do_GET(self):

        if self.check_authorization() == False:
            self.send_response(401)
            self.send_header('WWW-Authenticate', 'Basic realm="Secure Area"')
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write('Authorization required.')
            return

	# handle commands sent via GET
        if self.path.startswith('/command/'):
	    command = self.path[9:]

	    try:
		command_func = getattr(self.server, 'command_' + self.path[9:])
	    except AttributeError:
		self.send_404()
		return

            self.send_json_headers()
	    ret = command_func()
	    self.wfile.write(json.dumps(ret))
	    return

	if not self.is_valid_path(self.path):
	    self.send_404()
	    return

	filename = self.server.root + '/' + self.path[1:]

	# If the path resolves to a directory, then set the filename to the index.html file inside that directory
	if os.path.isdir(filename):
	    filename = filename.strip('/') + '/index.html'

	# server up the file
	if os.path.isfile(filename):
	    self.extension = self.get_extension(filename)
	    self.mimetype = self.get_mimetype(filename)

	    self.send_response(200)
	    self.send_header('Content-type', self.mimetype)
	    self.end_headers()

	    with open(filename, 'r') as f:
		contents = f.read()
		if self.extension == 'html':
		    contents = self.parse(contents)
		self.wfile.write(contents)
		return

	# send error if nothing found
	self.send_404()

    def do_POST(self):

        if self.check_authorization() == False:
            self.send_response(401)
            self.send_header('WWW-Authenticate', 'Basic realm="Secure Area"')
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write('Authorization required.')
            return

	# empty post doesn't provide a content-type.
	ctype = None
        try:
            (ctype, pdict) = parse_header(self.headers['content-type'])
        except:
	    pass

        if ctype == 'multipart/form-data':
            postvars = parse_multipart(self.rfile, pdict)
        elif ctype == 'application/x-www-form-urlencoded':
            length = int(self.headers['content-length'])
            postvars = parse_qs(self.rfile.read(length), keep_blank_values=True)
        else:
            postvars = {}

        self.send_json_headers()

	ret = self.server.handle_post(self.path, postvars)
	self.wfile.write(json.dumps(ret))

    @staticmethod
    def is_valid_path(path):
	if not path[0] == '/':
	    return False
	for name in path.split('/'):
	    if name == '.' or name == '..':
		return False
	return True

    @staticmethod
    def get_extension(filename):
	return filename.rpartition('.')[2]

    @staticmethod
    def get_mimetype(filename):
	extension = ObHTTPRequestHandler.get_extension(filename)
	if extension in ObHTTPRequestHandler.extensions:
	    return ObHTTPRequestHandler.extensions[extension]
	else:
	    return 'text/plain'



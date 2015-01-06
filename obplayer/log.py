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

import time
import thread

MAX_BACKLOG = 2000

#
# OpenBroadcaster Logging Class
# Provides logging for remote application.  Presently logging outputs to stdout only.
#
class ObLog:

    #
    # Initialization, does nothing at the moment.
    #
    def __init__(self):
	self.datadir = obplayer.ObData.get_datadir()
	self.logbuffer = []
	self.debug = False

	# open log file to write to.
        self.logdate = False
        self.logfile = False

	self.lock = thread.allocate_lock()

    def set_debug(self, flag):
	self.debug = flag

    #
    # Given message, outputs time + message to stdout.
    # mtypes = error, emerg, audio, image, sync
    #
    def log(self, message, mtype='error'):

        mstring = '[' + time.strftime('%b %d %Y %H:%M:%S', time.gmtime()) + ' UTC] [' + mtype + '] ' + message

	self.lock.acquire()

	# write to log file. (filename is present date).
        if self.logdate != time.strftime('%Y.%m.%d'):
            self.logdate = time.strftime('%Y.%m.%d')

            if self.logfile != False:
                self.logfile.close()

            self.logfile = open(self.datadir + '/logs/' + self.logdate + '.obplayer.log', 'a', 1)
        self.logfile.write(mstring + '\n')

	self.logbuffer.append(mstring)
	if len(self.logbuffer) > MAX_BACKLOG:
	    self.logbuffer.pop(0)

	if self.debug:
	    print mstring

	self.lock.release()

        return True

    def get_log(self):
	return self.logbuffer

    def get_in_hms(seconds):
	hours = int(seconds) / 3600
	seconds -= 3600 * hours
	minutes = seconds / 60
	seconds -= 60 * minutes
	return "%02d:%02d:%02d" % (hours, minutes, seconds)


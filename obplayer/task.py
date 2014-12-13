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

import thread
import threading

import traceback

class ObThread (threading.Thread):
    threads = []

    def __init__(self, name=None, target=None):
	threading.Thread.__init__(self, None, target, name)
	ObThread.threads.insert(0, self)
	self.stopflag = threading.Event()

    def remove_thread(self):
	ObThread.threads.remove(self)

    def start(self):
	obplayer.Log.log("starting thread <%s>" % (str(self.name),), 'debug')
	threading.Thread.start(self)

    def stop(self):
	self.stopflag.set()

    @staticmethod
    def stop_all():
	for t in ObThread.threads:
	    t.stop()

    @staticmethod
    def join_all():
	for t in ObThread.threads:
	    if t.daemon is False:
		t.join()
		obplayer.Log.log("thread <%s> has joined successfully" % (str(t.name),), 'debug')
	    else:
		obplayer.Log.log("thread <%s> is daemon, skipping" % (str(t.name),), 'debug')

    """
    def run(self):
	try:
	    if self.__target:
		self.__target(*self.__args, **self.__kwargs)
	except:
	    obplayer.Log.log("exception occurred in thread " + str(self.name) + ":", 'error')
	    obplayer.Log.log(traceback.format_exc(), 'error')
	finally:
	    del self.__target, self.__args, self.__kwargs
    """


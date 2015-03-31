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

from __future__ import absolute_import 

from obplayer.scheduler.scheduler import *
from obplayer.scheduler.sync import *

Sync = None
Scheduler = None

class VersionUpdateThread (obplayer.ObThread):
    def try_run(self):
	obplayer.Sync.version_update()
	self.remove_thread()


class SyncShowsThread (obplayer.ObThread):
    def run(self):
	self.synctime = int(60 * obplayer.Config.setting('sync_freq'))
	while not self.stopflag.wait(self.synctime):
	    try:
		obplayer.Sync.sync_shows()
	    except:
		obplayer.Log.log("exception in " + self.name + " thread", 'error')
		obplayer.Log.log(traceback.format_exc(), 'error')

    # TODO this is temporary until you can have Sync check the stop flags directly
    def stop(self):
	obplayer.ObThread.stop(self)
	obplayer.Sync.quit = True


class SyncPlaylogThread (obplayer.ObThread):
    def run(self):
	if not obplayer.Config.setting('sync_playlog_enable'):
	    self.remove_thread()
	    return

	self.synctime = int(60 * obplayer.Config.setting('sync_freq_log'))
	while not self.stopflag.wait(self.synctime):
	    try:
		obplayer.Sync.sync_playlog()
	    except:
		obplayer.Log.log("exception in " + self.name + " thread", 'error')
		obplayer.Log.log(traceback.format_exc(), 'error')

    def stop(self):
	obplayer.ObThread.stop(self)
	obplayer.Sync.quit = True


class SyncEmergThread (obplayer.ObThread):
    def run(self):
	self.synctime = int(60 * obplayer.Config.setting('sync_freq_emerg'))
	while not self.stopflag.wait(self.synctime):
	    try:
		obplayer.Sync.sync_priority_broadcasts()
	    except:
		obplayer.Log.log("exception in " + self.name + " thread", 'error')
		obplayer.Log.log(traceback.format_exc(), 'error')

    def stop(self):
	obplayer.ObThread.stop(self)
	obplayer.Sync.quit = True


class SyncMediaThread (obplayer.ObThread):
    def run(self):
	self.synctime = int(5)
	while not self.stopflag.wait(self.synctime):
	    try:
		obplayer.Sync.sync_media()
	    except:
		obplayer.Log.log("exception in " + self.name + " thread", 'error')
		obplayer.Log.log(traceback.format_exc(), 'error')

    def stop(self):
	obplayer.ObThread.stop(self)
	obplayer.Sync.quit = True


def init():
    global Sync, Scheduler

    obplayer.Sync = ObSync()
    obplayer.Scheduler = ObScheduler()

    # reset show/show_media tables, priority tables
    if obplayer.Config.args.reset:
	obplayer.Log.log('resetting show, media, and priority data', 'data')
	obplayer.RemoteData.empty_table('shows')
	obplayer.RemoteData.empty_table('shows_media')
	obplayer.RemoteData.empty_table('groups')
	obplayer.RemoteData.empty_table('group_items')
	obplayer.RemoteData.empty_table('priority_broadcasts')

    # determine our version from the VERSION file.  if we can do that, report the version to the server.
    if os.path.exists('VERSION'):
	obplayer.Config.version = open('VERSION').read().strip()
	VersionUpdateThread().start()

    # if resetting the databases, run our initial sync.  otherwise skip and setup other sync interval timers.
    if obplayer.Config.args.reset:
	obplayer.Sync.sync_shows(True)
	obplayer.Sync.sync_priority_broadcasts()
	obplayer.Sync.sync_media()

    # Start sync threads
    SyncShowsThread().start()
    SyncEmergThread().start()
    SyncMediaThread().start()
    SyncPlaylogThread().start()


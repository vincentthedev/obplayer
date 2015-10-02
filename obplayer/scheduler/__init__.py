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
from obplayer.scheduler.priority import *

Sync = None
Scheduler = None

def init():
    global Sync, Scheduler

    obplayer.Sync = ObSync()
    obplayer.Scheduler = ObScheduler()
    obplayer.PriorityBroadcaster = ObPriorityBroadcaster()

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


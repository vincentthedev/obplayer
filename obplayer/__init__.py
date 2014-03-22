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

from __future__ import absolute_import 

import sys

# workaround for gstreamer stealing -h (help) argument.
# thanks to: http://29a.ch/2009/2/14/pygst-messing-with-sys-argv
argv = sys.argv
sys.argv = []

from obplayer.data import *
from obplayer.log import *
from obplayer.sync import *
from obplayer.scheduler import *
from obplayer.player import *
from obplayer.fallback_player import *
from obplayer.httpadmin import *
from obplayer.liveassist import *
from obplayer.gui import *
from obplayer.main import *

sys.argv = argv
del argv

Log = ObLog()
Sync = ObSync()
Config = ObConfigData()
RemoteData = ObRemoteData()
PlaylogData = ObPlaylogData()
Player = ObPlayer()
FallbackPlayer = ObFallbackPlayer()
Scheduler = ObScheduler()
HTTPAdmin = ObHTTPAdmin()
LiveAssist = ObLiveAssist()
Gui = ObGui()
Main = None

def main():
    global Main

    Main = MainApp()
    Main.start()


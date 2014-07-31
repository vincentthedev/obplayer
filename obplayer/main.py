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

import signal
import sys
import os

import gobject
#import gtk

import argparse


class Task (threading.Thread):
    threads = []

    def __init__(self):
	threading.Thread.__init__(self)
	Task.threads.append(self)
	self.stopflag = threading.Event()

    def remove_task(self):
	Task.threads.remove(self)

    def stop(self):
	self.stopflag.set()

    @staticmethod
    def stop_all():
	for t in Task.threads:
	    t.stop()

    @staticmethod
    def join_all():
	for t in Task.threads:
	    t.join()


class SchedulerTask (Task):
    def run(self):
	while not self.stopflag.wait(0.25):
	    obplayer.Scheduler.schedule_loop()
	    obplayer.FallbackPlayer.run()


class HTTPAdminTask (Task):
    def run(self):
	obplayer.HTTPAdmin = obplayer.ObHTTPAdmin()
        obplayer.HTTPAdmin.serve_forever()

    def stop(self):
	if obplayer.HTTPAdmin:
	    obplayer.HTTPAdmin.shutdown()


class LiveAssistTask (Task):
    def run(self):
	obplayer.LiveAssist = obplayer.ObLiveAssist()
        obplayer.LiveAssist.serve_forever()

    def stop(self):
	if obplayer.LiveAssist:
	    obplayer.LiveAssist.shutdown()


class VersionUpdateTask (Task):
    def run(self):
	obplayer.Sync.version_update()
	self.remove_task()


class SyncShowsTask (Task):
    def run(self):
	self.synctime = int(60 * obplayer.Main.timer_scale * obplayer.Config.setting('syncfreq'))
	while not self.stopflag.wait(self.synctime):
	    obplayer.Sync.sync_shows()


class SyncPlaylogTask (Task):
    def run(self):
	self.synctime = int(60 * obplayer.Main.timer_scale * obplayer.Config.setting('syncfreq_log'))
	while not self.stopflag.wait(self.synctime):
	    obplayer.Sync.sync_playlog()


class SyncEmergTask (Task):
    def run(self):
	self.synctime = int(60 * obplayer.Main.timer_scale * obplayer.Config.setting('syncfreq_emerg'))
	while not self.stopflag.wait(self.synctime):
	    obplayer.Sync.sync_emergency_broadcasts()


class SyncMediaTask (Task):
    def run(self):
	self.synctime = int(5 * obplayer.Main.timer_scale)
	while not self.stopflag.wait(self.synctime):
	    obplayer.Sync.sync_media()



class ObMainApp:

    def __init__(self):
	# we can use this to speed up (or slow down) our timer for debugging.
        self.timer_scale = 1

        self.quit = False
        self.sync_run_state = False
	self.stopflag = threading.Event()

        parser = argparse.ArgumentParser(prog='obremote', formatter_class=argparse.ArgumentDefaultsHelpFormatter, description='OpenBroadcaster Remote')
        parser.add_argument('-f', '--fullscreen', action='store_true', help='start fullscreen', default=False)
        parser.add_argument('-m', '--minimize', action='store_true', help='start minimized', default=False)
        parser.add_argument('-r', '--reset', action='store_true', help='reset show, media, and emergency broadcast databases', default=False)
        parser.add_argument('-H', '--headless', action='store_true', help='run headless (audio only)', default=False)
        parser.add_argument('-d', '--debug', action='store_true', help='print log messages to stdout', default=False)
        parser.add_argument('-c', '--configdir', nargs=1, help='specifies an alternate data directory', default=[ None ])
        parser.add_argument('--disable-http', action='store_true', help='disables the http admin', default=False)

        self.args = parser.parse_args()
        self.headless = self.args.headless

	obplayer.Log = obplayer.ObLog()
	obplayer.Log.set_debug(self.args.debug)

	obplayer.Config = obplayer.ObConfigData(self.args.configdir[0])
	obplayer.RemoteData = obplayer.ObRemoteData(self.args.configdir[0])
	obplayer.PlaylogData = obplayer.ObPlaylogData(self.args.configdir[0])

	obplayer.Sync = obplayer.ObSync()
	obplayer.Player = obplayer.ObPlayer()
	obplayer.FallbackPlayer = obplayer.ObFallbackPlayer()
	obplayer.Scheduler = obplayer.ObScheduler()

	obplayer.Gui = obplayer.ObGui()
	obplayer.Main = self

    def start(self):

	gobject.threads_init()
	signal.signal(signal.SIGINT, self.sigint_handler)

	obplayer.Gui.create_window()
        obplayer.Player.player_init()

	# reset show/show_media tables, emergency tables
        if self.args.reset:
            obplayer.Log.log('resetting show, media, and emergency data', 'data')
            obplayer.RemoteData.empty_table('shows')
            obplayer.RemoteData.empty_table('shows_media')
            obplayer.RemoteData.empty_table('groups')
            obplayer.RemoteData.empty_table('group_items')
            obplayer.RemoteData.empty_table('emergency_broadcasts')

	# run our admin web server.
        if self.args.disable_http is False:
	    HTTPAdminTask().start()

	# determine our version from the VERSION file.  if we can do that, report the version to the server.
        if os.path.exists('VERSION'):
            self.version = open('VERSION').read().strip()
	    VersionUpdateTask().start()

	# if resetting the databases, run our initial sync.  otherwise skip and setup other sync interval timers.
        if self.args.reset:
	    obplayer.Sync.sync_shows(True)
	    obplayer.Sync.sync_emergency_broadcasts()
	    obplayer.Sync.sync_media()

	# run our live assist web server.
        if obplayer.Config.setting('live_assist_enable'):
	    LiveAssistTask().start()

	# Start scheduler thread
	SchedulerTask().start()

	# Start sync threads
	SyncShowsTask().start()
	SyncPlaylogTask().start()
	SyncEmergTask().start()
	SyncMediaTask().start()

	self.loop = gobject.MainLoop()
        self.loop.run()
	#gtk.main()

	self.application_shutdown(False)

    def sigint_handler(self, signal, frame):
	#gtk.main_quit()
	self.loop.quit()
        #self.application_shutdown(False)

    def application_shutdown(self, widget):

	# backup our main db to disk.
        obplayer.RemoteData.backup()

        self.quit = True

	# send stop signals to all threads
	Task.stop_all()

	# wait for all threads to complete
	Task.join_all()

	# quit main thread.
        sys.exit(0)



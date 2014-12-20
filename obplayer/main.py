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

import sys
import time
import signal
import traceback

import argparse

import gi
from gi.repository import GObject

GObject.threads_init()


class ObMainApp:

    def __init__(self):
        parser = argparse.ArgumentParser(prog='obplayer', formatter_class=argparse.ArgumentDefaultsHelpFormatter, description='OpenBroadcaster Player')
        parser.add_argument('-f', '--fullscreen', action='store_true', help='start fullscreen', default=False)
        parser.add_argument('-m', '--minimize', action='store_true', help='start minimized', default=False)
        parser.add_argument('-r', '--reset', action='store_true', help='reset show, media, and emergency broadcast databases', default=False)
        parser.add_argument('-H', '--headless', action='store_true', help='run headless (audio only)', default=False)
        parser.add_argument('-d', '--debug', action='store_true', help='print log messages to stdout', default=False)
        parser.add_argument('-c', '--configdir', nargs=1, help='specifies an alternate data directory', default=[ None ])
        parser.add_argument('--disable-http', action='store_true', help='disables the http admin', default=False)

        self.args = parser.parse_args()

	obplayer.Log = obplayer.ObLog()
	obplayer.Log.set_debug(self.args.debug)

	obplayer.Config = obplayer.ObConfigData(self.args.configdir[0])
	obplayer.RemoteData = obplayer.ObRemoteData(self.args.configdir[0])
	obplayer.PlaylogData = obplayer.ObPlaylogData(self.args.configdir[0])

	obplayer.Config.args = self.args
        obplayer.Config.headless = self.args.headless

	obplayer.Main = self

    def start(self):

	signal.signal(signal.SIGINT, self.sigint_handler)

	try:
	    self.loop = GObject.MainLoop()

	    obplayer.Gui = obplayer.ObGui()
	    obplayer.Gui.create_window()

	    obplayer.Player = obplayer.ObPlayer()

	    self.load_module('httpadmin')
	    if obplayer.Config.setting('alerts_enable'):
		self.load_module('alerts')
	    if obplayer.Config.setting('scheduler_enable'):
		self.load_module('scheduler')
	    if obplayer.Config.setting('fallback_enable'):
	    	self.load_module('fallback')
	    if obplayer.Config.setting('live_assist_enable'):
		self.load_module('liveassist')

	    #### TEST CODE ####

	    #time.sleep(2)

	    #alert = obplayer.alerts.parse_alert_file("/media/work/Projects/OpenBroadcaster/Information/2014-08 Pelmorex Tie-In/CAP Examples/2example_CAPCP_with_Embedded_Large_Audio_File(2).xml")
	    #alert = obplayer.alerts.parse_alert_file("/media/work/Projects/OpenBroadcaster/Information/2014-08 Pelmorex Tie-In/CAP Examples/4example_CAPCP_with_External_Large_Audio_File(2).xml")
	    #obplayer.alerts.Processor.dispatch(alert)

	    ctrl = obplayer.Player.create_controller('testsource', 30, default_play_mode='overlap')
	    #ctrl.add_request(media_type='testsignal', duration=5)
	    #ctrl.add_request(media_type='video', file_location="/home/trans/.openbroadcaster/fallback_media/", filename="110-Unknown-The_Return_Of_Doctor_X.ogg", duration=153)
	    #ctrl.add_request(media_type='audio', start_time=time.time() + 5, file_location="/home/trans/.openbroadcaster/alerts/", filename="2014_12_01T00_13_00_00_00I2.49.0.1.124.b7fb9ec4.2014", duration=10)
	    #ctrl.add_request(media_type='video', file_location="/home/trans/.openbroadcaster/fallback_media/", filename="110-Unknown-The_Return_Of_Doctor_X.ogg", duration=153)
	    #ctrl.add_request(media_type='image', start_time=time.time(), file_location="/home/trans/.openbroadcaster/fallback_media/", filename="97-ctfn_potlatch-sdfsdg.svg", duration=30)
	    #ctrl.add_request(media_type='audio', start_time=time.time(), file_location="/home/trans/.openbroadcaster/fallback_media/", filename="104-Lamb-Piste_6.mp3", duration=70)
	    #ctrl.add_request(media_type='audio', start_time=time.time(), file_location="/home/trans/.openbroadcaster/fallback_media/", filename="104-Lamb-Piste_6.mp3", duration=70)
	    #ctrl.add_request(media_type='video', start_time=time.time() + 2, file_location="/home/trans/.openbroadcaster/fallback_media/", filename="109-Unknown-The_Pit_And_The_Pendulum.ogg", duration=153)

	    alertctrl = obplayer.Player.create_controller('testalert', 100, default_play_mode='overlap', allow_overlay=True)
	    #alertctrl.add_request(media_type='audio', start_time=time.time() + 7, file_location="obplayer/alerts/data", filename="attention-signal.ogg", duration=4)
	    #alertctrl.add_request(media_type='audio', file_location="/home/trans/.openbroadcaster/alerts/", filename="2014_12_01T00_13_00_00_00I2.49.0.1.124.b7fb9ec4.2014", duration=5)

	    #### END TEST CODE ####

	    obplayer.Player.start_player()
	    self.loop.run()
	except KeyboardInterrupt:
	    print "Keyboard Interrupt"
	except:
	    obplayer.Log.log("exception occurred in main thead. Terminating...", 'error')
	    obplayer.Log.log(traceback.format_exc(), 'error')

	self.application_shutdown()

    def quit(self):
	self.loop.quit()

    def sigint_handler(self, signal, frame):
	self.loop.quit()

    def application_shutdown(self):
	# backup our main db to disk.
        obplayer.RemoteData.backup()

	# send stop signals to all threads
	obplayer.ObThread.stop_all()

	# wait for all threads to complete
	obplayer.ObThread.join_all()

	# quit main thread.
        sys.exit(0)

    def load_module(self, name):
	obplayer.Log.log('loading module ' + name, 'module')
	exec 'import obplayer.%s; obplayer.%s.init()' % (name, name)



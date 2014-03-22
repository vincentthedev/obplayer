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

import pygst
pygst.require('0.10')
import gst
import os
import time

import gtk

import threading

#
#
# Class to manage output of playing of data.
#
class ObPlayer:

    #
    # Initialize audio/video.  Creates instance of OBConfig, establishes gstreamer pipeline based on output specified in config.
    #
    def __init__(self):
        self.media_stop_timestamp = 0  # keep track of when media is supposed to play for (required for 'is_playing').
        self.media_mode = None
        self.player = None
	self.now_playing = None

    def player_init(self, media):

	# nothing to do if we're playing an image, unless this is the initial init.
        if self.player and media['media_type'] == 'image':
            return

        if self.player:
            self.player.set_state(gst.STATE_NULL)
            self.sync_state()

        self.player = gst.element_factory_make('playbin2', 'player')

        audio_output = obplayer.Config.setting('audio_output')
        if audio_output == 'alsa':
            self.sc_sink = gst.element_factory_make('alsasink', 'sc_sink')
            alsa_device = obplayer.Config.setting('alsa_device')
            if alsa_device != '':
                self.sc_sink.set_property('device', alsa_device)

        elif audio_output == 'esd':
            self.sc_sink = gst.element_factory_make('esdsink', 'sc_sink')

        elif audio_output == 'jack':
            self.sc_sink = gst.element_factory_make('jackaudiosink', 'sc_sink')
            self.sc_sink.set_property('connect', 0)  # don't autoconnect ports.

        elif audio_output == 'oss':
            self.sc_sink = gst.element_factory_make('osssink', 'sc_sink')

        elif audio_output == 'pulse':
            self.sc_sink = gst.element_factory_make('pulsesink', 'sc_sink')

        elif audio_output == 'test':
            self.sc_sink = gst.element_factory_make('fakesink', 'sc_sink')

        else:
	    # this is stdout audio output (experimental, some possibility to use with streaming but doesn't propery output silence as audio data).
            self.sc_sink = gst.element_factory_make('autoaudiosink', 'sc_sink')

        self.player.set_property('audio-sink', self.sc_sink)

        if obplayer.Config.setting('audiovis'):
            self.audiovis = gst.element_factory_make('libvisual_jess')
            self.player.set_property('flags', self.player.get_property('flags') | 0x00000008)
            self.player.set_property('vis-plugin', self.audiovis)

        self.bus = self.player.get_bus()
        #self.bus.set_sync_handler(self.sync_handler)
	self.bus.add_signal_watch()
	self.bus.enable_sync_message_emission()
	self.bus.connect("sync-message::element", self.sync_handler)

	# wait for state change.
        if self.sync_state() == False:
            obplayer.Log.log('ObPlayer.init wait for state change (sync_state()) failed (after stop).', 'error')


    def change_media_mode(self,mode):
	if obplayer.Main.headless:
	    return

	if mode == 'image' or (mode == 'audio' and obplayer.Config.setting('audiovis') == 0):
	    #obplayer.Gui.gui_gst_area_viewport.hide()
	    #obplayer.Gui.gui_drawing_area_viewport.show()
	    pass

	else:
	    #obplayer.Gui.gui_drawing_area_viewport.hide()
	    #obplayer.Gui.gui_gst_area_viewport.show()
	    pass

	self.media_mode = mode

    #
    #
    # Play file.
    #
    # filename (string) : name of file to play (in media directory)
    # offset (int) : how many seconds into the file to begin playing.  Specify 0 to play from beginning (default).
    #
    def play(self, media, offset=0, context='show', emerg_id=''):

        self.player_init(media)

	# self.media_stop_timestamp = 0; # reset the image stop timestamp (required for 'is_playing').
	#
	# file location specified explicitly
        if media['file_location'][0] == '/':
            media_filename = media['file_location'] + '/' + media['filename']
        else:

	    # file location specified as 2-character directory code.
            media_filename = obplayer.Config.setting('remote_media') + '/' + media['file_location'][0] + '/' + media['file_location'][1] + '/' + media['filename']

	# see if the file exists.  if not, return false...
        if os.path.exists(media_filename) == False:
            return False

	# write entry into play log.
        if offset == 0:
            playlog_notes = ''
        else:
            playlog_notes = 'resuming at ' + str(offset) + 's'
        obplayer.PlaylogData.playlog_add(media['media_id'], media['artist'], media['title'], time.time(), context, emerg_id, playlog_notes)

        if media['media_type'] == 'audio':
            self.stop('av')
        elif media['media_type'] == 'image':
            self.stop('image')
        else:
            self.stop('all')

	# wait for state change.  could also watch for state change message in bus (non-locking)
        if self.sync_state() == False:
            obplayer.Log.log('ObPlayer.play wait for state change (sync_state()) failed (after stop).', 'error')

        if media['media_type'] == 'audio' or media['media_type'] == 'video':
	    self.now_playing = media

	    if media['media_type'] == 'audio':
		self.change_media_mode('audio')

	    if media['media_type'] == 'video':
		self.change_media_mode('video')

	    # print 'audio: play '+filename;
            self.player.set_state(gst.STATE_READY)

	    # wait for state change.  could also watch for state change message in bus (non-locking)
            if self.sync_state() == False:
                obplayer.Log.log('ObPlayer.play wait for state change (sync_state()) failed (after setting state to ready).', 'error')

            self.player.set_property('uri', 'file://' + media_filename)

            self.player.set_state(gst.STATE_PAUSED)
	    # wait for state change.  could also watch for state change message in bus (non-locking)
            if self.sync_state() == False:
                obplayer.Log.log('ObPlayer.play wait for state change (sync_state()) failed (after setting state to paused).', 'error')

            if obplayer.Config.setting('gst_init_callback'):
                os.system(obplayer.Config.setting('gst_init_callback'))

            if offset != 0:
                if self.player.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, offset * gst.SECOND) == False:
                    obplayer.Log.log('unable to seek on this track', 'error')

            self.player.set_state(gst.STATE_PLAYING)

	    # wait for state change.  could also watch for state change message in bus (non-locking)
            if self.sync_state() == False:
                obplayer.Log.log('ObPlayer.play wait for state change (sync_state()) failed (after setting state to playing).', 'error')

	# remote image from display if applicable.
	# self.Gui.drawing_area_image_update();

        if media['order_num']:
            track_num = ' ' + str(media['order_num'] + 1)
        else:
            track_num = ''

        self.media_stop_timestamp = max(self.media_stop_timestamp, time.time() + media['duration'] - offset)  # keep track of when this is supposed to play until. (required to check 'is playing').

        obplayer.Log.log('now playing track' + str(track_num) + ': ' + unicode(media['artist']).encode('ascii', 'replace') + ' - ' + unicode(media['title']).encode('ascii', 'replace') + ' (id: '
                     + str(media['media_id']) + ' file: ' + unicode(media['filename']).encode('ascii', 'replace') + ')', 'player')
        if offset > 0:
            obplayer.Log.log('resuming track at ' + str(offset) + ' seconds.', 'player')

	#
	# empty out the bus (not using it at the moment anyway).
        while self.bus.have_pending():
            self.bus.pop()

        return True

    #
    # Stop playing audio.
    #
    def stop(self, mode='all'):
        if mode == 'av' or mode == 'all':
	    # print 'stopping av';
            self.player.set_state(gst.STATE_NULL)
	    self.now_playing = None

    #
    # Cleanup before quitting audio application.  Presently sets gstreamer pipeline state to 'NULL' (stopped).
    #
    def quit(self):
        self.player.set_state(gst.STATE_NULL)

	# wait for state change.  could also watch for state change message in bus (non-locking)
        if self.sync_state() == False:
            obplayer.Log.log('ObPlayer.quit wait for state change (sync_state()) failed (after setting state to null).', 'error')

    # sync handler (assigns video sink to drawing area)
    def sync_handler(self, bus, message):

        if message.structure is None:
            return gst.BUS_PASS

        if message.structure.get_name() == 'prepare-xwindow-id':
            message.src.set_property('force-aspect-ratio', True)
	    #print threading.current_thread()
	    #gtk.gdk.threads_enter()
	    #message.src.set_xwindow_id(obplayer.Gui.gui_gst_area.window.xid);
	    #gtk.gdk.threads_leave()

	# pass to async queue.
        return gst.BUS_PASS

    # wait for state change, up to 5 seconds.
    def sync_state(self):
        statechange = self.player.get_state(timeout=5 * gst.SECOND)[0]
        if statechange == gst.STATE_CHANGE_SUCCESS:
            return True
        else:
            return False

    # get the status (state) of the pipline (debug)
    def status(self):
	if not self.player:
	    return True
        if self.player.get_state()[1] == gst.STATE_PLAYING:
            return False
        else:
            return str(self.player.get_state())

    def is_playing(self):
	# check if we've been stopped for more than 0.5seconds (i.e., give the scheduler a chance to play something).
        if self.media_stop_timestamp - time.time() > -0.5:
            return True
        else:
            return False



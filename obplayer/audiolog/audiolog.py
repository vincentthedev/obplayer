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

import os
import time
import traceback

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

AUDIOLOG_SAMPLE_RATE = '22050'
AUDIOLOG_CHANNELS = '1'

class ObAudioLog (object):
    def __init__(self):
        self.pipeline = None
        self.date = time.strftime('%Y-%m-%d-%H')
        self.start()

    def start(self):
        obplayer.Log.log("starting new audio log", 'audiolog')
        outfile = obplayer.ObData.get_datadir() + '/audiologs/' + time.strftime('%Y-%m-%d_%H:%M:%S') + '.ogg'

        audio_output = obplayer.Config.setting('audio_out_mode')
        #launchcmd = 'pulsesrc device=' + self.args.alsa_device \
        launchcmd = 'pulsesrc client-name="obplayer-audiolog"' \
                    + ' ! audioconvert ! audioresample ' \
                    + ' ! audio/x-raw, rate=' + AUDIOLOG_SAMPLE_RATE + ', channels=' + AUDIOLOG_CHANNELS \
                    + ' ! queue ! vorbisenc quality=0.0 ! oggmux ! queue ! filesink location=' + outfile

        self.pipeline = Gst.parse_launch(launchcmd)
        self.pipeline.set_state(Gst.State.PLAYING)
        self.log_rotate()

    def stop(self):
        self.pipeline.set_state(Gst.State.NULL)
        self.pipeline = None

    def log_rotate(self):
        if self.date != time.strftime('%Y-%m-%d-%H'):
            self.date = time.strftime('%Y-%m-%d-%H')
            self.stop()
            self.start()
        GObject.timeout_add(10.0, self.log_rotate)



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
import traceback

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst, GstVideo, GstController

from obplayer.player.pipes.base import ObGstPipeline


"""
class ObBreakPipeline (ObGstPipeline):
    output_caps = [ 'audio' ]

    def __init__(self, name, player):
        ObGstPipeline.__init__(self, name)
        self.player = player

    def patch(self, mode):
        # we don't have to do anything because the output patched to us will just remain disconnected
        ObGstPipeline.patch(self, mode)

    def unpatch(self, mode):
        # we don't have to do anything because the output patched to us will just remain disconnected
        ObGstPipeline.unpatch(self, mode)
"""


class ObBreakPipeline (ObGstPipeline):
    min_class = [ 'audio' ]
    max_class = [ 'audio' ]

    def __init__(self, name, player):
        ObGstPipeline.__init__(self, name)
        self.player = player

        self.pipeline = Gst.Pipeline()
        self.audiotestsrc = Gst.ElementFactory.make('audiotestsrc')
        self.pipeline.add(self.audiotestsrc)
        self.audiosink = None

        self.fakesink = Gst.ElementFactory.make('fakesink')

        self.set_property('audio-sink', self.fakesink)
        self.audiotestsrc.set_property('wave', 4)       # silence
        self.audiotestsrc.set_property('is-live', True)

        self.register_signals()

    def set_property(self, property, value):
        if property == 'audio-sink':
            if self.audiosink:
                self.pipeline.remove(self.audiosink)
            self.audiosink = value
            if self.audiosink:
                self.pipeline.add(self.audiosink)
                self.audiotestsrc.link(self.audiosink)

    def patch(self, mode):
        self.wait_state(Gst.State.NULL)
        if 'audio' in mode:
            self.set_property('audio-sink', self.player.outputs['audio'].get_bin())
        ObGstPipeline.patch(self, mode)
        self.wait_state(Gst.State.PLAYING)
        if obplayer.Config.setting('gst_init_callback'):
            os.system(obplayer.Config.setting('gst_init_callback'))

    def unpatch(self, mode):
        self.wait_state(Gst.State.NULL)
        if 'audio' in mode:
            self.set_property('audio-sink', self.fakesink)
        ObGstPipeline.unpatch(self, mode)
        if len(self.mode) > 0:
            self.wait_state(Gst.State.PLAYING)
            if obplayer.Config.setting('gst_init_callback'):
                os.system(obplayer.Config.setting('gst_init_callback'))



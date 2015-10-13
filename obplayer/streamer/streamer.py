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


class ObStreamer (object):
    def __init__(self):
        self.pipeline = Gst.Pipeline()

        self.elements = [ ]

        audio_input = obplayer.Config.setting('streamer_audio_in_mode')
        if audio_input == 'alsa':
            self.audiosrc = Gst.ElementFactory.make('alsasrc', 'audiosrc')
            alsa_device = obplayer.Config.setting('streamer_audio_in_alsa_device')
            if alsa_device != '':
                self.audiosrc.set_property('device', alsa_device)

        elif audio_input == 'jack':
            self.audiosrc = Gst.ElementFactory.make('jackaudiosrc', 'audiosrc')
            self.audiosrc.set_property('connect', 0)  # don't autoconnect ports.
            name = obplayer.Config.setting('streamer_audio_in_jack_name')
            self.audiosrc.set_property('client-name', name if name else 'obplayer')

        elif audio_input == 'oss':
            self.audiosrc = Gst.ElementFactory.make('osssrc', 'audiosrc')

        elif audio_input == 'pulse':
            self.audiosrc = Gst.ElementFactory.make('pulsesrc', 'audiosrc')

        elif audio_input == 'test':
            self.audiosrc = Gst.ElementFactory.make('fakesrc', 'audiosrc')

        else:
            self.audiosrc = Gst.ElementFactory.make('autoaudiosrc', 'audiosrc')

        self.elements.append(self.audiosrc)


        """
        self.level = Gst.ElementFactory.make("level", "level")
        self.level.set_property('message', True)
        self.level.set_property('interval', int(1.0 * Gst.SECOND))
        self.elements.append(self.level)

        self.selector = Gst.ElementFactory.make("valve", "selector")
        self.selector.set_property('drop', True)
        self.is_dropping = True
        self.pipeline.get_bus().add_signal_watch()
        self.pipeline.get_bus().connect('message::element', self.detect_silence)
        self.elements.append(self.selector)
        """

        self.encoder = Gst.ElementFactory.make("lamemp3enc", "lamemp3enc")
        self.elements.append(self.encoder)

        self.shout2send = Gst.ElementFactory.make("shout2send", "shout2send")
        self.shout2send.set_property('ip', obplayer.Config.setting('streamer_shoutcast_ip'))
        self.shout2send.set_property('port', int(obplayer.Config.setting('streamer_shoutcast_port')))
        self.shout2send.set_property('password', obplayer.Config.setting('streamer_shoutcast_password'))
        self.shout2send.set_property('mount', obplayer.Config.setting('streamer_shoutcast_mount'))
        self.elements.append(self.shout2send)

        self.build_pipeline(self.elements)


    def build_pipeline(self, elements):
        for element in elements:
            #print "adding element to bin: " + element.get_name()
            self.pipeline.add(element)
        for index in range(0, len(elements) - 1):
            elements[index].link(elements[index + 1])

    def start(self):
        self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self):
        self.pipeline.set_state(Gst.State.NULL)

    def quit(self):
        self.pipeline.set_state(Gst.State.NULL)

    def detect_silence(self, bus, message, *args):
        peak = message.get_structure().get_value('peak')
        if peak[0] < -28:
            if not self.is_dropping:
                self.is_dropping = True
                self.selector.set_property('drop', True)
                print "now dropping buffers"
        else:
            if self.is_dropping:
                self.is_dropping = False
                self.selector.set_property('drop', False)
                print "now outputting buffers"
        return True



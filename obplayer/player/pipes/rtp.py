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
from gi.repository import GObject, Gst, GstVideo

from obplayer.player.pipes.base import ObGstPipeline


class ObRTPInputPipeline (ObGstPipeline):
    min_class = [ 'audio' ]
    max_class = [ 'audio' ]

    def __init__(self, name, player):
        ObGstPipeline.__init__(self, name)
        self.player = player

        self.pipeline = Gst.Pipeline()
        self.elements = [ ]

        self.prequeue = Gst.ElementFactory.make('queue2')
        self.elements.append(self.prequeue)

        self.rtpdepay = Gst.ElementFactory.make('rtpopusdepay')
        self.elements.append(self.rtpdepay)

        self.decoder = Gst.ElementFactory.make('opusdec')
        self.decoder.set_property('plc', True)  # Packet loss concealment
        self.decoder.set_property('use-inband-fec', True)  # FEC
        self.elements.append(self.decoder)

        self.audioconvert = Gst.ElementFactory.make('audioconvert')
        self.elements.append(self.audioconvert)
        self.audioresample = Gst.ElementFactory.make('audioresample')
        self.audioresample.set_property('quality', 6)
        self.elements.append(self.audioresample)

        self.postqueue = Gst.ElementFactory.make('queue2')
        self.elements.append(self.postqueue)

        self.build_pipeline(self.elements)

        ## Hook up RTPBin
        self.udpsrc_rtp = Gst.ElementFactory.make('udpsrc')
        self.udpsrc_rtp.set_property('port', 5004)
        self.udpsrc_rtp.set_property('caps', Gst.Caps.from_string("application/x-rtp,payload=96,media=audio,clock-rate=48000,encoding-name=OPUS"))
        #self.udpsrc_rtp.set_property('caps', Gst.Caps.from_string("application/x-rtp,media=audio,channels=1,clock-rate=44100,encoding-name=L16"))
        #self.udpsrc_rtp.set_property('timeout', 3000000)
        #self.elements.append(self.udpsrc_rtp)
        self.pipeline.add(self.udpsrc_rtp)

        self.udpsrc_rtcp = Gst.ElementFactory.make('udpsrc')
        self.udpsrc_rtcp.set_property('port', 5004 + 1)
        self.pipeline.add(self.udpsrc_rtcp)

        self.rtpbin = Gst.ElementFactory.make('rtpbin')
        #self.rtpbin.set_property('latency', 2000)
        #self.rtpbin.set_property('autoremove', True)
        #self.rtpbin.set_property('do-lost', True)
        #self.rtpbin.set_property('buffer-mode', 1)
        self.rtpbin.set_property('drop-on-latency', True)
        #self.elements.append(self.rtpbin)
        self.pipeline.add(self.rtpbin)

        self.udpsrc_rtp.link_pads('src', self.rtpbin, 'recv_rtp_sink_0')
        self.udpsrc_rtcp.link_pads('src', self.rtpbin, 'recv_rtcp_sink_0')

        def rtpbin_pad_added(obj, pad):
            self.rtpbin.unlink(self.elements[0])
            self.rtpbin.link(self.elements[0])
        self.rtpbin.connect('pad-added', rtpbin_pad_added)

        self.audiosink = None
        self.fakesink = Gst.ElementFactory.make('fakesink')
        self.set_property('audio-src', self.fakesink)

        self.register_signals()
        #self.bus.connect("message", self.message_handler_rtp)
        #self.bus.add_signal_watch()

    def start(self):
        # We start the pipe without waiting because it wont enter the playing state until the transmitting end is connected 
        self.pipeline.set_state(Gst.State.PLAYING)

    def set_property(self, property, value):
        if property == 'audio-sink':
            if self.audiosink:
                self.pipeline.remove(self.audiosink)
            self.audiosink = value
            if self.audiosink:
                self.pipeline.add(self.audiosink)
                self.elements[-1].link(self.audiosink)

    def patch(self, mode):
        self.wait_state(Gst.State.NULL)
        if 'audio' in mode:
            self.set_property('audio-sink', self.player.outputs['audio'].get_bin())
        ObGstPipeline.patch(self, mode)

        self.pipeline.set_state(Gst.State.PLAYING)

        if obplayer.Config.setting('gst_init_callback'):
            os.system(obplayer.Config.setting('gst_init_callback'))

    def unpatch(self, mode):
        self.wait_state(Gst.State.NULL)
        if 'audio' in mode:
            self.set_property('audio-sink', self.fakesink)
        ObGstPipeline.unpatch(self, mode)
        if len(self.mode) > 0:
            self.pipeline.set_state(Gst.State.PLAYING)

            if obplayer.Config.setting('gst_init_callback'):
                os.system(obplayer.Config.setting('gst_init_callback'))

    def message_handler_rtp(self, bus, message):
        if message.type == Gst.MessageType.ERROR:
            obplayer.Log.log("attempting to restart pipeline", 'info')
            GObject.timeout_add(1.0, self.restart_pipeline)

    def restart_pipeline(self):
        self.wait_state(Gst.State.NULL)
        self.wait_state(Gst.State.PLAYING)



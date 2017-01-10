#!/usr/bin/python3
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
import threading
import traceback

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

output_settings = {
    '240p': (426, 240, 700),
    '360p': (640, 360, 1000),
    '480p': (854, 480, 2000),
    '720p': (1280, 720, 4000),
}


class ObYoutubeStreamer (object):
    def __init__(self):
        self.pipeline = Gst.Pipeline()

        self.mode = output_settings[obplayer.Config.setting('streamer_youtube_mode')]

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.message_handler)

        obplayer.Player.add_inter_tap('youtube')

        self.audiopipe = [ ]

        self.interaudiosrc = Gst.ElementFactory.make('interaudiosrc')
        self.interaudiosrc.set_property('channel', 'youtube:audio')
        #self.interaudiosrc.set_property('buffer-time', 8000000000)
        #self.interaudiosrc.set_property('latency-time', 8000000000)
        self.audiopipe.append(self.interaudiosrc)

        #self.audiopipe.append(Gst.ElementFactory.make("audiotestsrc"))
        #self.audiopipe[-1].set_property('is-live', True)

        caps = Gst.ElementFactory.make('capsfilter')
        caps.set_property('caps', Gst.Caps.from_string("audio/x-raw,channels=2,channel-mask=(bitmask)=0x3"))
        self.audiopipe.append(caps)

        self.audiopipe.append(Gst.ElementFactory.make("queue2"))

        self.audiopipe.append(Gst.ElementFactory.make("audioconvert"))
        self.audiopipe.append(Gst.ElementFactory.make("audioresample"))

        caps = Gst.ElementFactory.make('capsfilter')
        caps.set_property('caps', Gst.Caps.from_string("audio/x-raw,channels=2,rate=44100"))
        #caps.set_property('caps', Gst.Caps.from_string("audio/x-raw,channels=2,rate=48000"))
        self.audiopipe.append(caps)

        self.encoder = Gst.ElementFactory.make("voaacenc")
        #self.encoder = Gst.ElementFactory.make("lamemp3enc")
        #self.encoder = Gst.ElementFactory.make("opusenc")
        #self.encoder = Gst.ElementFactory.make("vorbisenc")
        self.audiopipe.append(self.encoder)

        self.audiopipe.append(Gst.ElementFactory.make("queue2"))

        self.build_pipeline(self.audiopipe)


        self.videopipe = [ ]

        self.intervideosrc = Gst.ElementFactory.make('intervideosrc')
        self.intervideosrc.set_property('channel', 'youtube:video')
        self.videopipe.append(self.intervideosrc)

        #self.videopipe.append(Gst.ElementFactory.make("videotestsrc"))
        #self.videopipe[-1].set_property('is-live', True)

        self.videopipe.append(Gst.ElementFactory.make("queue2"))

        self.videopipe.append(Gst.ElementFactory.make("videorate"))
        self.videopipe.append(Gst.ElementFactory.make("videoconvert"))
        self.videopipe.append(Gst.ElementFactory.make("videoscale"))

        caps = Gst.ElementFactory.make('capsfilter', "videocapsfilter")
        #caps.set_property('caps', Gst.Caps.from_string("video/x-raw,width=384,height=288,framerate=15/1"))
        #caps.set_property('caps', Gst.Caps.from_string("video/x-raw,width=100,height=75,framerate=15/1"))
        #caps.set_property('caps', Gst.Caps.from_string("video/x-raw,width=384,height=288,framerate=15/1"))
        #caps.set_property('caps', Gst.Caps.from_string("video/x-raw,width=320,height=200,framerate=24/1,pixel-aspect-ratio=1/1"))
        caps.set_property('caps', Gst.Caps.from_string("video/x-raw,width={0},height={1},framerate=30/1,pixel-aspect-ratio=1/1".format(self.mode[0], self.mode[1])))
        self.videopipe.append(caps)

        #self.videopipe.append(Gst.ElementFactory.make("vp8enc"))
        #self.videopipe.append(Gst.ElementFactory.make("vp9enc"))
        #self.videopipe.append(Gst.ElementFactory.make("theoraenc"))
        self.videopipe.append(Gst.ElementFactory.make("x264enc"))
        self.videopipe[-1].set_property('bitrate', self.mode[2])
        self.videopipe[-1].set_property('bframes', 2)
        self.videopipe[-1].set_property('tune', 0x4)
        self.videopipe[-1].set_property('key-int-max', 60)

        self.videopipe.append(Gst.ElementFactory.make("queue2"))

        self.build_pipeline(self.videopipe)


        self.commonpipe = [ ]

        self.commonpipe.append(Gst.ElementFactory.make("flvmux"))
        #self.commonpipe.append(Gst.ElementFactory.make("oggmux"))
        #self.commonpipe.append(Gst.ElementFactory.make("webmmux"))
        self.commonpipe[-1].set_property('streamable', True)

        self.commonpipe.append(Gst.ElementFactory.make("queue2"))

        self.commonpipe.append(Gst.ElementFactory.make("rtmpsink"))
        self.commonpipe[-1].set_property('location', "rtmp://a.rtmp.youtube.com/live2/x/" + obplayer.Config.setting('streamer_youtube_key'))

        """
        self.shout2send = Gst.ElementFactory.make("shout2send", "shout2send")
        self.shout2send.set_property('ip', obplayer.Config.setting('streamer_icecast_ip'))
        self.shout2send.set_property('port', int(obplayer.Config.setting('streamer_icecast_port')))
        self.shout2send.set_property('password', obplayer.Config.setting('streamer_icecast_password'))
        self.shout2send.set_property('mount', obplayer.Config.setting('streamer_icecast_mount'))
        self.shout2send.set_property('streamname', obplayer.Config.setting('streamer_icecast_streamname'))
        self.shout2send.set_property('description', obplayer.Config.setting('streamer_icecast_description'))
        self.shout2send.set_property('url', obplayer.Config.setting('streamer_icecast_url'))
        self.shout2send.set_property('public', obplayer.Config.setting('streamer_icecast_public'))
        self.shout2send.set_property('async', False)
        self.shout2send.set_property('sync', False)
        self.shout2send.set_property('qos', True)
        self.commonpipe.append(self.shout2send)
        """

        #self.commonpipe.append(Gst.ElementFactory.make("filesink"))
        #self.commonpipe[-1].set_property('location', "/home/trans/test.webm")

        self.build_pipeline(self.commonpipe)

        self.audiopipe[-1].link(self.commonpipe[0])
        self.videopipe[-1].link(self.commonpipe[0])


    def message_handler(self, bus, message):
        if message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            obplayer.Log.log("gstreamer error: %s, %s, %s" % (err, debug, err.code), 'error')
            obplayer.Log.log("attempting to restart youtube streaming pipeline", 'info')
            GObject.timeout_add(5000, self.restart_pipeline)

        elif message.type == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            obplayer.Log.log("gstreamer warning: %s, %s, %s" % (err, debug, err.code), 'warning')

        elif message.type == Gst.MessageType.INFO:
            err, debug = message.parse_info()
            obplayer.Log.log("gstreamer info: %s, %s, %s" % (err, debug, err.code), 'info')

    def restart_pipeline(self):
        self.wait_state(Gst.State.NULL)
        self.wait_state(Gst.State.PLAYING)

    def build_pipeline(self, elements):
        for element in elements:
            #print("adding element to bin: " + element.get_name())
            self.pipeline.add(element)
        for index in range(0, len(elements) - 1):
            elements[index].link(elements[index + 1])

    def start(self):
        obplayer.Log.log("starting youtube streamer", 'debug')
        self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self):
        obplayer.Log.log("stopping youtube streamer", 'debug')
        self.pipeline.set_state(Gst.State.NULL)

    def quit(self):
        self.pipeline.set_state(Gst.State.NULL)

    def wait_state(self, target_state):
        self.pipeline.set_state(target_state)
        (statechange, state, pending) = self.pipeline.get_state(timeout=5 * Gst.SECOND)
        if statechange != Gst.StateChangeReturn.SUCCESS:
            obplayer.Log.log("gstreamer failed waiting for state change to " + str(pending), 'error')
            #raise Exception("Failed waiting for state change")
            return False
        return True

    def detect_silence(self, bus, message, *args):
        peak = message.get_structure().get_value('peak')
        if peak[0] < -28:
            if not self.is_dropping:
                self.is_dropping = True
                self.selector.set_property('drop', True)
                print("now dropping buffers")
        else:
            if self.is_dropping:
                self.is_dropping = False
                self.selector.set_property('drop', False)
                print("now outputting buffers")
        return True



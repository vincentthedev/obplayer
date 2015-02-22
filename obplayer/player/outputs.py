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
import sys
import time
import thread
import threading
import traceback

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst, GstVideo

Overlay = None

#############################
#
# Output Classes
#
#############################

class ObOutputBin (Gst.Bin):
    def build_pipeline(self, elements):
	for element in elements:
	    obplayer.Log.log("adding element to bin: " + element.get_name(), 'debug')
	    self.add(element)
	for index in range(0, len(elements) - 1):
	    elements[index].link(elements[index + 1])


class ObAudioSinkBin (ObOutputBin):
    __gstmetadata__ = ( "OpenBroadcaster Audio Sink Bin", "Sink", "Custom audio sink for OpenBroadcaster", "Sari McFarland <sari@pikalabs.com>" )

    def __init__(self):
	Gst.Bin.__init__(self)

	self.elements = [ ]

	# create filter elements
	level = Gst.ElementFactory.make("level", "level")
        level.set_property('interval', int(0.5 * Gst.SECOND))
	self.elements.append(level)

	## create audio sink element
        audio_output = obplayer.Config.setting('audio_out_mode')
        if audio_output == 'alsa':
            self.audiosink = Gst.ElementFactory.make('alsasink', 'audiosink')
            alsa_device = obplayer.Config.setting('audio_out_alsa_device')
            if alsa_device != '':
                self.audiosink.set_property('device', alsa_device)

        elif audio_output == 'esd':
            self.audiosink = Gst.ElementFactory.make('esdsink', 'audiosink')

        elif audio_output == 'jack':
            self.audiosink = Gst.ElementFactory.make('jackaudiosink', 'audiosink')
            self.audiosink.set_property('connect', 0)  # don't autoconnect ports.
	    name = obplayer.Config.setting('audio_out_jack_name')
            self.audiosink.set_property('client-name', name if name else 'obplayer')

        elif audio_output == 'oss':
            self.audiosink = Gst.ElementFactory.make('osssink', 'audiosink')

        elif audio_output == 'pulse':
            self.audiosink = Gst.ElementFactory.make('pulsesink', 'audiosink')

        elif audio_output == 'test':
            self.audiosink = Gst.ElementFactory.make('fakesink', 'audiosink')

        else:
            self.audiosink = Gst.ElementFactory.make('autoaudiosink', 'audiosink')

	self.elements.append(self.audiosink)

	self.build_pipeline(self.elements)

	self.sinkpad = Gst.GhostPad.new('sink', self.elements[0].get_static_pad('sink'))
	self.add_pad(self.sinkpad)


class ObVideoSinkBin (ObOutputBin):
    __gstmetadata__ = ( "OpenBroadcaster Video Sink Bin", "Sink", "Custom video sink for OpenBroadcaster", "Sari McFarland <sari@pikalabs.com>" )

    def __init__(self):
	Gst.Bin.__init__(self)

	self.video_width = obplayer.Config.setting('video_out_width')
	self.video_height = obplayer.Config.setting('video_out_height')

	self.elements = [ ]

	## create basic filter elements
	self.elements.append(Gst.ElementFactory.make("queue", "pre_queue"))
	self.elements.append(Gst.ElementFactory.make("videoscale", "pre_scale"))
	#self.elements[-1].set_property('add-borders', True)
	self.elements.append(Gst.ElementFactory.make("videoconvert", "pre_convert"))
	self.elements.append(Gst.ElementFactory.make("videorate", "pre_rate"))

	"""
	## create caps filter element to set the output video parameters
	box = Gst.ElementFactory.make('capsfilter', "capsfilter2")
	box.set_property('caps', Gst.Caps.from_string("video/x-raw,width=" + str(self.video_width - 100) + ",height=" + str(self.video_height - 100)))
	self.elements.append(box)
	"""

	#self.videobox = Gst.ElementFactory.make('videobox', "videobox")
	#self.videobox.set_property("top", -50)
	#self.videobox.set_property("bottom", -50)
	#self.videobox.set_property("left", -50)
	#self.videobox.set_property("right", -50)
	#self.videobox.set_property("autocrop", True)
	#self.elements.append(self.videobox)

	#self.crop = Gst.ElementFactory.make('aspectratiocrop', "effect")
	#ratio = GObject.Value(Gst.Fraction)
	#Gst.value_set_fraction(ratio, 4, 3)
	#self.crop.set_property('aspect-ratio', ratio)
	#self.elements.append(self.crop)

	#self.effect = Gst.ElementFactory.make('glfilterglass', "effect")
	#self.elements.append(self.effect)

	"""
	## create caps filter element to set the output video parameters
	caps_filter = Gst.ElementFactory.make('capsfilter', "capsfilter1")
	caps_filter.set_property('caps', Gst.Caps.from_string("video/x-raw,width=" + str(self.video_width) + ",height=" + str(self.video_height)))
	#caps_filter.set_property('caps', Gst.Caps.from_string("video/x-raw,width=" + str(1280) + ",height=" + str(300)))
	self.elements.append(caps_filter)

	self.mixer = Gst.ElementFactory.make("videomixer", "mixer")
	self.mixer.set_property('background', 3)
	self.elements.append(self.mixer)

	self.elements.append(Gst.ElementFactory.make("queue2", "queue"))
	self.elements.append(Gst.ElementFactory.make("videoscale", "scale"))
	#self.elements[-1].set_property('add-borders', True)
	self.elements.append(Gst.ElementFactory.make("videoconvert", "convert"))
	self.elements.append(Gst.ElementFactory.make("videorate", "rate"))
	"""

	## create overlay elements (if enabled)
        if obplayer.Config.setting('overlay_enable'):
	    self.elements.append(ObVideoOverlayBin())

	## create caps filter element to set the output video parameters
	caps_filter = Gst.ElementFactory.make('capsfilter', "capsfilter")
	caps_filter.set_property('caps', Gst.Caps.from_string("video/x-raw,width=" + str(self.video_width) + ",height=" + str(self.video_height)))
	#caps_filter.set_property('caps', Gst.Caps.from_string("video/x-raw,width=" + str(1280) + ",height=" + str(300)))
	self.elements.append(caps_filter)

	## create video sink element
	video_out_mode = obplayer.Config.setting('video_out_mode')
	if video_out_mode == 'x11':
	    self.videosink = Gst.ElementFactory.make("ximagesink", "videosink")

	elif video_out_mode == 'xvideo':
	    self.videosink = Gst.ElementFactory.make("xvimagesink", "videosink")

	elif video_out_mode == 'opengl':
	    self.videosink = Gst.ElementFactory.make("glimagesink", "videosink")

	elif video_out_mode == 'wayland':
	    self.videosink = Gst.ElementFactory.make("waylandsink", "videosink")

	elif video_out_mode == 'ascii':
	    self.videosink = Gst.ElementFactory.make("cacasink", "videosink")

	else:
	    self.videosink = Gst.ElementFactory.make("autovideosink", "videosink")

	self.elements.append(self.videosink)

	self.build_pipeline(self.elements)


	"""
	self.videotestsrc = Gst.ElementFactory.make("videotestsrc", "testsrc")
	self.videotestsrc.set_property('pattern', 5)
	self.add(self.videotestsrc)

	self.caps_filter = Gst.ElementFactory.make('capsfilter', "canvas-capsfilter")
	self.caps_filter.set_property('caps', Gst.Caps.from_string("video/x-raw,width=" + str(self.video_width) + ",height=" + str(self.video_height)))
	self.add(self.caps_filter)

	self.alpha = Gst.ElementFactory.make("alpha", "alpha")
	self.alpha.set_property('method', 1)
	self.add(self.alpha)

	self.overlay = ObVideoOverlayBin()
	self.add(self.overlay)

	self.queue = Gst.ElementFactory.make("queue", "queuetoo")
	self.add(self.queue)

	self.videotestsrc.link(self.caps_filter)
	self.caps_filter.link(self.alpha)
	self.alpha.link(self.overlay)
	self.overlay.link(self.queue)
	self.queue.link(self.mixer)
	"""


	self.sinkpad = Gst.GhostPad.new('sink', self.elements[0].get_static_pad('sink'))
	self.add_pad(self.sinkpad)


class ObVideoOverlayBin (ObOutputBin):
    __gstmetadata__ = ( "OpenBroadcaster Video Overlay Bin", "Chain", "Custom video overlay for OpenBroadcaster", "Sari McFarland <sari@pikalabs.com>" )

    def __init__(self):
	Gst.Bin.__init__(self)
	from obplayer.player.overlay import ObOverlay
	self.overlay = ObOverlay()
	global Overlay
	Overlay = self.overlay
	#self.overlay.set_message("My cat has cutenesses coming out of her body.  It's really spectacular and your head will explode when you see it.")

	self.elements = [ ]

	## create basic filter elements
	#self.elements.append(Gst.ElementFactory.make("queue", "pre_queue"))
	#self.elements.append(Gst.ElementFactory.make("videoscale", "pre_scale"))
	#self.elements.append(Gst.ElementFactory.make("videoconvert", "pre_convert"))

	"""
	self.videobox = Gst.ElementFactory.make('videobox', "videobox")
	self.videobox.set_property("top", -50)
	self.videobox.set_property("bottom", -50)
	self.videobox.set_property("left", -50)
	self.videobox.set_property("right", -50)
	self.elements.append(self.videobox)
	"""

	## create overlay elements (if enabled)
	self.cairooverlay = Gst.ElementFactory.make('cairooverlay', "overlay")
	self.cairooverlay.connect("draw", self.overlay_draw)
	self.cairooverlay.connect("caps-changed", self.overlay_caps_changed)
	self.elements.append(self.cairooverlay)

	self.elements.append(Gst.ElementFactory.make("queue", "post_queue"))
	self.elements.append(Gst.ElementFactory.make("videoscale", "post_scale"))
	self.elements.append(Gst.ElementFactory.make("videoconvert", "post_convert"))
	self.elements.append(Gst.ElementFactory.make("videorate", "post_rate"))

	"""
	# RSVG Overlay Test
	self.svgoverlay = Gst.ElementFactory.make("rsvgoverlay", "rsvgoverlay")
	self.add(self.svgoverlay)

	#self.svgoverlay.set_property('fit-to-frame', True)
	#self.svgoverlay.set_property('width', 1920)
	#self.svgoverlay.set_property('height', 1080)
	#self.svgoverlay.set_property('data', '<svg><text x="0" y="3" fill="blue">Hello World</text></svg>')
	self.svgoverlay.set_property('data', '<svg><circle cx="100" cy="100" r="50" fill="blue" /><text x="1" y="1" fill="red">Hello World</text></svg>')
	#self.svgoverlay.set_property('location', '/home/trans/Downloads/strawberry.svg')
	"""

	self.build_pipeline(self.elements)

	self.sinkpad = Gst.GhostPad.new('sink', self.elements[0].get_static_pad('sink'))
	self.add_pad(self.sinkpad)
	self.srcpad = Gst.GhostPad.new('src', self.elements[-1].get_static_pad('src'))
	self.add_pad(self.srcpad)

    def overlay_caps_changed(self, overlay, caps):
	self.overlay_caps = GstVideo.VideoInfo()
	self.overlay_caps.from_caps(caps)
	#print str(self.overlay_caps.width) + " x " + str(self.overlay_caps.height)

    def overlay_draw(self, overlay, context, arg1, arg2):
	self.overlay.draw_overlay(context, self.overlay_caps.width, self.overlay_caps.height)



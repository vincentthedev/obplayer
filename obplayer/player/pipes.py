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
from gi.repository import GObject, Gst, GstVideo, GstController


class ObPipeline (object):
    def __init__(self, name):
	self.mode = set()
	self.name = name
	self.playing = False

    def start(self):
	self.playing = True

    def stop(self):
	self.playing = False

    def quit(self):
	self.playing = False

    def is_playing(self):
	return self.playing

    def patch(self, mode):
	for output in mode.split('/'):
	    self.mode.add(output)

    def unpatch(self, mode):
	for output in mode.split('/'):
	    self.mode.discard(output)

    def set_request(self, req):
	pass


class ObGstPipeline (ObPipeline):
    def __init__(self, name):
	ObPipeline.__init__(self, name)

    def build_pipeline(self, elements):
	for element in elements:
	    obplayer.Log.log("adding element to bin: " + element.get_name(), 'debug')
	    self.pipeline.add(element)
	for index in range(0, len(elements) - 1):
	    elements[index].link(elements[index + 1])

    """
    def build_pipeline(self, elements):
	# TODO this totally doesn't work yet
	for element in elements:
	    if type(element) != type(list):
		obplayer.Log.log("adding element to bin: " + element.get_name(), 'debug')
		self.pipeline.add(element)
	for index in range(0, len(elements) - 1):
	    if type(element) == type(list):
		segment = self.build_pipeline(element)
		# TODO then add it to the pipeline
	    else:
		elements[index].link(elements[index + 1])
	return
    """


    """

	self.elements = [ ]
	# TODO actually this doesn't get linked up until later, so we don't include it??
	#self.elements.append(Gst.ElementFactory.make('uridecoder', 'uridecoder'))

	self.branch1 = [ ]
	self.branch1.append(Gst.ElementFactory.make('imagefreeze', 'imagefreeze1'))
	self.branch1.append(Gst.ElementFactory.make('alpha', 'alpha1'))

	self.branch2 = [ ]
	self.branch2.append(Gst.ElementFactory.make('imagefreeze', 'imagefreeze2'))
	self.branch2.append(Gst.ElementFactory.make('alpha', 'alpha2'))

	self.elements.append([ self.branch1, self.branch2 ])
	self.elements.append(Gst.ElementFactory.make('videomixer', 'videomixer'))
    """

    def register_signals(self):
        self.bus = self.pipeline.get_bus()
	self.bus.add_signal_watch()
	self.bus.enable_sync_message_emission()
	self.bus.connect("sync-message::element", self.sync_handler)
	self.bus.connect("message", self.message_handler)

    def wait_state(self, target_state):
	self.pipeline.set_state(target_state)
        (statechange, state, pending) = self.pipeline.get_state(timeout=5 * Gst.SECOND)
        if statechange != Gst.StateChangeReturn.SUCCESS:
	    obplayer.Log.log("gstreamer failed waiting for state change to " + str(pending), 'error')
	    #raise Exception("Failed waiting for state change")
	    return False
	return True

    def start(self):
	#print self.name + ": starting"
	self.wait_state(Gst.State.PLAYING)

    def stop(self):
	#print self.name + ": stopping"
	self.wait_state(Gst.State.READY)

    def quit(self):
	self.wait_state(Gst.State.NULL)

    def is_playing(self):
	(change, state, pending) = self.pipeline.get_state(0)
	if state == Gst.State.PLAYING:
	    return True
	return False

    # sync handler (assigns video sink to drawing area)
    def sync_handler(self, bus, message):
        if message.get_structure() is None:
            return Gst.BusSyncReply.PASS
        if message.get_structure().get_name() == 'prepare-window-handle':
	    message.src.set_window_handle(obplayer.Gui.gst_xid)
        return Gst.BusSyncReply.PASS

    # message handler (handles gstreamer messages posted to the bus)
    def message_handler(self, bus, message):
	if message.type == Gst.MessageType.STATE_CHANGED:
	    oldstate, newstate, pending = message.parse_state_changed()
	    """
	    if message.src == self.pipeline:
		obplayer.Log.log("State Changed to " + str(newstate), "player")
		if newstate == Gst.State.PLAYING:
		    self.is_playing.set()
		else:
		    self.is_playing.clear()
	    """

	elif message.type == Gst.MessageType.ERROR:
	    err, debug = message.parse_error()
	    obplayer.Log.log("gstreamer error: %s, %s, %s" % (err, debug, err.code), 'error')
	    #self.pipeline.set_state(Gst.State.READY)
	    self.player.request_update.set()

	elif message.type == Gst.MessageType.WARNING:
	    err, debug = message.parse_warning()
	    obplayer.Log.log("gstreamer warning: %s, %s, %s" % (err, debug, err.code), 'warning')

	elif message.type == Gst.MessageType.INFO:
	    err, debug = message.parse_info()
	    obplayer.Log.log("gstreamer info: %s, %s, %s" % (err, debug, err.code), 'info')

	elif message.type == Gst.MessageType.BUFFERING:
	    print "Buffering Issue"
	    #percent = message.parse_buffering()
	    #if percent < 100:
	    #    self.pipeline.set_state(Gst.State.PAUSED)
	    #else:
	    #    self.pipeline.set_state(Gst.State.PLAYING)

	elif message.type == Gst.MessageType.EOS:
	    obplayer.Log.log("player received end of stream signal", 'debug')
	    self.player.request_update.set()

	elif message.type == Gst.MessageType.ELEMENT:
	    struct = message.get_structure()
	    #self.player.audio_levels = [ pow(10, rms / 20) for rms in rms_values ]
	    self.player.audio_levels = struct.get_value('rms')

    """
    def signal_about_to_finish(self, message):
	print "About to finish"
	with self.lock:
	    for ctrl in self.controllers:
		# TODO this function needs to 
		req = ctrl.get_next_request()
		# you can't just play the request... you need a function that just sets the uri, does the playlog, and all the log statements
    """



class ObBreakPipeline (ObPipeline):
    output_caps = [ 'audio' ]

    def __init__(self, name, player):
	ObPipeline.__init__(self, name)
	self.player = player

    def patch(self, mode):
	# we don't have to do anything because the output patched to us will just remain disconnected
	ObPipeline.patch(self, mode)

    def unpatch(self, mode):
	# we don't have to do anything because the output patched to us will just remain disconnected
	ObPipeline.unpatch(self, mode)


class ObPlaybinPipeline (ObGstPipeline):
    output_caps = [ 'audio', 'visual' ]

    def __init__(self, name, player, audiovis=False):
	ObGstPipeline.__init__(self, name)
	self.player = player
	self.start_time = 0
        self.pipeline = Gst.ElementFactory.make('playbin')
	# TODO this is false for testing
        #self.pipeline.set_property('force-aspect-ratio', False)
        self.pipeline.set_property('force-aspect-ratio', True)

        if audiovis is True:
            self.audiovis = Gst.ElementFactory.make('libvisual_jess')
            self.pipeline.set_property('flags', self.pipeline.get_property('flags') | 0x00000008)
            self.pipeline.set_property('vis-plugin', self.audiovis)

	self.fakesinks = { }
	for output in self.player.outputs.keys() + [ 'audio', 'visual' ]:
	    self.fakesinks[output] = Gst.ElementFactory.make('fakesink')

	self.pipeline.set_property('audio-sink', self.fakesinks['audio'])
	self.pipeline.set_property('video-sink', self.fakesinks['visual'])

	self.register_signals()
	#self.pipeline.connect("about-to-finish", self.about_to_finish_handler)

    def patch(self, mode):
	obplayer.Log.log(self.name + ": patching " + mode, 'debug')

	(change, state, pending) = self.pipeline.get_state(0)
	self.wait_state(Gst.State.NULL)

	for output in mode.split('/'):
	    if output not in self.mode:
		#print self.name + " -- Connecting " + output
		self.pipeline.set_property('audio-sink' if output == 'audio' else 'video-sink', self.player.outputs[output])
		if output == 'visual':
		    obplayer.Gui.change_media_mode('video')
		self.mode.add(output)

	if state == Gst.State.PLAYING:
	    self.seek_pause()
	    self.wait_state(Gst.State.PLAYING)

    def unpatch(self, mode):
	obplayer.Log.log(self.name + ": unpatching " + mode, 'debug')

	(change, state, pending) = self.pipeline.get_state(0)
	self.wait_state(Gst.State.NULL)

	for output in mode.split('/'):
	    if output in self.mode:
		#print self.name + " -- Disconnecting " + output
		self.pipeline.set_property('audio-sink' if output == 'audio' else 'video-sink', self.fakesinks[output])
		self.mode.discard(output)

	if len(self.mode) > 0 and state == Gst.State.PLAYING:
	    self.seek_pause()
	    self.wait_state(Gst.State.PLAYING)

    def set_request(self, req):
	self.start_time = req['start_time']
	self.pipeline.set_property('uri', "file://" + req['file_location'] + '/' + req['filename'])
	self.seek_pause()

    def seek_pause(self):
	# Set pipeline to paused state
	self.wait_state(Gst.State.PAUSED)

	if obplayer.Config.setting('gst_init_callback'):
	    os.system(obplayer.Config.setting('gst_init_callback'))

	if self.start_time <= 0:
	    self.start_time = time.time()

	offset = time.time() - self.start_time
	if offset != 0:
	#if offset > 0.25:
	    if self.pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, offset * Gst.SECOND) == False:
		obplayer.Log.log('unable to seek on this track', 'error')
	    obplayer.Log.log('resuming track at ' + str(offset) + ' seconds.', 'player')


class ObTestPipeline (ObGstPipeline):
    output_caps = [ 'audio', 'visual' ]

    def __init__(self, name, player):
	ObGstPipeline.__init__(self, name)
	self.player = player

	self.pipeline = Gst.Pipeline()
	self.audiotestsrc = Gst.ElementFactory.make('audiotestsrc')
	self.pipeline.add(self.audiotestsrc)
	self.videotestsrc = Gst.ElementFactory.make('videotestsrc')
	self.pipeline.add(self.videotestsrc)
	self.audiosink = None
	self.videosink = None

	self.fakesinks = { }
	for output in self.player.outputs.keys() + [ 'audio', 'visual' ]:
	    self.fakesinks[output] = Gst.ElementFactory.make('fakesink')

	self.set_property('audio-sink', self.fakesinks['audio'])
	self.set_property('video-sink', self.fakesinks['visual'])

	self.audiotestsrc.set_property('volume', 0.2)
	self.register_signals()

    def set_property(self, property, value):
	if property == 'audio-sink':
	    if self.audiosink:
		self.pipeline.remove(self.audiosink)
	    self.audiosink = value
	    if self.audiosink:
		self.pipeline.add(self.audiosink)
		self.audiotestsrc.link(self.audiosink)
	elif property == 'video-sink':
	    if self.videosink:
		self.pipeline.remove(self.videosink)
	    self.videosink = value
	    if self.videosink:
		self.pipeline.add(self.videosink)
		self.videotestsrc.link(self.videosink)

    def patch(self, mode):
	self.wait_state(Gst.State.NULL)
	if 'audio' in mode:
	    self.set_property('audio-sink', self.player.outputs['audio'])
	if 'visual' in mode:
	    obplayer.Gui.change_media_mode('video')
	    self.set_property('video-sink', self.player.outputs['visual'])
	ObPipeline.patch(self, mode)
	self.wait_state(Gst.State.PLAYING)

    def unpatch(self, mode):
	self.wait_state(Gst.State.NULL)
	if 'audio' in mode:
	    self.set_property('audio-sink', self.fakesinks['audio'])
	if 'visual' in mode:
	    self.set_property('video-sink', self.fakesinks['visual'])
	ObPipeline.unpatch(self, mode)
	if len(self.mode) > 0:
	    self.wait_state(Gst.State.PLAYING)


class ObLineInPipeline (ObGstPipeline):
    output_caps = [ 'audio' ]

    def __init__(self, name, player):
	ObGstPipeline.__init__(self, name)
	self.player = player

	self.pipeline = Gst.Pipeline()

        audio_input = obplayer.Config.setting('audio_in_mode')
        if audio_input == 'alsa':
            self.audiosrc = Gst.ElementFactory.make('alsasrc', 'audiosrc')
            alsa_device = obplayer.Config.setting('audio_in_alsa_device')
            if alsa_device != '':
                self.audiosrc.set_property('device', alsa_device)

        elif audio_input == 'jack':
            self.audiosrc = Gst.ElementFactory.make('jackaudiosrc', 'audiosrc')
            self.audiosrc.set_property('connect', 0)  # don't autoconnect ports.
	    name = obplayer.Config.setting('audio_in_jack_name')
            self.audiosrc.set_property('client-name', name if name else 'obplayer')

        elif audio_input == 'oss':
            self.audiosrc = Gst.ElementFactory.make('osssrc', 'audiosrc')

        elif audio_input == 'pulse':
            self.audiosrc = Gst.ElementFactory.make('pulsesrc', 'audiosrc')

        elif audio_input == 'test':
            self.audiosrc = Gst.ElementFactory.make('fakesrc', 'audiosrc')

        else:
            self.audiosrc = Gst.ElementFactory.make('autoaudiosrc', 'audiosrc')

	self.pipeline.add(self.audiosrc)

	self.audioconvert = Gst.ElementFactory.make('audioconvert')
	self.pipeline.add(self.audioconvert)
	self.audiosrc.link(self.audioconvert)

	self.audiosink = None
	self.fakesink = Gst.ElementFactory.make('fakesink')
	self.set_property('audio-src', self.fakesink)

	self.register_signals()

    def set_property(self, property, value):
	if property == 'audio-sink':
	    if self.audiosink:
		self.pipeline.remove(self.audiosink)
	    self.audiosink = value
	    if self.audiosink:
		self.pipeline.add(self.audiosink)
		self.audioconvert.link(self.audiosink)

    def patch(self, mode):
	self.wait_state(Gst.State.NULL)
	if 'audio' in mode:
	    self.set_property('audio-sink', self.player.outputs['audio'])
	ObPipeline.patch(self, mode)
	self.wait_state(Gst.State.PLAYING)

    def unpatch(self, mode):
	self.wait_state(Gst.State.NULL)
	if 'audio' in mode:
	    self.set_property('audio-sink', self.fakesinks['audio'])
	ObPipeline.unpatch(self, mode)
	if len(self.mode) > 0:
	    self.wait_state(Gst.State.PLAYING)


"""
class ObImagePipeline (ObPipeline):
    output_caps = [ 'visual' ]

    def __init__(self, name, player):
	ObPipeline.__init__(self, name)
	self.player = player

    def patch(self, mode):
	if 'visual' in mode:
	    obplayer.Gui.change_media_mode('image')
	ObPipeline.patch(self, mode)

    def unpatch(self, mode):
	ObPipeline.unpatch(self, mode)

    #def stop(self):
	# TODO make the canvas blank
	#pass

    def set_media_file(self, filename, start_time):
	obplayer.Gui.drawing_area_image_update(filename)
"""


class ObImagePipeline (ObGstPipeline):
    output_caps = [ 'visual' ]

    def __init__(self, name, player, audiovis=False):
	ObGstPipeline.__init__(self, name)
	self.player = player
	self.request = None
	self.videosink = None

        self.pipeline = Gst.Pipeline()

	#self.imagebin = Gst.parse_launch('uridecodebin uri="file:///home/trans/Downloads/kitty.jpg" ! imagefreeze ! videoconvert ! videoscale ! video/x-raw, height=1920, width=1080 ! autovideosink')

	self.decodebin = Gst.ElementFactory.make('uridecodebin', 'uridecodebin')
	self.pipeline.add(self.decodebin)
	self.decodebin.connect("pad-added", self.on_decoder_pad_added)

	self.elements = [ ]
	self.elements.append(Gst.ElementFactory.make('imagefreeze', 'imagefreeze'))

	#self.videobalance = Gst.ElementFactory.make('videobalance', 'videobalance')
	#self.videobalance.set_property('videobalance', 0.0)
	#self.elements.append(self.videobalance)

	self.control_source = GstController.InterpolationControlSource.new()
	self.control_source.props.mode = GstController.InterpolationMode.LINEAR

	#binding = GstController.DirectControlBinding.new(self.videobalance, 'contrast', self.control_source)
	#self.videobalance.add_control_binding(binding)

	self.elements.append(Gst.ElementFactory.make('alpha', 'alpha'))
	#self.elements[-1].set_property('method', 1)
	binding = GstController.DirectControlBinding.new(self.elements[-1], 'alpha', self.control_source)
	self.elements[-1].add_control_binding(binding)

	self.elements.append(Gst.ElementFactory.make('videomixer', 'videomixer'))
	self.elements[-1].set_property('background', 1)

	self.build_pipeline(self.elements)

	self.register_signals()

    def on_decoder_pad_added(self, element, pad):
	#caps = pad.get_current_caps()
	#if caps.to_string().startswith('video'):
	    #pad.link(self.elements[0].get_static_pad('sink'))
	sinkpad = self.elements[0].get_compatible_pad(pad, pad.get_current_caps())
        pad.link(sinkpad)

    def patch(self, mode):
	obplayer.Log.log(self.name + ": patching " + mode, 'debug')

	(change, state, pending) = self.pipeline.get_state(0)
	self.wait_state(Gst.State.NULL)

	for output in mode.split('/'):
	    if output not in self.mode:
		#print self.name + " -- Connecting " + output
		if self.videosink:
		    self.pipeline.remove(self.videosink)
		self.videosink = self.player.outputs[output]
		if self.videosink:
		    self.pipeline.add(self.videosink)
		    self.elements[-1].link(self.videosink)

		if output == 'visual':
		    obplayer.Gui.change_media_mode('video')
		self.mode.add(output)

	if state == Gst.State.PLAYING:
	    self.wait_state(Gst.State.PLAYING)

    def unpatch(self, mode):
	obplayer.Log.log(self.name + ": unpatching " + mode, 'debug')

	(change, state, pending) = self.pipeline.get_state(0)
	self.wait_state(Gst.State.NULL)

	for output in mode.split('/'):
	    if output in self.mode:
		#print self.name + " -- Disconnecting " + output
		if self.videosink:
		    self.pipeline.remove(self.videosink)
		    self.videosink = None
		self.mode.discard(output)

	if len(self.mode) > 0 and state == Gst.State.PLAYING:
	    self.wait_state(Gst.State.PLAYING)

    def set_request(self, req):
	self.request = req
	self.decodebin.set_property('uri', "file://" + req['file_location'] + '/' + req['filename'])

	end_time = req['end_time'] - time.time()
	self.control_source.unset_all()
	self.control_source.set(0, 0.0)
	self.control_source.set(1 * Gst.SECOND, 1.0)
	self.control_source.set((end_time - 1) * Gst.SECOND, 1.0)
	self.control_source.set(end_time * Gst.SECOND, 0.0)











"""
class ObDecodeBinPipeline (ObGstPipeline):
    output_caps = [ 'audio', 'visual' ]

    def __init__(self, name, player, audiovis=False):
	ObGstPipeline.__init__(self, name)
	self.player = player
	self.start_time = 0
	self.audiosink = None
	self.videosink = None

        self.pipeline = Gst.Pipeline()

        self.decodebin = Gst.ElementFactory.make('uridecodebin')
	self.pipeline.add(self.decodebin)
	self.decodebin.connect("pad-added", self.on_decoder_pad_added)

        #if audiovis is True:
        #    self.audiovis = Gst.ElementFactory.make('libvisual_jess')
        #    self.pipeline.set_property('flags', self.pipeline.get_property('flags') | 0x00000008)
        #    self.pipeline.set_property('vis-plugin', self.audiovis)

	self.fakesinks = { }
	for output in self.player.outputs.keys() + [ 'audio', 'visual' ]:
	    self.fakesinks[output] = Gst.ElementFactory.make('fakesink')

	self.set_property('audio-sink', self.fakesinks['audio'])
	self.set_property('video-sink', self.fakesinks['visual'])

	self.register_signals()
	#self.pipeline.connect("about-to-finish", self.about_to_finish_handler)

    def on_decoder_pad_added(self, element, pad):
	caps = pad.get_current_caps()

	#print caps.to_string()
	#print self.audiosink.get_static_pad('sink')
	#print self.audiosink.get_request_pad('sink')

	if caps.to_string().startswith('audio'):
	    #self.pipeline.add(self.audiosink)
	    pad.link(self.audiosink.get_static_pad('sink'))
	else:
	    #self.pipeline.add(self.videosink)
	    pad.link(self.videosink.get_static_pad('sink'))

    def set_property(self, property, value):
	if property == 'audio-sink':
	    if self.audiosink:
		self.pipeline.remove(self.audiosink)
	    self.audiosink = value
	    if self.audiosink:
		self.pipeline.add(self.audiosink)
		#self.decodebin.link(self.audiosink)
	elif property == 'video-sink':
	    if self.videosink:
		self.pipeline.remove(self.videosink)
	    self.videosink = value
	    if self.videosink:
		self.pipeline.add(self.videosink)
		#self.decodebin.link(self.videosink)

    def patch(self, mode):
	obplayer.Log.log(self.name + ": patching " + mode, 'debug')

	(change, state, pending) = self.pipeline.get_state(0)
	self.wait_state(Gst.State.NULL)

	for output in mode.split('/'):
	    if output not in self.mode:
		#print self.name + " -- Connecting " + output
		self.set_property('audio-sink' if output == 'audio' else 'video-sink', self.player.outputs[output])
		if output == 'visual':
		    obplayer.Gui.change_media_mode('video')
		self.mode.add(output)

	if state == Gst.State.PLAYING:
	    self.seek_pause()
	    self.wait_state(Gst.State.PLAYING)

    def unpatch(self, mode):
	obplayer.Log.log(self.name + ": unpatching " + mode, 'debug')

	(change, state, pending) = self.pipeline.get_state(0)
	self.wait_state(Gst.State.NULL)

	for output in mode.split('/'):
	    if output in self.mode:
		#print self.name + " -- Disconnecting " + output
		self.set_property('audio-sink' if output == 'audio' else 'video-sink', self.fakesinks[output])
		self.mode.discard(output)

	if len(self.mode) > 0 and state == Gst.State.PLAYING:
	    self.seek_pause()
	    self.wait_state(Gst.State.PLAYING)

    def set_media_file(self, filename, start_time):
	self.start_time = start_time
	self.decodebin.set_property('uri', "file://" + filename)
	self.seek_pause()

    def seek_pause(self):
	# Set pipeline to paused state
	self.wait_state(Gst.State.PAUSED)

	if obplayer.Config.setting('gst_init_callback'):
	    os.system(obplayer.Config.setting('gst_init_callback'))

	if self.start_time <= 0:
	    self.start_time = time.time()

	offset = time.time() - self.start_time
	if offset != 0:
	#if offset > 0.25:
	    if self.pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, offset * Gst.SECOND) == False:
		obplayer.Log.log('unable to seek on this track', 'error')
	    obplayer.Log.log('resuming track at ' + str(offset) + ' seconds.', 'player')
"""



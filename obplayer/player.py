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

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst, GstVideo #, cairo, Gdk, GdkPixbuf

Gst.init(None)

class ObPlayer (object):
    def __init__(self):
	self.controllers = [ ]
	self.request_update = threading.Event()
	self.lock = thread.allocate_lock()
	self.thread = None

    def start_player(self):
	self.thread = obplayer.ObThread('ObPlayerThread', target=self.run)
	self.thread.start()

    def player_init(self):
	self.outputs = { }
	self.outputs['audio'] = ObAudioSinkBin()
	if not obplayer.Config.headless:
            self.outputs['visual'] = ObVideoSinkBin()
	else:
            self.outputs['visual'] = Gst.ElementFactory.make('fakesink')

	self.patches = { }
	for output in self.outputs.keys():
	    self.patches[output] = None

	self.requests = { }
	for request in self.outputs.keys():
	    self.requests[request] = None

	self.pipes = { }
	self.pipes['audio'] = ObPlaybinPipeline('audio-playbin', self, obplayer.Config.setting('audiovis'))
	self.pipes['video'] = ObPlaybinPipeline('video-playbin', self)
	self.pipes['testsignal'] = ObTestPipeline('test-signal', self)
	self.pipes['image'] = ObImagePipeline('image-pipeline', self)
	self.pipes['break'] = ObBreakPipeline('audio-break', self)

	self.testctrl = self.create_controller('testsignal', 1, allow_requeue=False)
	def testsignal_request(self, present_time):
	    self.add_request(media_type='break', duration=5)
	    self.add_request(media_type='testsignal', duration=5000)
	self.testctrl.set_request_callback(testsignal_request)

    def player_quit(self):
	for pipe_name in self.pipes.keys():
	    self.pipes[pipe_name].quit()

    def create_controller(self, name, priority, default_play_mode=None, allow_requeue=True):
	ctrl = ObPlayerController(self, name, priority, default_play_mode, allow_requeue)
	for i in range(len(self.controllers)):
	    if self.controllers[i].priority < ctrl.priority:
		self.controllers.insert(i, ctrl)
		return ctrl
	self.controllers.append(ctrl)
	return ctrl

    def run(self):
	self.player_init()
	self.request_update.set()
	while not self.thread.stopflag.wait(1):
	    present_time = time.time()

	    # Stop any requests that have reached their end time and restore any outputs that may have been usurped by the now stopped request
	    restore = False
	    for output in self.requests.keys():
		if self.requests[output] is not None and present_time > self.requests[output]['end_time']:
		    self.stop_request(output)
		    self.request_update.set()
		    restore = True
	    if restore:
		print str(time.time()) + ": Attempting to restore outputs"
		self.restore_outputs()

	    # check for requests already in the queue that need to start now
	    with self.lock:
		lowest_priority = 100
		for output in self.requests.keys():
		    if self.requests[output] is not None and self.requests[output]['priority'] < lowest_priority:
			lowest_priority = self.requests[output]['priority']
		for ctrl in self.controllers:
		    # TODO somehow only set the bit if the request waiting is equal to or higher than the... lowest priority?
		    if ctrl.priority <= lowest_priority:
			break
		    if ctrl.check_for_start(present_time):
			print str(time.time()) + ": Found a future request that needs to start now..."
			self.request_update.set()


	    #if self.request_update.is_set() or not self.is_playing.is_set() or self.astream is None or self.vstream is None:
	    if self.request_update.is_set(): #or (self.astream is None and self.vstream is None):
		print str(time.time()) + ": Current State (" + str(time.time()) + "): " + repr(self.request_update.is_set()) + " | " + (self.requests['audio']['filename'] if self.requests['audio'] is not None else "No astream") + " | " + (self.requests['visual']['filename'] if 'visual' in self.requests and self.requests['visual'] is not None else "No vstream")

		# get a list of output names sorted by the priority of the currently playing request
		priority_list = sorted([ (self.requests[output]['priority'] if self.requests[output] else 0, output) for output in self.requests.keys() ], key=lambda pair: pair[0], reverse=True)
		#print priority_list

		req = None
		while len(priority_list) > 0:
		    print str(time.time()) + ": Trying to fill in outputs: " + repr(priority_list)
		    output_list = [ pair[1] for pair in priority_list ]

		    # if we are playing a request that only allows overlaying with itself, then we only check that controller for requests, otherwise we check all controllers
		    if req is not None and req['play_mode'] == 'overlay_self':
			req = req['controller'].get_request(present_time, output_list, query=True)
		    else:
			req = self.get_request(present_time, priority_list[0][0], output_list, query=True)

		    if req:
			self.execute_request(req, output_limit=output_list)
		    else:
			req = self.requests[priority_list[0][1]]

		    if req is not None:
			# if the current request is to be played exclusively, then exit the loop
			if req['play_mode'] == 'exclusive':
			    break

			# eliminate all outputs from the list that the currently playing request is using (they cannot be overidden by a lower priority request)
			class_list = req['media_class'].split('/')
			priority_list = [ pair for pair in priority_list if pair[1] not in class_list ]
		    else:
			break

		print str(time.time()) + ": Current State (" + str(time.time()) + "): " + repr(self.request_update.is_set()) + " | " + (self.requests['audio']['filename'] if self.requests['audio'] is not None else "No astream") + " | " + (self.requests['visual']['filename'] if 'visual' in self.requests and self.requests['visual'] is not None else "No vstream")

		# if the updated flag was set, then clear it
		if self.request_update.is_set():
		    self.request_update.clear()

	    # call the update functions
	    with self.lock:
		for ctrl in self.controllers:
		    if ctrl.next_update and present_time > ctrl.next_update:
			ctrl.next_update = 0
			ctrl.do_player_update(ctrl, present_time)

	self.player_quit()

    def get_request(self, present_time, priority, media_class, query=False):
	with self.lock:
	    for ctrl in self.controllers:
		if ctrl.priority < priority:
		    break
		req = ctrl.get_request(present_time, media_class, query=True)
		if req is not None:
		    return req
	return None

    def execute_request(self, req, output_limit=None):
	print str(time.time()) + ": Executing request: [" + req['media_type'] + "] " + req['filename']

	if req['play_mode'] == 'exclusive':
	    #stop_list = '/'.join(output_list)
	    for output in output_limit:
		self.stop_request(output, requeue=True)
	elif req['play_mode'] == 'overlay_all':
	    pass
	    #stop_list = '/'.join([ output for output in output_list if output in req['media_class'] ])
	    # NOTE this should be ok to not stop the outputs, because we'll unpatch those outputs later as necessary, and the repatch code will stop the pipe if it's not connected
	elif req['play_mode'] == 'overlay_self':
	    #stop_list = '/'.join([ output for output in output_list if self.requests[output] is not None and self.requests[output]['controller'] != req['controller'] ])
	    for output in output_limit:
		if self.requests[output] is not None and self.requests[output]['controller'] != req['controller'] and self.requests[output]['priority'] > req['priority']:
		    self.stop_request(output, requeue=True)


	"""
	# write entry into play log.
        playlog_notes = 'resuming at ' + str(offset) + 's' if offset == 0 else ''
        obplayer.PlaylogData.playlog_add(media['media_id'], media['artist'], media['title'], time.time(), context, emerg_id, playlog_notes)
	"""

	request_pipe = self.pipes[req['media_type']]

	# determine what outputs to play the request on (eg. audio can output the visualizer if nothing visual is otherwise being played)
	class_list = req['media_class'].split('/')
	patch_list = [ output for output in request_pipe.output_caps if self.requests[output] is None or output in class_list ]
	patch_list.sort()
	patch_class = '/'.join(patch_list)

	# NOTE this should never happen
	if patch_class == '':
	    print "Bloody Murder!!"
	    print repr(req)
	    print "Audio Request:"
	    print repr(self.requests['audio'])
	    print "Visual Request:"
	    print repr(self.requests['visual'])
	    print ""

	# change the patches as needed
	self.repatch_outputs(patch_class, req['media_type'])

	# set up and play the request
	if req['media_type'] in [ 'image', 'audio', 'video' ]:
	    media_filename = self.get_media_path(req)
	    print str(time.time()) + ": Media filename " + str(media_filename)
	    if media_filename is not None:
		request_pipe.set_media_file(media_filename, time.time() - req['start_time'])
	request_pipe.start()

	# record the currently playing requests in the requests table (only the minimum set)
	for output in req['media_class'].split('/'):
	    self.requests[output] = req

	# TODO make this look nicer, use a formatted string
        track_num = ' ' + str(req['order_num'] + 1) if req['order_num'] else '?'
        obplayer.Log.log('now playing track' + str(track_num) + ': ' + unicode(req['artist']).encode('ascii', 'replace') + ' - '
		    + unicode(req['title']).encode('ascii', 'replace') + ' (id: ' + str(req['media_id'])
		    + ' file: ' + unicode(req['filename']).encode('ascii', 'replace') + ')', 'player')

    def get_media_path(self, req):
        if req['file_location'][0] == '/':
            media_filename = req['file_location'] + '/' + req['filename']
        else:
	    # file location specified as 2-character directory code.
            media_filename = obplayer.Config.setting('remote_media') + '/' + req['file_location'][0] + '/' + req['file_location'][1] + '/' + req['filename']

	# see if the file exists.  if not, return false...
        if os.path.exists(media_filename) == False:
            obplayer.Log.log('ObPlayer: File ' + media_filename + ' does not exist. Skipping playback', 'error')
            return None
	return media_filename

    def stop_request(self, output, requeue=False):
	if self.requests[output] == None:
	    return

	req = self.requests[output]
	print "Stopping request: " + req['media_type'] + ": " + req['filename']
	request_pipe = self.pipes[req['media_type']]
	request_pipe.stop()

	# push the request back onto the queue. This assumes that this pipe is playing the same request
	if requeue is True:
	    req['controller'].requeue_request(req)

	for name in self.requests.keys():
	    if self.requests[name] == req:
		self.requests[name] = None

    def repatch_outputs(self, media_class, media_type):
	#print "Repatching " + media_class + " to pipe " + str(media_type)

	for output in self.requests.keys():
	    if self.requests[output] is not None and self.requests[output]['media_type'] == media_type:
		self.stop_request(output, requeue=True)

	output_list = media_class.split('/')
	for pipe in self.pipes.keys():
	    if pipe != media_type:
		unpatch_list = [ output for output in output_list if self.patches[output] == pipe ]
		if len(unpatch_list) > 0:
		    if len(unpatch_list) == len(self.pipes[pipe].mode):
			self.pipes[pipe].stop()
			# TODO requeue any request for which we stop the pipe
			print "*** We should be requeuing"
		    self.pipes[pipe].unpatch('/'.join(unpatch_list))

	if media_type is not None:
	    patch_list = [ output for output in output_list if self.patches[output] != media_type ]
	    if len(patch_list) > 0:
		self.pipes[media_type].patch('/'.join(patch_list))
	for output in output_list:
	    self.patches[output] = media_type
		
    def restore_outputs(self):
	for output in self.requests.keys():
	    if self.requests[output] is not None:
		class_list = self.requests[output]['media_class'].split('/')
		patch_list = [ output for output in class_list if self.requests[output] is None ]
		if len(patch_list) > 0:
		    patch_list.sort()
		    self.repatch_outputs('/'.join(patch_list), self.patches[output])
		    for class_name in patch_list:
			self.requests[class_name] = self.requests[output]


    """
    # get the status (state) of the pipline (debug)
    def status(self):
	if not self.pipeline:
	    return True
        if self.pipeline.get_state()[1] == Gst.State.PLAYING:
            return False
        else:
            return str(self.pipeline.get_state())
    """

    def get_controller_requests(self, ctrl):
	return [ output for output in self.requests.keys() if self.requests[output] != None and self.requests[output]['controller'] == ctrl ]

    def controller_request_is_playing(self, ctrl):
	for output in self.get_controller_requests(ctrl):
	    request_pipe = self.pipes[self.requests[output]['media_type']]
	    if request_pipe.is_playing():
		return True
	return False

    def stop_controller_requests(self, ctrl):
	for output in self.requests.keys():
	    if self.requests[output] != None and self.requests[output]['controller'] == ctrl:
		self.stop_request(output)


#############################
#
# Player Controller
#
#############################

class ObPlayerController (object):
    def __init__(self, player, name, priority, default_play_mode=None, allow_requeue=True):
	if default_play_mode is None:
	    default_play_mode = 'exclusive'
	self.player = player
	self.name = name
	self.priority = priority
	self.default_play_mode = default_play_mode
	self.allow_requeue = allow_requeue

	self.lock = thread.allocate_lock()
	self.queue = [ ]
	self.next_update = 0

	# TODO you could have a list of failed requests, where the request is automatically added (auto limit to say 5 entries)
	self.failed = [ ]
	# TODO this is possible too, but i think calling the player is better, even though it's a bit messy.  It's less messy than this way
	#self.playing = [ ]

    # media_type can be:	audio, video, image, audioin, break, testsignal
    # play_mode can be:		exclusive, overlay_self, overlay_all
    def add_request(self, media_type, start_time=None, end_time=None, file_location='', filename='', duration=0, offset=0, media_id=0, order_num=-1, artist='unknown', title='unknown', play_mode=None):
	if start_time is None:
	    start_time = self.get_requests_endtime()
	if end_time is not None:
	    duration = end_time - start_time
	else:
	    end_time = start_time + duration
	print str(time.time()) + ": Adding request at " + str(start_time) + " and ending " + str(end_time) + " (Duration: " + str(duration) + ") [" + media_type + "] " + filename

	if play_mode is None:
	    play_mode = self.default_play_mode

	req = {
	    'media_type' : media_type,
	    'start_time' : start_time,
	    'end_time' : end_time,
	    'file_location' : file_location,
	    'filename' : filename,
	    'duration' : duration,
	    'offset' : offset,
	    'media_id' : media_id,
	    'order_num' : order_num,
	    'artist' : artist,
	    'title' : title,
	    'play_mode' : play_mode,
	    'priority' : self.priority,
	    'media_class' : self.media_type_to_class(media_type),
	    'controller' : self
	}

	self.insert_request(req)
	self.player.request_update.set()

    def insert_request(self, req):
	with self.lock:
	    index = len(self.queue)
	    for i in range(len(self.queue)):
		if self.queue[i]['start_time'] > req['start_time']:
		    index = i
		    break
	    self.queue.insert(index, req)

    def requeue_request(self, req):
	if self.allow_requeue is True:
	    self.insert_request(req)

    def clear_queue(self):
	with self.lock:
	    self.queue = [ ]

    def has_requests(self):
	if len(self.queue) > 0 or len(self.player.get_controller_requests(self)) > 0:
	    print str(time.time()) + ": Player: " + repr(self.player.get_controller_requests(self)) +"  Queue: " + repr([ req['media_type'] for req in self.queue ])
	    return True
	return False

    def request_is_playing(self):
	return self.player.controller_request_is_playing(self)

    def stop_requests(self):
	self.clear_queue()
	self.player.stop_controller_requests(self)

    def get_request(self, present_time, media_class, query=False):
	index = self.find_current_request(present_time)
	if index is None and query is True:
	    self.do_player_request(self, present_time)
	    index = self.find_current_request(present_time + 1)		# the plus one is because the new request's start time will be slight after present_time

	if index is None:
	    return None

	with self.lock:
	    for output in self.queue[index]['media_class'].split('/'):
		if output not in media_class:
		    return None
	    req = self.queue[index]
	    self.queue = self.queue[index+1:]
	return req

    def find_current_request(self, present_time):
	with self.lock:
	    for (i, req) in enumerate(self.queue):
		#print "Found " + req['media_class'] + " " + req['filename']
		#print str(req['start_time']) + " " + str(present_time) + " " + str(req['end_time'])
		#print str(req['start_time'] <= present_time) + " " + str(req['end_time'] > present_time)
		if present_time >= req['start_time'] and present_time < req['end_time']:
		    return i
	return None

    def get_requests_endtime(self):
	start_time = time.time()
	for output in self.player.get_controller_requests(self):
	    req = self.player.requests[output]
	    if req['end_time'] > start_time:
		start_time = req['end_time']

	with self.lock:
	    for req in self.queue:
		if req['end_time'] > start_time:
		    start_time = req['end_time']
	return start_time

    def check_for_start(self, present_time):
	if self.find_current_request(present_time) is not None:
	    return True
	return False

    @staticmethod
    def media_type_to_class(media_type):
	if media_type in [ 'video', 'testsignal' ]:
	    return 'audio/visual'
	elif media_type in [ 'audio', 'audioin', 'break' ]:
	    return 'audio'
	elif media_type in [ 'image' ]:
	    return 'visual'

    def set_request_callback(self, func):
	self.do_player_request = func

    def set_update_callback(self, func):
	self.do_player_update = func

    def set_next_update(self, t):
	print str(time.time()) + ": ***** Setting next update for " + self.name + " for " + str(t)
	with self.lock:
	    self.next_update = t

    def get_next_update(self):
	return self.next_update

    # called by the player to ask the controller what it wants to happen
    @staticmethod
    def do_player_request(ctrl, present_time):
	pass

    @staticmethod
    # called by the player to let the controller check things
    def do_player_update(ctrl, present_time):
	pass


#############################
#
# Output Classes
#
#############################

class ObVideoSinkBin (Gst.Bin):
    __gstmetadata__ = ( 'Video Sink Bin', 'Sink', '', '' )

    def __init__(self):
	Gst.Bin.__init__(self)

	self.videoscale = Gst.ElementFactory.make("videoscale", "videoscale")
	self.add(self.videoscale)
	self.videoconvert = Gst.ElementFactory.make("videoconvert", "videoconvert")
	self.add(self.videoconvert)
	self.videosink = Gst.ElementFactory.make("autovideosink", "videosink")
	self.add(self.videosink)

	self.videoscale.link(self.videosink)


	"""
	# Cairo Overlay Test
	self.cairooverlay = Gst.ElementFactory.make("cairooverlay", "cairooverlay")
	self.cairooverlay.connect("draw", self.overlay_draw)
	self.cairooverlay.connect("caps-changed", self.overlay_caps_changed)
	self.add(self.cairooverlay)
	self.videoscale.link(self.cairooverlay)
	self.cairooverlay.link(self.videoconvert)
	self.videoconvert.link(self.videosink)
	"""

	"""
	# RSVG Overlay Test
	self.svgoverlay = Gst.ElementFactory.make("rsvgoverlay", "rsvgoverlay")
	self.add(self.svgoverlay)
	self.videoscale.link(self.svgoverlay)
	self.svgoverlay.link(self.videoconvert)
	self.videoconvert.link(self.videosink)
	#self.svgoverlay.set_property('fit-to-frame', True)
	#self.svgoverlay.set_property('width', 1920)
	#self.svgoverlay.set_property('height', 1080)
	#self.svgoverlay.set_property('data', '<svg><text x="0" y="3" fill="blue">Hello World</text></svg>')
	self.svgoverlay.set_property('data', '<svg><circle cx="100" cy="100" r="50" fill="blue" /><text x="1" y="1" fill="red">Hello World</text></svg>')
	#self.svgoverlay.set_property('location', '/home/trans/Downloads/strawberry.svg')
	"""

	self.sinkpad = Gst.GhostPad.new('sink', self.videoscale.get_static_pad('sink'))
	self.add_pad(self.sinkpad)

    def overlay_caps_changed(self, overlay, caps):
	self.overlay_caps = GstVideo.VideoInfo()
	self.overlay_caps.from_caps(caps)

    def overlay_draw(self, overlay, context, arg1, arg2):
	#context.scale(self.overlay_caps.width, self.overlay_caps.height)
	#context.set_source_rgb(1, 0, 0)
	#context.show_text("Hello World")
	pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size("/home/trans/Downloads/kitty.jpg", self.overlay_caps.width, self.overlay_caps.height)
	Gdk.cairo_set_source_pixbuf(context, pixbuf, 0, 0)
	context.paint_with_alpha(100)
	context.stroke()


class ObAudioSinkBin (Gst.Bin):
    __gstmetadata__ = ( 'Audio Sink Bin', 'Sink', '', '' )

    def __init__(self):
	Gst.Bin.__init__(self)

        audio_output = obplayer.Config.setting('audio_output')
        if audio_output == 'alsa':
            self.audiosink = Gst.ElementFactory.make('alsasink', 'audiosink')
            alsa_device = obplayer.Config.setting('alsa_device')
            if alsa_device != '':
                self.audiosink.set_property('device', alsa_device)

        elif audio_output == 'esd':
            self.audiosink = Gst.ElementFactory.make('esdsink', 'audiosink')

        elif audio_output == 'jack':
            self.audiosink = Gst.ElementFactory.make('jackaudiosink', 'audiosink')
            self.audiosink.set_property('connect', 0)  # don't autoconnect ports.
	    name = obplayer.Config.setting('jack_port_name')
            self.audiosink.set_property('client-name', name if name else 'obplayer')

        elif audio_output == 'oss':
            self.audiosink = Gst.ElementFactory.make('osssink', 'audiosink')

        elif audio_output == 'pulse':
            self.audiosink = Gst.ElementFactory.make('pulsesink', 'audiosink')

        elif audio_output == 'test':
            self.audiosink = Gst.ElementFactory.make('fakesink', 'audiosink')

        else:
	    # this is stdout audio output (experimental, some possibility to use with streaming but doesn't propery output silence as audio data).
            self.audiosink = Gst.ElementFactory.make('autoaudiosink', 'audiosink')

	self.add(self.audiosink)

	self.sinkpad = Gst.GhostPad.new('sink', self.audiosink.get_static_pad('sink'))
	self.add_pad(self.sinkpad)


#############################
#
# Pipelines Classes
#
#############################

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

    def set_media_file(self, filename, offset):
	pass


class ObGstPipeline (ObPipeline):
    def __init__(self, name):
	ObPipeline.__init__(self, name)

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

    """
    def signal_about_to_finish(self, message):
	print "About to finish"
	with self.lock:
	    for ctrl in self.controllers:
		# TODO this function needs to 
		req = ctrl.get_next_request()
		# you can't just play the request... you need a function that just sets the uri, does the playlog, and all the log statements
    """

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

    def set_media_file(self, filename, offset):
	pass


class ObPlaybinPipeline (ObGstPipeline):
    output_caps = [ 'audio', 'visual' ]

    def __init__(self, name, player, audiovis=False):
	ObGstPipeline.__init__(self, name)
	self.position = None
	self.player = player
        self.pipeline = Gst.ElementFactory.make('playbin')
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
	if state == Gst.State.PLAYING:
	    (success, pos) = self.pipeline.query_position(Gst.Format.TIME)
	    if success is True:
		self.position = pos / Gst.SECOND
	self.wait_state(Gst.State.NULL)

	for output in mode.split('/'):
	    if output not in self.mode:
		#print self.name + " -- Connecting " + output
		self.pipeline.set_property('audio-sink' if output == 'audio' else 'video-sink', self.player.outputs[output])
		if output == 'visual':
		    obplayer.Gui.change_media_mode('video')
		self.mode.add(output)

	if state == Gst.State.PLAYING:
	    if self.position:
		self.seek_pause(self.position)
		self.position = None
	    self.wait_state(Gst.State.PLAYING)

    def unpatch(self, mode):
	obplayer.Log.log(self.name + ": unpatching " + mode, 'debug')
	(change, state, pending) = self.pipeline.get_state(0)
	if state == Gst.State.PLAYING:
	    (success, pos) = self.pipeline.query_position(Gst.Format.TIME)
	    if success is True:
		self.position = pos / Gst.SECOND
	self.wait_state(Gst.State.NULL)

	for output in mode.split('/'):
	    if output in self.mode:
		#print self.name + " -- Disconnecting " + output
		self.pipeline.set_property('audio-sink' if output == 'audio' else 'video-sink', self.fakesinks[output])
		self.mode.discard(output)

	if len(self.mode) > 0 and state == Gst.State.PLAYING:
	    if self.position:
		self.seek_pause(self.position)
		self.position = None
	    self.wait_state(Gst.State.PLAYING)

    def set_media_file(self, filename, offset):
	self.pipeline.set_property('uri', "file://" + filename)
	self.seek_pause(offset)

    def seek_pause(self, offset):
	# Set pipeline to paused state
	self.wait_state(Gst.State.PAUSED)

	if obplayer.Config.setting('gst_init_callback'):
	    os.system(obplayer.Config.setting('gst_init_callback'))

	if offset != 0:
	#if offset > 0.25:
	    if self.pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, offset * Gst.SECOND) == False:
		obplayer.Log.log('unable to seek on this track', 'error')

	if offset > 0:
	    obplayer.Log.log('resuming track at ' + str(offset) + ' seconds.', 'player')


class ObImagePipeline (ObPipeline):
    output_caps = [ 'visual' ]

    def __init__(self, name, player):
	ObPipeline.__init__(self, name)
	self.player = player

	"""
	obplayer.Gui.change_media_mode('video')
	self.imagebin = Gst.parse_launch('uridecodebin uri="file:///home/trans/Downloads/kitty.jpg" ! imagefreeze ! videoconvert ! videoscale ! video/x-raw, height=1920, width=1080 ! autovideosink')

        self.bus = self.imagebin.get_bus()
	self.bus.add_signal_watch()
	self.bus.enable_sync_message_emission()
	self.bus.connect("sync-message::element", self.sync_handler)
	self.bus.connect("message", self.message_handler)

	self.pipeline = self.imagebin
        self.pipeline.set_state(Gst.State.PLAYING)
        if self.wait_sync() == False:
            obplayer.Log.log('ObPlayer.init wait for state change (wait_sync()) failed (after stop).', 'error')
	"""

    def patch(self, mode):
	if 'visual' in mode:
	    obplayer.Gui.change_media_mode('image')
	ObPipeline.patch(self, mode)

    def unpatch(self, mode):
	ObPipeline.unpatch(self, mode)

    """
    def stop(self):
	# TODO make the canvas blank
	pass
    """

    def set_media_file(self, filename, offset):
	obplayer.Gui.drawing_area_image_update(filename)


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




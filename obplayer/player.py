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

Gst.init(None)

class ObPlayer (object):
    def __init__(self):
	self.request_update = threading.Event()
	self.lock = thread.allocate_lock()
	self.thread = None

	self.controllers = [ ]
	self.outputs = { }
	self.patches = { }
	self.requests = { }
	self.pipes = { }

    def start_player(self):
	self.thread = obplayer.ObThread('PlayerThread', target=self.run)
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
	self.pipes['audio'] = ObPlaybinPipeline('audio-playbin', self, obplayer.Config.setting('audio_out_visualization'))
	self.pipes['video'] = ObPlaybinPipeline('video-playbin', self)
	self.pipes['testsignal'] = ObTestPipeline('test-signal', self)
	self.pipes['image'] = ObImagePipeline('image-pipeline', self)
	self.pipes['break'] = ObBreakPipeline('audio-break', self)
	self.pipes['audioin'] = ObAudioInPipeline('audio-input', self)

	self.testctrl = self.create_controller('testsignal', 1, allow_requeue=False)
	def testsignal_request(self, present_time):
	    self.add_request(media_type='break', duration=5)
	    self.add_request(media_type='testsignal', duration=5000)
	self.testctrl.set_request_callback(testsignal_request)

    def player_quit(self):
	for pipe_name in self.pipes.keys():
	    self.pipes[pipe_name].quit()

    def create_controller(self, name, priority, default_play_mode=None, allow_overlay=False, allow_requeue=True):
	ctrl = ObPlayerController(self, name, priority, default_play_mode, allow_overlay, allow_requeue)
	for i in range(len(self.controllers)):
	    if self.controllers[i].priority < ctrl.priority:
		self.controllers.insert(i, ctrl)
		return ctrl
	self.controllers.append(ctrl)
	return ctrl

    def run(self):
	self.player_init()
	self.request_update.set()
	while not self.thread.stopflag.wait(0.1):
	    try:
		present_time = time.time()

		# stop any requests that have reached their end time and restore any outputs that may have been usurped by the now stopped request
		restore = False
		for output in self.requests.keys():
		    if self.requests[output] is not None and present_time > self.requests[output]['end_time']:
			self.stop_request(output)
			self.request_update.set()
			restore = True
		if restore:
		    print str(time.time()) + ": Attempting to restore outputs"
		    self.restore_outputs()

		#print str(time.time()) + ": Current State (" + str(time.time()) + "): " + repr(self.request_update.is_set()) + " | " + (self.requests['audio']['filename'] if self.requests['audio'] is not None else "No astream") + " | " + (self.requests['visual']['filename'] if 'visual' in self.requests and self.requests['visual'] is not None else "No vstream")
		test = time.time()

		# get a list of output names sorted by the priority of the currently playing request
		priority_list = sorted([ (self.requests[output]['priority'] if self.requests[output] else 0, output) for output in self.requests.keys() ], key=lambda pair: pair[0], reverse=True)

		req = None
		while len(priority_list) > 0:
		    #print str(time.time()) + ": Trying to fill in outputs: " + repr(priority_list)
		    remaining_outputs = [ pair[1] for pair in priority_list ]

		    req = self.get_request(present_time, priority_list[0][0], remaining_outputs, allow_query=self.request_update.is_set())

		    # if we found a request, then execute it, otherwise set req to the current highest priority request
		    if req:
			print remaining_outputs
			self.execute_request(req, output_limit=remaining_outputs)
		    else:
			req = self.requests[priority_list[0][1]]

		    if not req:
			# if there was no request found and no existing requests to check, then exit the loop
			break
		    else:
			# if the current request is to be played exclusively, then exit the loop
			if req['play_mode'] == 'exclusive':
			    break

			# remove all outputs that the currently playing request is using (they cannot be overidden by a lower priority request, so we wont check them)
			class_list = req['media_class'].split('/')
			priority_list = [ pair for pair in priority_list if pair[1] not in class_list ]

		#print "----- It took: " + str(time.time() - test)
		#print str(time.time()) + ": Current State (" + str(time.time()) + "): " + repr(self.request_update.is_set()) + " | " + (self.requests['audio']['filename'] if self.requests['audio'] is not None else "No astream") + " | " + (self.requests['visual']['filename'] if 'visual' in self.requests and self.requests['visual'] is not None else "No vstream")

		# if the updated flag was set, then clear it
		if self.request_update.is_set():
		    self.request_update.clear()

		# call the update functions
		with self.lock:
		    for ctrl in self.controllers:
			if ctrl.next_update and present_time > ctrl.next_update:
			    ctrl.next_update = 0
			    ctrl.call_player_update(present_time)

	    except:
		obplayer.Log.log("exception in " + self.thread.name + " thread", 'error')
		obplayer.Log.log(traceback.format_exc(), 'error')
		time.sleep(2)

	self.player_quit()

    def get_request(self, present_time, priority, output_list, allow_query=False):
	with self.lock:
	    for ctrl in self.controllers:
		# TODO justify this being <= and also the has_requests check at the bottom
		if ctrl.priority <= priority:
		    break

		req = ctrl.get_request(present_time, allow_query=allow_query)
		if req is not None:
		    if output_list:
			# the request must play on at least one of the outputs in output list or there's no point in trying to play it (it would be masked by a higher priority req)
			class_list = req['media_class'].split('/')
			for output in output_list:
			    if output in class_list:
				return req
			ctrl.requeue_request(req)
			return None
		    return req

		if ctrl.allow_overlay is False and ctrl.has_requests():
		    break
	return None

    def execute_request(self, req, output_limit=None):
	print str(time.time()) + ": executing request from " + req['controller'].name + ": [" + req['media_type'] + "] " + req['filename']

	request_pipe = self.pipes[req['media_type']]

	stop_list = [ ]
	if req['play_mode'] == 'exclusive':
	    stop_list = [ output for output in output_limit if self.requests[output] ]
	elif req['controller'].allow_overlay is False:
	    stop_list = [ output for output in output_limit if self.requests[output] and self.requests[output]['controller'] != req['controller'] ]

	if len(stop_list) > 0:
	    self.repatch_outputs('/'.join(stop_list), None)

	max_list = [ output for output in request_pipe.output_caps if output in output_limit ]
	min_list = [ output for output in req['media_class'].split('/') if output in output_limit ]

	patch_list = [ output for output in max_list if output in min_list or self.requests[output] is None ]
	patch_class = '/'.join(patch_list)
	print max_list
	print min_list
	print patch_class

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
	request_pipe.stop()
	if req['media_type'] in [ 'image', 'audio', 'video' ]:
	    media_filename = self.get_media_path(req)
	    print str(time.time()) + ": Media filename " + str(media_filename)
	    if media_filename is not None:
		request_pipe.set_media_file(media_filename, req['start_time'])
	request_pipe.start()

	# record the currently playing requests in the requests table (only the minimum set, so that other requests can use those outputs)
	for output in min_list:
	    self.requests[output] = req

	# write entry into play log.
        playlog_notes = 'resuming at ' + str(time.time() - req['start_time']) + 's'
        obplayer.PlaylogData.playlog_add(req['media_id'], req['artist'], req['title'], time.time(), req['controller'].name, playlog_notes)

        obplayer.Log.log("now playing track %s: %s - %s (id: %d file: %s duration: %s type: '%s' source: %s)" % (
	    str(req['order_num'] + 1) if req['order_num'] else '?',
	    unicode(req['artist']).encode('ascii', 'replace'),
	    unicode(req['title']).encode('ascii', 'replace'),
	    req['media_id'],
	    unicode(req['filename']).encode('ascii', 'replace'),
	    str(req['duration']),
	    req['media_type'],
	    req['controller'].name
	), 'player')

    def get_media_path(self, req):
        if '/' in req['file_location']:
            media_filename = req['file_location'] + '/' + req['filename']
	    if media_filename[0] != '/':
		media_filename = os.getcwd() + '/' + media_filename
        else:
	    # file location specified as 2-character directory code.
            media_filename = obplayer.Config.setting('remote_media') + '/' + req['file_location'][0] + '/' + req['file_location'][1] + '/' + req['filename']

	# see if the file exists.  if not, return false...
        if os.path.exists(media_filename) == False:
            obplayer.Log.log('ObPlayer: File ' + media_filename + ' does not exist. Skipping playback', 'error')
            return None
	return media_filename

    def stop_request(self, output):
	if self.requests[output] == None:
	    return

	req = self.requests[output]
	print "Stopping request: " + req['media_type'] + ": " + req['filename']
	request_pipe = self.pipes[req['media_type']]
	request_pipe.stop()

	for name in self.requests.keys():
	    if self.requests[name] == req:
		self.requests[name] = None

    def repatch_outputs(self, media_class, media_type):
	print "Repatching " + media_class + " to pipe " + str(media_type)

	output_list = media_class.split('/')
	for pipe in self.pipes.keys():
	    if pipe != media_type:
		unpatch_list = [ output for output in output_list if self.patches[output] == pipe ]
		if len(unpatch_list) > 0:
		    if set(unpatch_list) == self.pipes[pipe].mode:
			self.pipes[pipe].stop()
			if self.requests[unpatch_list[0]]:
			    self.requests[unpatch_list[0]]['controller'].requeue_request(self.requests[unpatch_list[0]])
			# TODO requeue any request for which we stop the pipe
			print "*** We should be requeuing"
		    self.pipes[pipe].unpatch('/'.join(unpatch_list))

	if media_type is not None:
	    for output in [ output for output in output_list if self.patches[output] == media_type ]:
		if self.requests[output]:
		    self.requests[output]['controller'].requeue_request(self.requests[output])
		    break
	    patch_list = [ output for output in output_list if self.patches[output] != media_type ]
	    if len(patch_list) > 0:
		self.pipes[media_type].patch('/'.join(patch_list))
	for output in output_list:
	    self.patches[output] = media_type
	    self.requests[output] = None
		
    def restore_outputs(self):
	for output in self.requests.keys():
	    if self.requests[output] is not None:
		# TODO you should maybe use the output caps instead of the media_class
		class_list = self.requests[output]['media_class'].split('/')
		patch_list = [ output for output in class_list if self.requests[output] is None ]
		if len(patch_list) > 0:
		    patch_list.sort()
		    print "restoring outputs " + str(patch_list)
		    self.repatch_outputs('/'.join(patch_list), self.patches[output])
		    for class_name in patch_list:
			self.requests[class_name] = self.requests[output]

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
    def __init__(self, player, name, priority, default_play_mode=None, allow_overlay=False, allow_requeue=True):
	if default_play_mode is None:
	    default_play_mode = 'exclusive'
	self.player = player
	self.name = name
	self.priority = priority
	self.default_play_mode = default_play_mode
	self.allow_requeue = allow_requeue
	self.allow_overlay = allow_overlay

	self.lock = thread.allocate_lock()
	self.queue = [ ]
	self.next_update = 0

	# TODO you could have a list of failed requests, where the request is automatically added (auto limit to say 5 entries)
	self.failed = [ ]
	# TODO this is possible too, but i think calling the player is better, even though it's a bit messy.  It's less messy than this way
	#self.playing = [ ]

    # media_type can be:	audio, video, image, audioin, break, testsignal
    # play_mode can be:		exclusive, overlap
    def add_request(self, media_type, start_time=None, end_time=None, file_location='', filename='', duration=0.0, offset=0, media_id=0, order_num=-1, artist='unknown', title='unknown', play_mode=None):
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
	#self.player.request_update.set()

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
	    with self.lock:
		for queued in self.queue:
		    if queued == req:
			print "We totally didn't requeue!"
			return
	    #print "Requeuing request from [" + self.name + "] for (Duration: " + str(req['duration']) + ") [" + req['media_type'] + "] " + req['filename']
	    self.insert_request(req)
	else:
	    # if requeues are not allowed and we are requeuing, then the player wont be playing the currently queued requests,
	    # and we should get rid of them all, so that the player always calls the controllers to get new requests
	    print "Clearing queue for source " + self.name
	    self.clear_queue()

    def clear_queue(self):
	with self.lock:
	    self.queue = [ ]

    def has_requests(self):
	if len(self.queue) > 0 or len(self.player.get_controller_requests(self)) > 0:
	    return True
	return False

    def request_is_playing(self):
	return self.player.controller_request_is_playing(self)

    def stop_requests(self):
	self.clear_queue()
	self.player.stop_controller_requests(self)

    def get_request(self, present_time, allow_query=False):
	index = self.find_current_request(present_time)
	if index is None and allow_query is True:
	    self.call_player_request(present_time)
	    index = self.find_current_request(present_time + 1)		# the plus one is because the new request's start time will be slight after present_time

	if index is None:
	    return None

	with self.lock:
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
	#print str(time.time()) + ": ***** Setting next update for " + self.name + " for " + str(t)
	with self.lock:
	    self.next_update = t

    def get_next_update(self):
	return self.next_update

    def call_player_request(self, present_time):
	try:
	    return self.do_player_request(self, present_time)
	except:
	    obplayer.Log.log("exception while calling do_player_request() on " + self.name, 'error')
	    obplayer.Log.log(traceback.format_exc(), 'error')

    def call_player_update(self, present_time):
	try:
	    return self.do_player_update(self, present_time)
	except:
	    obplayer.Log.log("exception while calling do_player_update() on " + self.name, 'error')
	    obplayer.Log.log(traceback.format_exc(), 'error')

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
    __gstmetadata__ = ( "OpenBroadcaster Video Sink Bin", "Sink", "Custom video sink for OpenBroadcaster", "Sari McFarland <sari@pikalabs.com>" )

    def __init__(self):
	Gst.Bin.__init__(self)

	self.elements = [ ]

	## create basic filter elements
	self.elements.append(Gst.ElementFactory.make("queue", "pre_queue"))
	self.elements.append(Gst.ElementFactory.make("videoscale", "pre_scale"))
	self.elements.append(Gst.ElementFactory.make("videoconvert", "pre_convert"))

	## create overlay elements (if enabled)
        if obplayer.Config.setting('overlay_enable'):
	    overlay_mode = obplayer.Config.setting('overlay_mode')
	    if overlay_mode:
		self.overlay = Gst.ElementFactory.make('cairooverlay', "overlay")
		self.overlay.connect("draw", self.overlay_draw)
		self.overlay.connect("caps-changed", self.overlay_caps_changed)
	    self.elements.append(self.overlay)
	    self.elements.append(Gst.ElementFactory.make("queue", "post_queue"))
	    self.elements.append(Gst.ElementFactory.make("videoscale", "post_scale"))
	    self.elements.append(Gst.ElementFactory.make("videoconvert", "post_convert"))

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

	for element in self.elements:
	    self.add(element)

	for index in range(0, len(self.elements) - 1):
	    self.elements[index].link(self.elements[index + 1])

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

	self.sinkpad = Gst.GhostPad.new('sink', self.elements[0].get_static_pad('sink'))
	self.add_pad(self.sinkpad)

    def overlay_caps_changed(self, overlay, caps):
	self.overlay_caps = GstVideo.VideoInfo()
	self.overlay_caps.from_caps(caps)

    def overlay_draw(self, overlay, context, arg1, arg2):
	obplayer.Gui.draw_overlay(context, self.overlay_caps.width, self.overlay_caps.height)


class ObAudioSinkBin (Gst.Bin):
    __gstmetadata__ = ( "OpenBroadcaster Audio Sink Bin", "Sink", "Custom audio sink for OpenBroadcaster", "Sari McFarland <sari@pikalabs.com>" )

    def __init__(self):
	Gst.Bin.__init__(self)

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

    def set_media_file(self, filename, start_time):
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


class ObPlaybinPipeline (ObGstPipeline):
    output_caps = [ 'audio', 'visual' ]

    def __init__(self, name, player, audiovis=False):
	ObGstPipeline.__init__(self, name)
	self.player = player
	self.start_time = 0
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

    def set_media_file(self, filename, start_time):
	self.start_time = start_time
	self.pipeline.set_property('uri', "file://" + filename)
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


class ObAudioInPipeline (ObGstPipeline):
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

    def set_media_file(self, filename, start_time):
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




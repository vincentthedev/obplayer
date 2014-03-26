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

import time
import thread

class ObPlaylist (object):
    def __init__(self, show_id):
	self.pos = 0
	self.playlist = obplayer.RemoteData.get_show_media(show_id)
	if self.playlist == None:
	    self.playlist = [ ]

    def size(self):
	return len(self.playlist)

    def current_pos(self):
	if self.pos >= len(self.playlist):
	    return len(self.playlist) - 1
	return self.pos

    def current(self):
	if self.pos >= len(self.playlist):
	    return None
	return self.playlist[self.pos]

    def increment(self):
	self.pos += 1
	if self.pos >= len(self.playlist):
	    return False
	return True

    def decrement(self):
	self.pos -= 1
	if self.pos < 0:
	    self.pos = 0
	    return False
	return True

    def set(self, pos):
	self.pos = pos
	if self.pos < 0:
	    self.pos = 0
	elif self.pos > len(self.playlist):
	    self.pos = len(self.playlist)

    def is_finished(self):
	if self.pos >= len(self.playlist):
	    return True
	return False

    def is_last(self):
	if self.pos + 1 >= len(self.playlist):
	    return True
	return False

    def seek_current(self, present_offset):
	for i in range(0, len(self.playlist) - 1):
	    if self.playlist[i + 1]['offset'] > present_offset:
		self.pos = i
		return
	self.pos = len(self.playlist) - 1

    def advance_to_current(self, present_offset):
	if self.pos + 1 < len(self.playlist) and present_offset >= self.playlist[self.pos + 1]['offset']:
	    self.pos += 1
	    return True
	return False


class ObShow (object):
    def __init__(self):
	self.paused = False
	self.pause_position = 0
	self.auto_advance = True

	self.image_end_time = 0
	self.av_end_time = 0
	self.media_start_time = 0
	self.media_end_time = 0
	self.now_playing = None

	self.show_data = None
	self.playlist = None
	self.groups = None

    @staticmethod
    def find_show(datetime):
	data = obplayer.RemoteData.get_present_show(datetime)
	if not data:
	    return None

	self = ObShow()
	self.show_data = data
	self.playlist = ObPlaylist(self.show_data['id'])
	self.groups = obplayer.RemoteData.load_groups(self.show_data['id'])
	return self

    def id(self):
	return self.show_data['id']

    def show_id(self):
	return self.show_data['show_id']

    def name(self):
	return self.show_data['name']

    def start_time(self):
	return self.show_data['start_time']

    def end_time(self):
	return self.show_data['end_time']

    def get_playlist(self):
	return self.playlist.playlist

    def get_groups(self):
	return self.groups

    def start_show(self, present_time):

	if self.show_data['type'] == 'live_assist':
	    # if we start the show less than 30 seconds in, then start it, otherwise start paused
	    if present_time - self.show_data['start_time'] < 30:
		obplayer.Log.log('starting live assist show', 'scheduler')
	    else:
		obplayer.Log.log('starting live assist show paused', 'scheduler')
		self.auto_advance = False
	else:
	    # find the track that should play at the present time
	    self.playlist.seek_current(present_time - self.show_data['start_time'])
	    obplayer.Log.log('starting at track number ' + str(self.playlist.pos), 'scheduler')

	self.play_current(present_time)

    def play_next(self, present_time):
	if self.is_paused() or self.playlist.is_finished():
	    self.stop_current()
	    return False

	self.increment()

	if self.show_data['type'] != 'live_assist':
	    # this will keep trying to play until the media checks out as valid (in the case of presently downloading)
	    # in case downloading time is too long, we might still need to advance to the next track.
	    self.playlist.advance_to_current(present_time - self.show_data['start_time'])

	return self.play_current(present_time)

    def play_current(self, present_time):
	if self.is_paused():
	    return False

	media = self.playlist.current()
	if not media or not obplayer.Sync.check_media(media):
	    return False

	if self.show_data['type'] == 'live_assist':
	    self.play_media(media, 0, present_time)
	else:
	    offset = present_time - self.show_data['start_time'] - media['offset']
	    #print str(self.playlist.pos) + " " + media['title'] + " Offset: " + str(offset) + " " + str(present_time - self.show_data['start_time']) + " " + str(media['offset'])
	    self.play_media(media, offset, present_time)
	return True

    def play_media(self, media, offset, present_time):
	self.stop_current()
	self.now_playing = media
	self.media_start_time = present_time - offset

	if media['media_type'] == 'breakpoint':
	    obplayer.Log.log('stopping on breakpoint at position ' + str(self.playlist.pos), 'scheduler')
	    self.playlist.increment()
	    self.auto_advance = False
	    obplayer.Sync.now_playing_update(self.show_data['show_id'], self.show_data['end_time'], '', '', self.show_data['name'])

	else:
	    obplayer.Player.play(media, offset)

	    if media['media_type'] == 'image':
		self.image_end_time = self.media_start_time + media['duration']
	    else:
		self.av_end_time = self.media_start_time + media['duration']

	    self.media_end_time = self.media_start_time + media['duration']
	    obplayer.Sync.now_playing_update(self.show_data['show_id'], self.show_data['end_time'], media['media_id'], self.media_end_time, self.show_data['name'])

    def stop_current(self):
	# TODO maybe this shouldn't check anything and check in Player.stop to see if already stopped
	if self.av_end_time > 0:
	    obplayer.Player.stop()
	    self.av_end_time = 0
	self.media_end_time = 0

    def playlist_seek(self, track_num, seek):
	self.playlist.set(track_num)
	self.auto_advance = True
	if not self.playlist.is_finished():
	    media = self.playlist.current()
	    self.play_media(media, media['duration'] * (seek / 100), time.time())

    def play_group_item(self, group_num, group_item_num, seek):
	if self.show_data['type'] != 'live_assist':
	    return False

	if group_num < 0 or group_num >= len(self.groups):
	    return False
	group = self.groups[group_num]['items']

	if group_item_num < 0 or group_item_num >= len(group):
	    return False

	media = group[group_item_num]
	self.play_media(media, media['duration'] * (seek / 100), time.time())
	self.auto_advance = False
	return True

    def increment(self):
	if self.is_paused():
	    return False
	self.playlist.increment()

    def pause(self):
	if not self.paused:
	    self.paused = True
	    self.pause_position = time.time() - self.media_start_time
	    self.stop_current()

    def unpause(self):
	if self.paused:
	    self.paused = False
	    self.play_media(self.now_playing, self.pause_position, time.time())
	    self.pause_position = 0
	elif not self.auto_advance:
	    self.auto_advance = True
	    self.play_current(time.time())

    def is_paused(self):
	return self.paused or not self.auto_advance

    def position(self):
	print "Position... Start: " + str(self.media_start_time) + " End: " + str(self.media_end_time)
	if not self.media_end_time:
	    if self.now_playing == None:
		return 0
	    return self.now_playing['duration']
	return time.time() - self.media_start_time


class ObScheduler:

    def __init__(self):
        self.show_update_time = 0
        self.emerg_update_time = 0

        self.emerg_broadcasts = False
        self.emerg_broadcast_until = 0

	self.present_show = None

	self.lock = thread.allocate_lock()

    # update show update time after show sync. (if next show starting sooner than previously set, we need to update!)
    # this is already subject to the 'show lock' cutoff time.
    def update_show_update_time(self):
        next_show_times = obplayer.RemoteData.get_next_show_times(time.time())
        if next_show_times and next_show_times['start_time'] < self.show_update_time:
            self.show_update_time = next_show_times['start_time']

    def schedule_loop(self):

        present_time = time.time()
	self.lock.acquire()

	# run through emergency broadcasts and play if it's time. don't play while syncing emerg since it might be changing data or downloading new data.
        if obplayer.RemoteData.emergency_broadcasts != False and self.emerg_broadcast_until <= present_time and obplayer.Sync.emerg_sync_running == False:
            for (bindex, broadcast) in obplayer.RemoteData.emergency_broadcasts.iteritems():
                if broadcast['next_play'] <= present_time:

                    if obplayer.Sync.check_media(broadcast):

			# REMOVE self.Gui.set_media_summary(broadcast, 'emergency broadcast')

                        obplayer.Log.log('play emergency broadcast', 'emerg')
                        obplayer.RemoteData.emergency_broadcasts[bindex]['next_play'] = present_time + broadcast['duration'] + broadcast['frequency']
                        obplayer.RemoteData.emergency_broadcasts[bindex]['last_play'] = present_time
                        broadcast['order_num'] = False

                        obplayer.Player.play(broadcast, 0, 'emerg', broadcast['id'])
                        self.emerg_broadcast_until = time.time() + broadcast['duration'] + 3

			# we set this so the show will resume.
                        self.show_update_time = present_time
                        break

        if present_time >= self.show_update_time and present_time >= self.emerg_broadcast_until:

            self.present_show = ObShow.find_show(present_time)
            next_show_times = obplayer.RemoteData.get_next_show_times(present_time)

	    # no show, try again in 1min30secs.  (we add the 30 seconds to let the emergency broadcaster update come through first, if applicable.
            if self.present_show == None:

                self.show_update_time = present_time + 90

		# if next show starting in less than 90s, we need to update sooner.
                if next_show_times != None and self.show_update_time > next_show_times['start_time']:
                    self.show_update_time = next_show_times['start_time']

                obplayer.Log.log('no show found.', 'scheduler')

		# update now_playing data.
                obplayer.Sync.now_playing_update('', '', '', '', '')

            else:
		# we have a show, let's load it...
                obplayer.Log.log('loading show ' + str(self.present_show.show_id()), 'scheduler')

		# update now_playing data
                obplayer.Sync.now_playing_update(self.present_show.show_id(), self.present_show.end_time(), '', '', self.present_show.name())
		# TODO get rid of this?? ^^^

		# figure out show update time. (lower of next show start time, present show end time).
                if next_show_times != None and next_show_times['start_time'] < self.present_show.end_time():
                    self.show_update_time = next_show_times['start_time']
                else:
                    self.show_update_time = self.present_show.end_time()

		self.present_show.start_show(present_time)

                if self.present_show.playlist.is_finished():
		    if next_show_times != None:
			obplayer.Log.log('this show over. waiting for next show to start in ' + str(next_show_times['start_time'] - present_time) + ' seconds', 'scheduler')
		    else:
			obplayer.Log.log('this show over. next show not found. will retry after next update.')

	if self.present_show != None:
	    # media stop time (image)
	    if self.present_show.image_end_time != 0 and present_time >= self.present_show.image_end_time:
		self.present_show.image_end_time = 0
		obplayer.Player.stop('image')
		# REMOVE self.Gui.reset_media_summary('image')

	    # media stop time (av)
	    if self.present_show.av_end_time != 0 and present_time >= self.present_show.av_end_time:
		#print ">>Stopping"
		self.present_show.av_end_time = 0
		obplayer.Player.stop('av')
		# REMOVE self.Gui.reset_media_summary('av')

	    # media update time.
	    if self.present_show.media_end_time > 0 and present_time >= self.present_show.media_end_time and present_time >= self.emerg_broadcast_until:
		print "Updating At: " + str(present_time)
		self.present_show.play_next(present_time)
		#print "Seek Time: " + str(obplayer.Player.stats_seek_time)
		#if self.present_show.now_playing:
		    #print "Scheduler Duration: " + str(self.present_show.media_end_time - self.present_show.media_start_time)
		#print "Time To Start: " + str(obplayer.Player.media_actual_start - present_time)
		#print "Next update at " + str(self.present_show.media_end_time)

	self.lock.release()
        return True

    # next update (timestamp) - show update or media update. this will be when the scheduler will next trigger a 'play' command to the player
    # this is used by the fallback player to determine whether it's worthwhile playing some fallback media. if scheduler is about to do something, forget about it.
    # this also avoids race conditions between the fallback player and scheduler (though that would probably be pretty unlikely).
    def next_update(self):
        next_update = 0

        if self.present_show.media_end_time > 0 and (next_update == 0 or self.present_show.media_end_time < next_update):
            next_update = self.present_show.media_end_time

        if self.show_update_time > 0 and (next_update == 0 or self.show_update_time < next_update):
            next_update = self.show_update_time

        if self.emerg_update_time > 0 and (next_update == 0 or self.emerg_update_time < next_update):
            next_update = self.emerg_update_time

        return next_update

    def get_show_name(self):
	if self.present_show == None:
	    return '(no show playing)'
	return self.present_show.name()

    def get_show_end(self):
	if self.present_show == None:
	    return 0
	return self.present_show.end_time()

    def get_current_playlist(self):
	playlist = [ ]
	if self.present_show != None:
	    for track in self.present_show.get_playlist():
		data = { 'track_id' : track['media_id'], 'artist' : track['artist'], 'title' : track['title'], 'duration' : track['duration'], 'media_type' : track['media_type'] }
		playlist.append(data)
	return playlist

    def get_current_groups(self):
	groups = [ ]
	if self.present_show != None:
	    for group in self.present_show.get_groups():
		group_items = [ ]
		for group_item in group['items']:
		    data = { 'id' : group_item['id'], 'artist' : group_item['artist'], 'title' : group_item['title'], 'duration' : group_item['duration'], 'media_type' : group_item['media_type'] }
		    group_items.append(data)
		groups.append({ 'name' : group['name'], 'items' : group_items })
	return groups

    def playlist_seek(self, track_num, seek):
	if self.present_show == None:
	    return False

	self.lock.acquire()
	self.present_show.playlist_seek(track_num, seek)
	self.lock.release()
	return True

    def play_group_item(self, group_num, group_item_num, seek):
	if self.present_show == None:
	    return False

	self.lock.acquire()
	self.present_show.play_group_item(group_num, group_item_num, seek)
	self.lock.release()
	return True

    def unpause_show(self):
	if self.present_show == None:
	    return False

	self.lock.acquire()
	self.present_show.unpause()
	self.lock.release()
	return True

    def pause_show(self):
	if self.present_show == None:
	    return False

	self.lock.acquire()
	self.present_show.pause()
	self.lock.release()
	return True

    def find_group_item_pos(self, group_id):
	if self.present_show == None:
	    return False

	groups = self.present_show.get_groups()
	for i in xrange(0, len(groups)):
	    group_items = groups[i]['items']
	    for j in xrange(0, len(group_items)):
		if group_items[j]['id'] == group_id:
		    return (i, j)
	return (0, 0)

    def get_now_playing(self):
	data = { }

	status = obplayer.Player.status()
	if status == False:
	    data['status'] = 'playing'
	else:
	    data['status'] = 'stopped'

	if self.present_show != None and self.present_show.now_playing != None:
	    now_playing = self.present_show.now_playing

	    data['artist'] = now_playing['artist']
	    data['title'] = now_playing['title']
	    data['position'] = self.present_show.position()

	    if 'group_id' in now_playing:
		data['mode'] = 'group'
		(data['group_num'], data['group_item_num']) = self.find_group_item_pos(now_playing['id'])
	    else:
		data['mode'] = 'playlist'
		data['track'] = self.present_show.playlist.current_pos()
	else:
	    data['artist'] = ''
	    data['title'] = ''
	    data['position'] = 0
	    data['track'] = -1

	print data
	return data

 

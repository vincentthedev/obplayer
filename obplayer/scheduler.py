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
    def __init__(self, datetime):
	self.paused = False
	self.media_end_time = 0
	self.media_start_time = 0
	self.now_playing = None

	self.show_data = obplayer.RemoteData.get_present_show(datetime)
	self.playlist = ObPlaylist(self.show_data['id'])
	self.groups = obplayer.RemoteData.load_groups(self.show_data['id'])

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

    def show_over(self, present_time=-1):
	if present_time == -1:
	    present_time = time.time()

	if present_time >= self.show_data['end_time']:
	    return True
	else:
	    return False

    def resume(self, present_time):
	self.media_end_time = 0

	if self.show_data['type'] == 'live_assist':
	    # if we start the show less than 30 seconds in, then start it, otherwise start paused
	    if present_time - self.show_data['start_time'] < 30:
		obplayer.Log.log('starting live assist show', 'scheduler')
		self.media_end_time = present_time
	    else:
		obplayer.Log.log('starting live assist show paused', 'scheduler')
		self.pause()
	else:
	    # find the track that should play at the present time
	    self.playlist.seek_current(present_time - self.show_data['start_time'])
	    obplayer.Log.log('starting at track number ' + str(self.playlist.pos), 'scheduler')
	    self.media_end_time = present_time

    def play_current(self, present_time):
	self.media_end_time = 0

	if self.is_paused():
	    return False

	if self.show_data['type'] != 'live_assist':
	    # this will keep trying to play until the media checks out as valid (in the case of presently downloading)
	    # in case downloading time is too long, we might still need to advance to the next track.
	    self.playlist.advance_to_current(present_time - self.show_data['start_time'])

	if self.playlist.is_finished():
	    return False

	media = self.playlist.current()
	if not media or not obplayer.Sync.check_media(media):
	    return False

	if self.show_data['type'] == 'live_assist':
	    self.play_media(media, 0, present_time)
	    self.increment()
	    self.media_end_time = present_time + media['duration']

	else:
	    offset = present_time - self.show_data['start_time'] - media['offset']
	    print str(self.playlist.pos) + " " + media['title'] + " Offset: " + str(offset) + " " + str(present_time - self.show_data['start_time']) + " " + str(media['offset'])
	    self.play_media(media, offset, present_time)
	    self.increment()

	obplayer.Sync.now_playing_update(self.show_data['show_id'], self.show_data['end_time'], media['media_id'], self.media_end_time, self.show_data['name'])
	return True

    def play_media(self, media, offset, present_time):
	self.now_playing = media
	self.media_start_time = present_time - offset

	if media['media_type'] == 'breakpoint':
	    obplayer.Log.log('stopping on breakpoint at position ' + str(self.playlist.pos), 'scheduler')
	    # TODO Should the stop times be move to the player? should they strictly be handled in the main loop?
	    self.stop_current()
	    self.playlist.increment()
	    self.pause()
	else:
	    obplayer.Player.play(media, offset)

	    if media['media_type'] == 'image':
		obplayer.Scheduler.image_stop_time = present_time + media['duration'] - offset
	    else:
		obplayer.Scheduler.av_stop_time = present_time + media['duration'] - offset

	    if not self.playlist.is_finished():
		self.media_end_time = present_time + media['duration'] - offset

    def stop_current(self):
	if obplayer.Scheduler.av_stop_time > 0:
	    obplayer.Player.stop()
	    obplayer.Scheduler.av_stop_time = 0

    def playlist_seek(self, track_num, seek):
	self.playlist.set(track_num)
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
	self.pause()
	return True

    def increment(self):
	if self.paused:
	    return False
	self.playlist.increment()

    def pause(self):
	self.paused = True

    def unpause(self):
	self.paused = False

    def is_paused(self):
	return self.paused


class ObScheduler:

    def __init__(self):

        self.show_update_time = 0
        self.media_update_time = 0
        self.emerg_update_time = 0

        self.av_stop_time = 0
        self.image_stop_time = 0

        self.emerg_broadcasts = False
        self.emerg_broadcast_until = 0

	self.present_show = None
	self.present_show_playlist = None
	self.present_show_groups = None
	self.next_show = None

	self.present_track = -1
	self.next_track = -1
	self.paused = False
	self.now_playing = None

	self.lock = thread.allocate_lock()
	self.play_lock = thread.allocate_lock()

    # update show update time after show sync. (if next show starting sooner than previously set, we need to update!)
    # this is already subject to the 'show lock' cutoff time.
    def update_show_update_time(self):
        next_show = obplayer.RemoteData.get_next_show(time.time())
        if next_show and next_show['start_time'] < self.show_update_time:
            self.show_update_time = next_show['start_time']

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
            self.present_show = ObShow(present_time)
            self.next_show = obplayer.RemoteData.get_next_show(present_time)

	    # no show, try again in 1min30secs.  (we add the 30 seconds to let the emergency broadcaster update come through first, if applicable.
            if self.present_show == None:

                self.show_update_time = present_time + 90
                self.media_update_time = present_time + 120  # don't bother updating media, nothing playing now!

		# if next show starting in less than 90s, we need to update sooner.
                if self.next_show != None and self.show_update_time > self.next_show['start_time']:
                    self.show_update_time = self.next_show['start_time']

                obplayer.Log.log('no show found.', 'scheduler')

		# update now_playing data.
                obplayer.Sync.now_playing_update('', '', '', '', '')
            else:

		# REMOVE self.Gui.reset_show_summary()
		# REMOVE self.Gui.reset_media_summary('all')

		# we have a show, let's load it...

                obplayer.Log.log('loading show ' + str(self.present_show.show_id()), 'scheduler')

		# REMOVE self.Gui.set_show_summary(str(self.present_show['show_id']), self.present_show['name'], self.present_show['description'])

		# update now_playing data
                obplayer.Sync.now_playing_update(self.present_show.show_id(), self.present_show.end_time(), '', '', self.present_show.name())

		# figure out show update time. (lower of next show start time, present show end time).
                if self.next_show != None and self.next_show['start_time'] < self.present_show.end_time():
                    self.show_update_time = self.next_show['start_time']
                else:
                    self.show_update_time = self.present_show.end_time()

		self.present_show.resume(present_time)
		self.media_update_time = self.present_show.media_end_time

                if self.present_show.playlist.is_finished():
		    if self.next_show != None:
			obplayer.Log.log('this show over. waiting for next show to start in ' + str(self.next_show['start_time'] - present_time) + ' seconds', 'scheduler')
		    else:
			obplayer.Log.log('this show over. next show not found. will retry after next update.')
			# REMOVE self.Gui.reset_show_summary()
			# REMOVE self.Gui.reset_media_summary('all')

	# media stop time (image)
        if self.image_stop_time != 0 and present_time >= self.image_stop_time:
            self.image_stop_time = 0
            obplayer.Player.stop('image')
	    # REMOVE self.Gui.reset_media_summary('image')

	# media stop time (av)
        if self.av_stop_time != 0 and present_time >= self.av_stop_time:
            self.av_stop_time = 0
            obplayer.Player.stop('av')
	    # REMOVE self.Gui.reset_media_summary('av')

	# media update time.
        if self.media_update_time > 0 and present_time >= self.media_update_time and present_time >= self.emerg_broadcast_until:
	    self.present_show.play_current(present_time)
	    self.media_update_time = self.present_show.media_end_time

	self.lock.release()
        return True
    """

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
            self.present_show = obplayer.RemoteData.get_present_show(present_time)
            self.next_show = obplayer.RemoteData.get_next_show(present_time)

	    # no show, try again in 1min30secs.  (we add the 30 seconds to let the emergency broadcaster update come through first, if applicable.
            if self.present_show == None:
		self.present_show_playlist = None
		self.present_show_groups = None

                self.show_update_time = present_time + 90
                self.media_update_time = present_time + 120  # don't bother updating media, nothing playing now!

		# if next show starting in less than 90s, we need to update sooner.
                if self.next_show != None and self.show_update_time > self.next_show['start_time']:
                    self.show_update_time = self.next_show['start_time']

                obplayer.Log.log('no show found.', 'scheduler')

		# update now_playing data.
                obplayer.Sync.now_playing_update('', '', '', '', '')
            else:

		# REMOVE self.Gui.reset_show_summary()
		# REMOVE self.Gui.reset_media_summary('all')

		# we have a show, let's load it...

                obplayer.Log.log('loading show ' + str(self.present_show['show_id']), 'scheduler')

		# REMOVE self.Gui.set_show_summary(str(self.present_show['show_id']), self.present_show['name'], self.present_show['description'])

		# update now_playing data
                obplayer.Sync.now_playing_update(self.present_show['show_id'], self.present_show['end_time'], '', '', self.present_show['name'])

		# figure out show update time. (lower of next show start time, present show end time).
                if self.next_show != None and self.next_show['start_time'] < self.present_show['end_time']:
                    self.show_update_time = self.next_show['start_time']
                else:
                    self.show_update_time = self.present_show['end_time']

                self.present_show_playlist = obplayer.RemoteData.get_show_media(self.present_show['id'])
		self.present_show_groups = obplayer.RemoteData.load_groups(self.present_show['id'])

		self.paused = False
		self.media_update_time = -1

		# add track start times to media list
                #track_start = self.present_show['start_time']
                if self.present_show_playlist != None:
                    for media in self.present_show_playlist:
                        media['start_time'] = self.present_show['start_time'] + media['offset']
			# track_start = track_start + self.present_show_playlist[mindex]['duration']

		    if self.present_show['type'] == 'live_assist':
			self.next_track = 0

			# If the current time is less than 30 seconds past the scheduled show start, then start the show, otherwise start it paused
			if present_time - self.present_show['start_time'] < 30:
			    self.media_update_time = present_time

		    else:
			# search backwards through media list to find last instance where time is lessthan or equalto present time (which track to begin on)
			self.next_track = -1
			for (mindex, media) in reversed(list(enumerate(self.present_show_playlist))):
			    if media['start_time'] <= present_time:
				next_track_offset = present_time - media['start_time']

				if next_track_offset < media['duration']:
				    self.next_track = mindex
				    obplayer.Log.log('found start track ' + str(self.next_track + 1) + ' to start', 'scheduler')
				    self.media_update_time = present_time
				    break

                if self.next_track == -1:
		    if self.next_show != None:
			obplayer.Log.log('this show over. waiting for next show to start in ' + str(self.next_show['start_time'] - present_time) + ' seconds', 'scheduler')
		    else:
			obplayer.Log.log('this show over. next show not found. will retry after next update.')
			# REMOVE self.Gui.reset_show_summary()
			# REMOVE self.Gui.reset_media_summary('all')

	# media stop time (image)
        if self.image_stop_time != 0 and present_time >= self.image_stop_time:
            self.image_stop_time = 0
            obplayer.Player.stop('image')
	    # REMOVE self.Gui.reset_media_summary('image')

	# media stop time (av)
        if self.av_stop_time != 0 and present_time >= self.av_stop_time:
            self.av_stop_time = 0
            obplayer.Player.stop('av')
	    # REMOVE self.Gui.reset_media_summary('av')

	# media update time.
        if self.media_update_time != -1 and present_time >= self.media_update_time and self.next_track != -1 and present_time >= self.emerg_broadcast_until and self.present_show_playlist:

	    # this will keep trying to play until the media checks out as valid (in the case of presently downloading)
	    # in case downloading time is too long, we might still need to advance to the next track.
	    # (note that in the case of the show actually changing, self.present_show_playlist and self.next_track will be updated so we are fine).

            if not self.paused and self.next_track + 1 < len(self.present_show_playlist):  # okay there is a next track. is it needing to start?
                if present_time >= self.present_show_playlist[self.next_track + 1]['start_time']:
                    self.next_track += 1

            if self._play_media(self.present_show_playlist[self.next_track], present_time - self.present_show_playlist[self.next_track]['start_time']):
		self.present_track = self.next_track

		if not self.paused:
		    # get next track ready.
		    self.next_track += 1

		    # if next track doesn't exist...
		    if self.next_track >= len(self.present_show_playlist):
			self.next_track = -1
			self.media_update_time = self.show_update_time
		    else:
			self.media_update_time = self.present_show_playlist[self.next_track]['start_time']

	self.lock.release()
        return True

    def _play_media(self, media, offset):	
	if not obplayer.Sync.check_media(media):
	    return False

	self.play_lock.acquire()

	present_time = time.time()
	self.now_playing = media

	if self.present_show_playlist[self.present_track]['media_type'] == 'breakpoint':
	    obplayer.Log.log('stopping on breakpoint at position ' + str(self.present_track), 'scheduler')
	    if self.av_stop_time:
		obplayer.Player.stop('av')
	    self.av_stop_time = 0
	    self.paused = True
	    self.media_update_time = self.show_update_time		# set the next media update time to the end time of the current show
	    obplayer.Sync.now_playing_update(self.present_show['show_id'], self.present_show['end_time'], '', self.media_update_time, self.present_show['name'])

	else:
	    if offset < 0:
		offset = 0

	    #print "Playing " + media['title'] + " at " + str(offset)
	    obplayer.Player.play(media, offset, 'show')

	    # set media stop time. this is set separately since av and image streams are separated (allowing for audio+image playback)
	    if media['type'] == 'image':
		self.image_stop_time = present_time + media['duration'] - offset
	    else:
		self.av_stop_time = present_time + media['duration'] - offset

	    # tell the web app some new "now playing" information.
	    obplayer.Sync.now_playing_update(self.present_show['show_id'], self.present_show['end_time'], media['media_id'], self.media_update_time, self.present_show['name'])

	self.play_lock.release()
	return True
    """



    # next update (timestamp) - show update or media update. this will be when the scheduler will next trigger a 'play' command to the player
    # this is used by the fallback player to determine whether it's worthwhile playing some fallback media. if scheduler is about to do something, forget about it.
    # this also avoids race conditions between the fallback player and scheduler (though that would probably be pretty unlikely).
    def next_update(self):

        next_update = 0

        if self.media_update_time > 0 and (next_update == 0 or self.media_update_time < next_update):
            next_update = self.media_update_time

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

    def get_liveassist_groups(self):
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
	self.media_update_time = self.present_show.media_end_time

	self.lock.release()
	return True

    def play_group_item(self, group_num, group_item_num, seek):

	self.lock.acquire()

	self.present_show.play_group_item(group_num, group_item_num, seek)
	self.media_update_time = self.present_show.media_end_time

	self.lock.release()
	return True

    def play(self):
	self.lock.acquire()

	if self.present_show.is_paused():
	    self.present_show.unpause()
	    self.media_update_time = time.time()

	self.lock.release()
	return True

    def pause(self):
	self.lock.acquire()

	if not self.present_show.is_paused():
	    self.present_show.stop_current()
	    self.present_show.playlist.decrement()
	    self.present_show.pause()
	    self.media_update_time = self.show_update_time

	self.lock.release()
	return True

    def find_group_item_pos(self, group_id):
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

	now_playing = self.present_show.now_playing
	if now_playing != None:
	    data['artist'] = now_playing['artist']
	    data['title'] = now_playing['title']
	    data['position'] = time.time() - self.present_show.media_start_time

	    if 'group_id' in now_playing:
		data['mode'] = 'group'
		(data['group_num'], data['group_item_num']) = self.find_group_item_pos(now_playing['id'])
	    else:
		data['mode'] = 'playlist'
		data['track'] = self.present_show.playlist.pos
	else:
	    data['artist'] = ''
	    data['title'] = ''
	    data['position'] = 0
	    data['track'] = -1

	return data

    """
    def get_show_name(self):
	if self.present_show == None:
	    return '(no show playing)'
	return self.present_show['name']

    def get_show_end(self):
	if self.present_show == None:
	    return 0
	return self.present_show['end_time'];

    def get_current_playlist(self):
	playlist = [ ]
	if self.present_show_playlist != None:
	    for track in self.present_show_playlist:
		data = { 'track_id' : track['media_id'], 'artist' : track['artist'], 'title' : track['title'], 'duration' : track['duration'], 'media_type' : track['media_type'] }
		playlist.append(data)
	return playlist

    def get_liveassist_groups(self):
	groups = [ ]
	if self.present_show_groups != None:
	    for group in self.present_show_groups:
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
	self.media_update_time = self.present_show.media_end_time

	self.lock.release()
	return True

    def play_group_item(self, group_num, group_item_num, seek):

	if group_num < 0 or group_num >= len(self.present_show_groups):
	    return False
	group = self.present_show_groups[group_num]['items']

	if group_item_num < 0 or group_item_num >= len(group):
	    return False

	self.present_track = -1
	self.paused = True
	group[group_item_num]['start_time'] = time.time()

	if not self._play_media(group[group_item_num], group[group_item_num]['duration'] * (seek / 100)):
	    return False
	return True

    def play(self):
	self.lock.acquire()

	if self.present_show_playlist[self.next_track]['media_type'] == 'breakpoint':
	    self.next_track += 1
	self.media_update_time = time.time()
	self.paused = False
	self.present_show_playlist[self.next_track]['start_time'] = self.media_update_time
	for i in xrange(self.next_track + 1, len(self.present_show_playlist)):
	    if self.present_show_playlist[i - 1]['duration']:
		self.present_show_playlist[i]['start_time'] = self.present_show_playlist[i - 1]['start_time'] + self.present_show_playlist[i - 1]['duration']

	self.lock.release()
	return True

    def pause(self):
	self.lock.acquire()

	if self.av_stop_time > 0:
	    self.av_stop_time = 0
	    obplayer.Player.stop('av')
	    self.media_update_time = self.show_update_time

	self.lock.release()
	return True

    def get_now_playing(self):
	status = obplayer.Player.status()
	if status == False:
	    status = 'playing'
	else:
	    status = 'stopped'

	if self.now_playing != None:
	    artist = self.now_playing['artist']
	    title = self.now_playing['title']
	    position = time.time() - self.now_playing['start_time']
	else:
	    artist = ''
	    title = ''
	    position = 0

	return { 'status' : status, 'track' : self.present_track, 'artist' : artist, 'title' : title, 'position' : position }
    """


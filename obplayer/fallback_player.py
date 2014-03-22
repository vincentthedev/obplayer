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

import os
import magic
import time
import random

import pygst
pygst.require('0.10')
import gst
from gst.extend import discoverer


class ObFallbackPlayer:

    def __init__(self):
        self.media = []

        self.media_types = []
        self.image_types = []

        self.media_types.append('audio/x-flac')
        self.media_types.append('audio/flac')
        self.media_types.append('audio/mpeg')
        self.media_types.append('audio/ogg')

	# TODO we're always headless new so we never play images or video??
        #if obplayer.Main.headless == False:
        self.image_types.append('image/jpeg')
        self.image_types.append('image/png')
        self.image_types.append('image/svg+xml')
        self.media_types.append('application/ogg')
        self.media_types.append('video/ogg')
        self.media_types.append('video/x-msvideo')
        self.media_types.append('video/mp4')
        self.media_types.append('video/mpeg')

        self.play_index = 0
        self.image_duration = 15.0

        m = magic.open(magic.MAGIC_MIME)
        m.load()

        for (dirname, dirnames, filenames) in os.walk(obplayer.Config.setting('fallback_media')):
            for filename in filenames:
                filetype = m.file(os.path.join(dirname, filename)).split(';')[0]

                if filetype in self.media_types:
                    d = discoverer.Discoverer(obplayer.Config.setting('fallback_media') + '/' + filename)
                    d.connect('discovered', self.mediainfo_discovered, filename)
                    d.discover()

                if filetype in self.image_types:
                    self.media.append([filename, 'image', self.image_duration])

	#
	# shuffle the list. (should really just do this after all discoverers are complete...)
        random.shuffle(self.media)

    def mediainfo_discovered(self, d, is_media, filename):

        if is_media == False:
            return

        if d.is_video:
            media_type = 'video'
            duration = d.videolength / gst.MSECOND
        else:

            media_type = 'audio'
            duration = d.audiolength / gst.MSECOND

	# we discovered some more fallback media, add to our media list.
        self.media.append([filename, media_type, duration / 1000.0])

	# shuffle the list. (should really just do this after all discoverers are complete...)
        random.shuffle(self.media)

    # check to see whether we need to play some fallback media.
    def run(self):

	# early return if we're playing something already, have no fallback media, or scheduler is about to do something.
        if obplayer.Player.is_playing() or len(self.media) == 0 or obplayer.Scheduler.next_update() - time.time() < 5:
            return True

        if len(self.media) <= self.play_index:
            self.play_index = 0
            random.shuffle(self.media)  # shuffle again to create a new order for next time.

	# nothing playing? well let's play something.
        media = {'media_id': 0, 'artist': u'unknown', 'file_location': unicode(obplayer.Config.setting('fallback_media')), 'start_time': 0.0, 'title': unicode(self.media[self.play_index][0]),
                 'filename': unicode(self.media[self.play_index][0]), 'duration': self.media[self.play_index][2], 'order_num': 0, 'media_type': unicode(self.media[self.play_index][1]),
                 'type': unicode(self.media[self.play_index][1])}

        obplayer.Player.play(media, 0, 'fallback')

        self.play_index = self.play_index + 1

        return True



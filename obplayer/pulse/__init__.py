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

from __future__ import absolute_import 

import obplayer

pulse = None

def init():
    global pulsectl, pulse

    try:
        import pulsectl
    except ImportError:
        obplayer.Log.log("Missing python package: pulsectl. PulseAudio controls will be disabled.")
        return
    pulse = pulsectl.Pulse('obplayer-pulsectl')

def quit():
    pass


def sink_info(index):
    return pulse.sink_info(index)

def sink_list():
    return pulse.sink_list()

def sink_input_list():
    return pulse.sink_input_list()

def source_info(index):
    return pulse.source_info(index)

def source_list():
    return pulse.source_list()

def source_output_list():
    return pulse.source_output_list()

def change_volume(name, volume):
    if name.startswith('pulse_sink_'):
        appname = name[11:]
        for sink in pulse.sink_input_list():
            if sink.proplist['application.name'] == appname:
                pulse.volume_set_all_chans(sink, float(volume) / 100.0)
                return sink.volume.values[0] * 100
    elif name.startswith('pulse_source_'):
        appname = name[11:]
        for source in pulse.source_output_list():
            if source.proplist['application.name'] == appname:
                pulse.volume_set_all_chans(source, float(volume) / 100.0)
                return source.volume.values[0] * 100

def select_output(name, s_index):
    if name.startswith('pulse_sink_select_'):
        appname = name[18:]
        for sink in pulse.sink_input_list():
            if sink.proplist['application.name'] == appname:
                pulse.sink_input_move(sink.index, int(s_index))
    elif name.startswith('pulse_source_select_'):
        appname = name[20:]
        for source in pulse.source_output_list():
            if source.proplist['application.name'] == appname:
                pulse.source_output_move(source.index, int(s_index))


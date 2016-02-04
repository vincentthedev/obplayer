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

import apsw
import os
import os.path
import re
import traceback


class ObData (object):
    datadir = None

    @classmethod
    def set_datadir(cls, name):
        cls.datadir = os.path.expanduser(name)

        if os.access(cls.datadir, os.F_OK) == False:
            os.mkdir(cls.datadir)

        if os.access(cls.datadir + '/alerts', os.F_OK) == False:
            os.mkdir(cls.datadir + '/alerts')

        if os.access(cls.datadir + '/audiologs', os.F_OK) == False:
            os.mkdir(cls.datadir + '/audiologs')

        if os.access(cls.datadir + '/media', os.F_OK) == False:
            os.mkdir(cls.datadir + '/media')

        if os.access(cls.datadir + '/logs', os.F_OK) == False:
            os.mkdir(cls.datadir + '/logs')

        if os.access(cls.datadir + '/fallback_media', os.F_OK) == False:
            os.mkdir(cls.datadir + '/fallback_media')

    @classmethod
    def get_datadir(cls, subdir=None):
        if subdir:
            return os.path.join(cls.datadir, subdir)
        return cls.datadir


    def __init__(self):
        self.db = None

    def open_db(self, filename):
        return apsw.Connection(filename)

    def table_exists(self, table):
        for row in self.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name = ? UNION ALL SELECT name FROM sqlite_temp_master WHERE type IN ('table','view') AND name = ?", (table, table)):
            return True
        return False

    def empty_table(self, table):
        self.execute("DELETE from " + table)

    def execute(self, query, bindings=None):
        return self.db.cursor().execute(query, bindings)

    # run query, return dict.
    def query(self, query, bindings=None):
        cursor = self.db.cursor().execute(query, bindings)

        try:
            cols = cursor.getdescription()
        except apsw.ExecutionCompleteError:
            return [ ]

        return_array = [ ]
        for row in cursor:
            rowdata = { col[0] : row[i] for (i, col) in enumerate(cols) }
            return_array.append(rowdata)
        return return_array

    def escape(self, text):
        return text.replace("'", "''")

    def row_addedit(self, table, data):
        column_list = []
        value_list = []

        for (key, value) in data.items():
            column_list.append("'" + self.escape(str(key)) + "'")
            value_list.append("'" + self.escape(str(value)) + "'")

        # this is INSERT or REPLACE, so if we have (for example) ID set in data, then it will edit. Otherwise it will insert.
        # Other unique keys may cause replace (edit) so be careful.
        self.execute("INSERT or REPLACE into " + table + " ( " + ','.join(column_list) + " ) VALUES ( " + ','.join(value_list) + " )")
        return self.db.last_insert_rowid()



class ObConfigData (ObData):

    def __init__(self):
        ObData.__init__(self)

        self.headless = False
        self.args = None
        self.version = open('VERSION').read().strip()

        self.db = self.open_db(self.datadir + '/settings.db')

        if not self.table_exists('settings'):
            self.execute("CREATE TABLE settings (id INTEGER PRIMARY KEY, name TEXT, value TEXT, type TEXT)")
            self.execute("CREATE UNIQUE INDEX name_index on settings(name)")

        self.check_defaults()

        self.settings_cache = {}
        self.settings_type = {}

        rows = self.query("SELECT name,value,type FROM 'settings'")
        for row in rows:
            value = row['value']
            datatype = row['type']
            if datatype == 'int':
                value = int(value)
            elif datatype == 'bool':
                value = bool(int(value))
            else:
                value = str(value)
            self.settings_cache[row['name']] = value
            self.settings_type[row['name']] = datatype

        # keep track of settings as they have been edited.
        # they don't take effect until restart, but we want to keep track of them for subsequent edits.
        self.settings_edit_cache = self.settings_cache.copy()

        if not self.setting("video_out_enable"):
            self.headless = True

    def validate_settings(self, settings):
        for (setting_name, setting_value) in settings.items():
            error = self.validate_setting(setting_name, setting_value, settings)
            if error:
                return error
        return None

    def is_int(self, value):
        if re.match('^[0-9]+$', str(value)):
            return True
        else:
            return False

    def validate_setting(self, setting_name, setting_value, settings=None):

        # if we don't have a batch of settings we're checking, use our settings cache.
        if settings == None:
            settings = self.settings_cache

        try:
            self.settings_cache[setting_name]
        except:
            return 'One or more setting names were not valid.' + setting_name

        # disabled for now - this was locking the UI while waiting to timeout (if network problems)
        # try:
        # urllib.urlopen(settings['sync_url']);
        # except IOError:
        # error = 'The SYNC URL you have provided does not appear to be valid.';

        if setting_name == 'sync_device_id' and self.is_int(setting_value) == False:
            return 'The device ID is not valid.'

        if setting_name == 'sync_buffer' and self.is_int(setting_value) == False:
            return 'The sync buffer is not valid.'

        if setting_name == 'sync_showlock' and self.is_int(setting_value) == False:
            return 'The show lock is not valid.'

        if setting_name == 'sync_freq' and self.is_int(setting_value) == False:
            return 'The show sync frequency is not valid.'

        if setting_name == 'sync_freq_emerg' and self.is_int(setting_value) == False:
            return 'The priority sync frequency is not valid.'

        if setting_name == 'sync_freq_playlog' and self.is_int(setting_value) == False:
            return 'The playlog sync frequency is not valid.'

        if setting_name == 'sync_device_password' and setting_value == '':
            return 'A device password is required.'

        url_regex = re.compile(
                r'^(?:http|ftp)s?://' # http:// or https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
                r'localhost|' #localhost...
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
                r'(?::\d+)?' # optional port
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        if setting_name == 'sync_url' and setting_value and url_regex.match(setting_value) == None:
            return 'The sync URL does not appear to be valid.'

        if setting_name == 'alerts_naad_stream1' and url_regex.match(setting_value) == None:
            return 'The stream #1 URL does not appear to be valid.'

        if setting_name == 'alerts_naad_stream2' and url_regex.match(setting_value) == None:
            return 'The stream #2 URL does not appear to be valid.'

        if setting_name == 'alerts_naad_archive1' and url_regex.match(setting_value) == None:
            return 'The archive #1 URL does not appear to be valid.'

        if setting_name == 'alerts_naad_archive2' and url_regex.match(setting_value) == None:
            return 'The archive #2 URL does not appear to be valid.'

        if setting_name == 'alerts_trigger_serial_file' and setting_value and not os.path.exists(setting_value):
            return 'The RS-232 device filename does not appear to be valid.'

        geocode_regex = re.compile(r'^(|\d+(|,\d+)*)$', re.IGNORECASE)
        if setting_name == 'alerts_geocode' and geocode_regex.match(setting_value) == None:
            return 'Geocodes must be specified as a list of comma-separated numbers.'

        if setting_name == 'alerts_leadin_delay' and setting_value <= 0:
            return 'The alert lead-in delay must be 1s or greater.'

        if setting_name == 'alerts_leadout_delay' and setting_value <= 0:
            return 'The alert lead-out delay must be 1s or greater.'

        if setting_name == 'fallback_media' and os.access(setting_value, os.F_OK) == False:
            return 'The fallback media directory you have specified does not exist.'

        if setting_name == 'local_media' and settings['sync_mode'] != 'remote' and setting_value != '' and os.access(setting_value, os.F_OK) == False:
            return 'The local media directory you have specified does not exist.'

        if setting_name == 'http_admin_port' and self.is_int(setting_value) == False:
            return 'The web admin port is not valid.'

        if setting_name == 'http_admin_secure' and settings['http_admin_secure'] and os.access(settings['http_admin_sslcert'], os.F_OK) == False:
            return 'To use the web admin with SSL, a valid certiciate file is required.'

        if setting_name == 'live_assist_port' and settings['live_assist_enable'] and settings['live_assist_port'] == settings['http_admin_port']:
            return 'Live Assist and HTTP Admin cannot use the same port.'

        lat_regex = re.compile(r'^[-+]?([1-8]?\d(\.\d+)?|90(\.0+)?)$')
        lng_regex = re.compile(r'[-+]?(180(\.0+)?|((1[0-7]\d)|([1-9]?\d))(\.\d+)?)$')
        if setting_name == 'device_latitude' and lat_regex.match(setting_value) == None:
             return 'Invalid latitdue coordinate.'
        if setting_name == 'device_longitude' and lng_regex.match(setting_value) == None:
             return 'Invalid longitude coordinate.'

        return None

    def set(self, setting_name, setting_value):
        settings = {}
        settings[setting_name] = setting_value
        self.save_settings(settings)

    # make sure we have all our required settings. if not, add setting with default value.
    def check_defaults(self):
        self.add_setting('audio_out_mode', 'auto', 'text')
        self.add_setting('audio_out_alsa_device', 'default', 'text')
        self.add_setting('audio_out_jack_name', '', 'text')
        self.add_setting('audio_out_shout2send_ip', '127.0.0.1', 'text')
        self.add_setting('audio_out_shout2send_port', '8000', 'int')
        self.add_setting('audio_out_shout2send_mount', 'stream', 'text')
        self.add_setting('audio_out_shout2send_password', 'hackme', 'text')
        self.add_setting('audio_out_visualization', '1', 'bool')
        self.add_setting('gst_init_callback', '', 'text')

        self.add_setting('audio_in_enable', '0', 'bool')
        self.add_setting('audio_in_mode', 'auto', 'text')
        self.add_setting('audio_in_alsa_device', 'default', 'text')
        self.add_setting('audio_in_jack_name', '', 'text')

        self.add_setting('audiolog_enable', '0', 'bool')

        self.add_setting('video_out_enable', '1', 'bool')
        self.add_setting('video_out_mode', 'auto', 'text')

        self.add_setting('images_transitions_enable', '1', 'bool')
        self.add_setting('images_width', '640', 'int')
        self.add_setting('images_height', '480', 'int')
        self.add_setting('images_framerate', '15', 'int')

        self.add_setting('overlay_enable', '0', 'bool')

        self.add_setting('streamer_enable', '0', 'bool')
        self.add_setting('streamer_audio_in_mode', 'auto', 'text')
        self.add_setting('streamer_audio_in_alsa_device', 'default', 'text')
        self.add_setting('streamer_audio_in_jack_name', '', 'text')
        self.add_setting('streamer_icecast_ip', '127.0.0.1', 'text')
        self.add_setting('streamer_icecast_port', '8000', 'int')
        self.add_setting('streamer_icecast_mount', 'stream', 'text')
        self.add_setting('streamer_icecast_password', 'hackme', 'text')
        self.add_setting('streamer_icecast_streamname', '', 'text')
        self.add_setting('streamer_icecast_description', '', 'text')
        self.add_setting('streamer_icecast_url', '', 'text')
        self.add_setting('streamer_icecast_public', '1', 'bool')
        self.add_setting('streamer_play_on_startup', '1', 'bool')

        self.add_setting('scheduler_enable', '1', 'bool')
        self.add_setting('sync_device_id', '1', 'int')
        self.add_setting('sync_device_password', 'password', 'text')
        self.add_setting('sync_url', 'https://demo.openbroadcaster.pro/remote.php', 'text')
        self.add_setting('sync_buffer', '24', 'int')
        self.add_setting('sync_showlock', '20', 'int')
        self.add_setting('sync_playlog_enable', '1', 'bool')
        self.add_setting('sync_freq', '2', 'int')
        self.add_setting('sync_freq_emerg', '1', 'int')
        self.add_setting('sync_freq_log', '3', 'int')
        self.add_setting('sync_mode', 'remote', 'text')
        self.add_setting('sync_copy_media_to_backup', '0', 'bool')
        self.add_setting('remote_media', self.datadir + '/media', 'text')
        self.add_setting('local_media', '', 'text')

        self.add_setting('http_admin_port', '23233', 'int')
        self.add_setting('http_admin_username', 'admin', 'text')
        self.add_setting('http_admin_password', 'admin', 'text')
        self.add_setting('http_readonly_username', 'user', 'text')
        self.add_setting('http_readonly_password', 'user', 'text')
        self.add_setting('http_readonly_allow_restart', '1', 'bool')
        self.add_setting('http_admin_secure', '0', 'bool')
        self.add_setting('http_admin_sslcert', '', 'text')
        self.add_setting('http_admin_title', 'OpenBroadcaster Player Dashboard', 'text')

        self.add_setting('http_show_sync', '1', 'bool')
        self.add_setting('http_show_streaming', '1', 'bool')
        self.add_setting('http_show_alerts', '1', 'bool')
        self.add_setting('http_show_location', '1', 'bool')
        self.add_setting('http_show_liveassist', '1', 'bool')

        self.add_setting('live_assist_enable', '0', 'bool')
        self.add_setting('live_assist_port', '23456', 'int')
        self.add_setting('live_assist_mic_enable', '0', 'bool')
        self.add_setting('live_assist_mic_mode', 'auto', 'text')
        self.add_setting('live_assist_mic_alsa_device', 'default', 'text')
        self.add_setting('live_assist_mic_jack_name', '', 'text')
        self.add_setting('live_assist_monitor_mode', 'auto', 'text')
        self.add_setting('live_assist_monitor_alsa_device', 'default', 'text')
        self.add_setting('live_assist_monitor_jack_name', '', 'text')

        self.add_setting('alerts_enable', '0', 'bool')
        self.add_setting('alerts_language_primary', 'english', 'text')
        self.add_setting('alerts_language_secondary', 'french', 'text')
        self.add_setting('alerts_voice_primary', 'en', 'text')
        self.add_setting('alerts_voice_secondary', 'fr', 'text')
        self.add_setting('alerts_geocode', '59', 'text')
        self.add_setting('alerts_repeat_interval', '30', 'int')
        self.add_setting('alerts_repeat_times', '0', 'int')
        self.add_setting('alerts_leadin_delay', '1', 'int')
        self.add_setting('alerts_leadout_delay', '1', 'int')
        self.add_setting('alerts_naad_stream1', "http://streaming1.naad-adna.pelmorex.com:8080", 'text')
        self.add_setting('alerts_naad_stream2', "http://streaming2.naad-adna.pelmorex.com:8080", 'text')
        self.add_setting('alerts_naad_archive1', "http://capcp1.naad-adna.pelmorex.com", 'text')
        self.add_setting('alerts_naad_archive2', "http://capcp2.naad-adna.pelmorex.com", 'text')
        self.add_setting('alerts_truncate', '0', 'bool')
        self.add_setting('alerts_play_moderates', '1', 'bool')
        self.add_setting('alerts_play_tests', '0', 'bool')
        self.add_setting('alerts_trigger_serial', '0', 'bool')
        self.add_setting('alerts_trigger_serial_file', '', 'text')
        self.add_setting('alerts_trigger_streamer', '0', 'bool')
        self.add_setting('alerts_purge_files', '1', 'bool')

        self.add_setting('fallback_enable', '1', 'bool')
        self.add_setting('fallback_media', self.datadir + '/fallback_media', 'text')

        self.add_setting('testsignal_enable', '1', 'bool')

        self.add_setting('enable_location', '1', 'bool')
        self.add_setting('device_longitude','-134.18537', 'decimal')
        self.add_setting('device_latitude','60.27434', 'decimal')

    def add_setting(self, name, value, datatype=None):

        check_setting = self.query("SELECT name,value,type from 'settings' WHERE name = '" + self.escape(name) + "'")
        if len(check_setting):
            return

        data = {}
        data['name'] = name
        data['value'] = value

        if datatype != None:
            data['type'] = datatype

        self.row_addedit('settings', data)

    def setting(self, name, use_edit_cache=False):
        settings = self.settings_edit_cache if use_edit_cache else self.settings_cache
        try:
            return settings[name]
        except:
            return False

    # save our settings into the database. update settings_edit_cache to handle subsequent edits.
    def save_settings(self, settings):

        for (name, value) in settings.items():
            self.query('UPDATE settings set value="' + self.escape(str(value)) + '" where name="' + self.escape(name) + '"')

            dataType = self.settings_type[name]
            if dataType == 'int':
                self.settings_edit_cache[name] = int(value)
            elif dataType == 'bool':
                self.settings_edit_cache[name] = bool(int(value))
            else:
                self.settings_edit_cache[name] = str(value)



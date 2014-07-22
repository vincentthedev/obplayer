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

import apsw
import string
import time
import os
import re


class ObData:

    @staticmethod
    def get_datadir():
	# if ~/.openbroadcaster doesn't exist, we need to create it.
        datadir = os.path.expanduser('~/.openbroadcaster')

        if os.access(datadir, os.F_OK) == False:
            os.mkdir(datadir)

        if os.access(datadir + '/media', os.F_OK) == False:
            os.mkdir(datadir + '/media')

        if os.access(datadir + '/logs', os.F_OK) == False:
            os.mkdir(datadir + '/logs')

        if os.access(datadir + '/fallback_media', os.F_OK) == False:
            os.mkdir(datadir + '/fallback_media')
	return datadir

    def table_exists(self, name):
        for row in self.cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name = '" + name + "' UNION ALL SELECT name FROM sqlite_temp_master WHERE type IN ('table','view') AND name = '" + name + "'"):
            return True
        return False

    def empty_table(self, name):
        self.cur.execute('DELETE from ' + name)

    def escape(self, what):
        return_what = string.replace(what, "'", "''")
        return return_what

    def row_addedit(self, table, data):

        column_list = []
        value_list = []

        for (key, value) in data.iteritems():
            column_list.append("'" + self.escape(str(key)) + "'")
            value_list.append("'" + self.escape(str(value)) + "'")

        column_list_string = ','.join(column_list)
        value_list_string = ','.join(value_list)

	# this is INSERT or REPLACE, so if we have (for example) ID set in data, then it will edit. Otherwise it will insert.
	# Other unique keys may cause replace (edit) so be careful.
        self.cur.execute('INSERT or REPLACE into ' + table + ' ( ' + column_list_string + ' ) VALUES ( ' + value_list_string + ' )')
        return self.con.last_insert_rowid()

    #
    # run query, return dict.
    def query(self, query, thread='main'):

        if thread == 'sync':
            use_cur = self.cur_sync
        elif thread == 'sync_show':

            use_cur = self.cur_sync_show
        elif thread == 'sync_emerg':

            use_cur = self.cur_sync_emerg
        else:

            use_cur = self.cur

        return_array = []

        cols = None

        for row in self.cur.execute(query):

            if cols == None:
                cols = self.cur.getdescription()

            count = 0
            rowdata = {}
            for col in cols:
                rowdata[col[0]] = row[count]
                count = count + 1

            return_array.append(rowdata)

        return return_array


class ObConfigData(ObData):

    def __init__(self):

	self.datadir = ObData.get_datadir()
        self.con = apsw.Connection(self.datadir + '/settings.db')
        self.cur = self.con.cursor()

        if self.table_exists('settings') != True:
            self.create_table()

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

    def validateSettings(self, settings):

        for (settingName, settingValue) in settings.iteritems():
            error = self.validateSetting(settingName, settingValue, settings)
            if error:
                return error

        return None

    def is_int(self, value):
        if re.match('^[0-9]+$', str(value)):
            return True
        else:
            return False

    def validateSetting(self, settingName, settingValue, settings=None):

	# if we don't have a batch of settings we're checking, use our settings cache.
        if settings == None:
            settings = self.settings_cache

        try:
            self.settings_cache[settingName]
        except:
            error = 'One or more setting names were not valid.' + settingName
            return error

	# disabled for now - this was locking the UI while waiting to timeout (if network problems)
	# try:
	# urllib.urlopen(settings['sync_url']);
	# except IOError:
	# error = 'The SYNC URL you have provided does not appear to be valid.';

        if settingName == 'device_id' and self.is_int(settingValue) == False:
            return 'The device ID is not valid.'

        if settingName == 'buffer' and self.is_int(settingValue) == False:
            return 'The sync buffer is not valid.'

        if settingName == 'showlock' and self.is_int(settingValue) == False:
            return 'The show lock is not valid.'

        if settingName == 'syncfreq' and self.is_int(settingValue) == False:
            return 'The show sync frequency is not valid.'

        if settingName == 'syncfreq_emerg' and self.is_int(settingValue) == False:
            return 'The emergency sync frequency is not valid.'

        if settingName == 'syncfreq_playlog' and self.is_int(settingValue) == False:
            return 'The playlog sync frequency is not valid.'

        if settingName == 'http_admin_port' and self.is_int(settingValue) == False:
            return 'The web admin port is not valid.'

        if settingName == 'device_password' and settingValue == '':
            return 'A device password is required.'

	url_regex = re.compile(
		r'^(?:http|ftp)s?://' # http:// or https://
		r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
		r'localhost|' #localhost...
		r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
		r'(?::\d+)?' # optional port
		r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        if settingName == 'sync_url' and url_regex.match(settingValue) == None:
            return 'The sync URL does not appear to be valid.'

        if settingName == 'fallback_media' and os.access(settingValue, os.F_OK) == False:
            return 'The fallback media directory you have specified does not exist.'

        if settingName == 'local_media' and settings['syncmode'] != 'remote' and os.access(settingValue, os.F_OK) == False:
            return 'The local media (approved) directory you have specified does not exist.'

        if settingName == 'local_archive' and settings['syncmode'] != 'remote' and os.access(settingValue, os.F_OK) == False:
            return 'The local media (archived) directory you have specified does not exist.'

        if settingName == 'local_uploads' and settings['syncmode'] != 'remote' and os.access(settingValue, os.F_OK) == False:
            return 'The local media (unapproved) directory you have specified does not exist.'

        if settingName == 'http_admin_enable' and settingValue == 1 and (settings['http_admin_username'] == '' or settings['http_admin_password'] == ''):
            return 'To use the web admin, a username and password are required.'

        if settingName == 'http_admin_secure' and settings['http_admin_enable'] and settings['http_admin_secure'] and os.access(settings['http_admin_sslcert'], os.F_OK) == False:
            return 'To use the web admin with SSL, a valid certiciate file is required.'

	if settingName == 'live_assist_port' and settings['http_admin_enable'] and settings['live_assist_enable'] and settings['live_assist_port'] == settings['http_admin_port']:
	    return 'Live Assist and HTTP Admin cannot use the same port.'

        return None

    def set(self, settingName, settingValue):

        settings = {}
        settings[settingName] = settingValue
        self.save_settings(settings)

    def create_table(self):
        self.cur.execute('CREATE TABLE settings (id INTEGER PRIMARY KEY, name TEXT, value TEXT, type TEXT)')
        self.cur.execute('CREATE UNIQUE INDEX name_index on settings(name)')

    # make sure we have all our required settings. if not, add setting with default value.
    def check_defaults(self):
        self.add_setting('device_id', '1', 'int')
        self.add_setting('device_password', 'password', 'text')
        self.add_setting('sync_url', 'http://demo.openbroadcaster.com/remote.php', 'text')
        self.add_setting('buffer', '24', 'int')
        self.add_setting('remote_media', self.datadir + '/media', 'text')
        self.add_setting('showlock', '20', 'int')
        self.add_setting('syncfreq', '2', 'int')
        self.add_setting('syncfreq_emerg', '1', 'int')
        self.add_setting('syncfreq_log', '3', 'int')
        self.add_setting('syncmode', 'remote', 'text')
        self.add_setting('local_archive', '', 'text')
        self.add_setting('local_uploads', '', 'text')
        self.add_setting('local_media', '', 'text')
        self.add_setting('copy_media_to_backup', '0', 'bool')
        self.add_setting('audiovis', '1', 'bool')
        self.add_setting('audio_output', 'auto', 'text')
        self.add_setting('alsa_device', 'default', 'text')
        self.add_setting('gst_init_callback', '', 'text')
        self.add_setting('http_admin_enable', '1', 'bool')
        self.add_setting('http_admin_secure', '0', 'bool')
        self.add_setting('http_admin_sslcert', '', 'text')
        self.add_setting('http_admin_port', '23233', 'int')
        self.add_setting('http_admin_username', 'admin', 'text')
        self.add_setting('http_admin_password', 'admin', 'text')
        self.add_setting('fallback_media', self.datadir + '/fallback_media', 'text')
	self.add_setting('live_assist_enable', '0', 'bool')
	self.add_setting('live_assist_port', '23456', 'int')

    def add_setting(self, name, value, datatype=None):

	check_setting = self.query('SELECT name,value,type from "settings" WHERE name = "' + self.escape(name) + '"')
	if len(check_setting):
	    return

        data = {}
        data['name'] = name
        data['value'] = value

        if datatype != None:
            data['type'] = datatype

        self.row_addedit('settings', data)

    def setting(self, name, use_edit_cache=False):
        if use_edit_cache:
            try:
                return self.settings_edit_cache[name]
            except:
                return False

        try:
            return self.settings_cache[name]
        except:
            return False

    # save our settings into the database. update settings_edit_cache to handle subsequent edits.
    def save_settings(self, settings):

        for (name, value) in settings.iteritems():
            self.query('UPDATE settings set value="' + self.escape(str(value)) + '" where name="' + self.escape(name) + '"')

            dataType = self.settings_type[name]
            if dataType == 'int':
                self.settings_edit_cache[name] = int(value)
            elif dataType == 'bool':
                self.settings_edit_cache[name] = bool(int(value))
            else:
                self.settings_edit_cache[name] = str(value)


class ObRemoteData(ObData):

    def __init__(self):

	self.datadir = ObData.get_datadir()

	# our main database, stored in memory.
        self.con = apsw.Connection(':memory:')

	# load our backup database from file. check integrity.  if the database doesn't exist, it will be created/empty - no problem, tables are checked/created below.
        backup_icheck = []
        backup = apsw.Connection(self.datadir + '/data.db')
        backup_cur = backup.cursor()
        for row in backup_cur.execute('PRAGMA integrity_check'):
            backup_icheck.extend(row)

        if '\n'.join(backup_icheck) != 'ok':
            obplayer.Log.log('backup file bad, ignoring.', 'data')
        else:

            obplayer.Log.log('restoring database from file', 'data')
            with self.con.backup('main', backup, 'main') as backup:
                backup.step()
            obplayer.Log.log('done restoring database', 'data')

        backup.close()

	# used by sync thread. (need separate cursor for each thread to use)
        self.cur = self.con.cursor()
        self.cur_sync_show = self.con.cursor()
        self.cur_sync_emerg = self.con.cursor()
        self.cur_sync_media_required = self.con.cursor()

        if self.table_exists('shows') != True:
            obplayer.Log.log('shows table not found, creating', 'data')
            self.shows_create_table()

        if self.table_exists('shows_media') != True:
            obplayer.Log.log('media table not found, creating', 'data')
            self.shows_media_create_table()

        if self.table_exists('emergency_broadcasts') != True:
            obplayer.Log.log('emergency broadcast table not found, creating', 'data')
            self.emergency_broadcasts_create_table()

        if self.table_exists('groups') != True:
            obplayer.Log.log('liveassist groups table not found, creating', 'data')
            self.shows_groups_create_table()

        if self.table_exists('group_items') != True:
            obplayer.Log.log('liveassist group items table not found, creating', 'data')
            self.shows_group_items_create_table()

        self.emergency_broadcasts = False

    def backup(self):
        obplayer.Log.log('backup database to disk', 'data')
        backupcon = apsw.Connection(self.datadir + '/data.db')

        with backupcon.backup('main', self.con, 'main') as backup:
            backup.step()

        backupcon.close()
        obplayer.Log.log('done backing up', 'data')

    def shows_create_table(self):
        self.cur.execute('CREATE TABLE shows (id INTEGER PRIMARY KEY, show_id INTEGER, name TEXT, type TEXT, description TEXT, datetime NUMERIC UNIQUE, duration NUMERIC, last_updated NUMERIC)')
        self.cur.execute('CREATE UNIQUE INDEX datetime_index on shows (datetime)')

    def shows_media_create_table(self):
        self.cur.execute('CREATE TABLE shows_media (id INTEGER PRIMARY KEY, local_show_id INTEGER, media_id INTEGER, show_id INTEGER, order_num INTEGER, filename TEXT, artist TEXT, title TEXT, offset NUMERIC, duration NUMERIC, media_type TEXT, file_hash TEXT, file_size INT, file_location TEXT, approved INT, archived INT)')
        self.cur.execute('CREATE INDEX local_show_id_index on shows_media (local_show_id)')

    def emergency_broadcasts_create_table(self):
        self.cur.execute('CREATE TABLE emergency_broadcasts (id INTEGER PRIMARY KEY, start_timestamp INTEGER, end_timestamp INTEGER, frequency INTEGER, filename TEXT, artist TEXT, title TEXT, duration NUMERIC, media_type TEXT, media_id INTEGER, file_hash TEXT, file_size INT, file_location TEXT, approved INT, archived INT)')

    def shows_groups_create_table(self):
	self.cur.execute('CREATE TABLE groups (id INTEGER PRIMARY KEY, local_show_id INTEGER, name TEXT)')
        self.cur.execute('CREATE INDEX groups_local_show_id_index on groups (local_show_id)')

    def shows_group_items_create_table(self):
        self.cur.execute('CREATE TABLE group_items (id INTEGER PRIMARY KEY, group_id INTEGER, media_id INTEGER, order_num INTEGER, filename TEXT, artist TEXT, title TEXT, duration NUMERIC, media_type TEXT, file_hash TEXT, file_size INT, file_location TEXT, approved INT, archived INT)')
        self.cur.execute('CREATE INDEX group_id_index on group_items (group_id)')

    #
    # Given show_id, name, description, datetime, and duration, add entry to show database.  If entry exists, edit if required.
    # Return false if edit not required.  Return lastrowid otherwise.
    #
    def show_addedit(self, show_id, name, show_type, description, datetime, duration, last_updated):

        name = self.escape(name)
        description = self.escape(description)

	# determine whether there is already a show in this slot.
        rows = self.cur_sync_show.execute("SELECT show_id,last_updated,id,duration from shows where datetime='" + str(datetime) + "'")
        for row in rows:

	    # if update not required, return false.
            if int(row[0]) == int(show_id) and int(row[1]) == int(last_updated) and float(row[3]) == float(duration):
                return False
            else:
		# if we have a match, but update is required, delete entry + associated media.
                self.cur_sync_show.execute("DELETE from shows_media where local_show_id='" + str(row[2]) + "'")

	# now add the show... (media not added here, but added by sync script)
        self.cur_sync_show.execute("INSERT or REPLACE into shows VALUES (null, '" + show_id + "','" + name + "','" + show_type + "','" + description + "','" + str(datetime) + "','" + duration + "','" + str(last_updated)
                                   + "')")
        return self.con.last_insert_rowid()

    #
    #
    # Given a list of timestamps, delete all shows with a timestamp not in this list.  (Clean out shows that have been removed).
    # DO NOT remove shows within starting within 'ignore_limit' (since these fall within 'showlock').
    #
    def show_remove_deleted(self, timestamps, ignore_limit):

        seperator = ','

	# convert our timestamp list to string values.
        timestamps_string = []
        for timestamp in timestamps:
            timestamps_string.append(str(timestamp))

        not_in_string = seperator.join(timestamps_string)

        rows = self.query('SELECT id from shows WHERE datetime NOT IN (' + not_in_string + ') and datetime > ' + str(ignore_limit), 'sync_show')

        for row in rows:
            self.cur_sync_show.execute('DELETE from shows where id=' + str(row['id']))
            self.cur_sync_show.execute('DELETE from shows_media where local_show_id=' + str(row['id']))

        return True

    # remove shows that are over, and associated media.
    def show_remove_old(self):
        rows = self.query('SELECT id from shows WHERE (datetime+duration) < ' + str(time.time()), 'sync_show')

        for row in rows:
            self.cur_sync_show.execute('DELETE from shows where id=' + str(row['id']))
            self.cur_sync_show.execute('DELETE from shows_media where local_show_id=' + str(row['id']))

        return True

    #
    #
    #
    # Given broadcast_id, start time, end time ('' for none), frequency, artist, title, filename, media_id, duration, and media type, update emergency broadcast database.
    # If row with broadcast_id exists, it will be updated.  Otherwise row will be added.
    #
    def emergency_broadcast_addedit(
        self,
        broadcast_id,
        start,
        end,
        frequency,
        artist,
        title,
        filename,
        media_id,
        duration,
        media_type,
        file_hash,
        file_size,
        file_location,
        approved,
        archived,
        ):

        broadcast_id = self.escape(broadcast_id)
        start = self.escape(start)
        end = self.escape(end)
        frequency = self.escape(frequency)
        artist = self.escape(artist)
        title = self.escape(title)
        filename = self.escape(filename)
        media_id = self.escape(media_id)
        duration = self.escape(duration)
        media_type = self.escape(media_type)

        query = "INSERT OR REPLACE into emergency_broadcasts VALUES ('" + broadcast_id + "', '" + start + "','" + end + "','" + frequency + "','" + filename + "','" + artist + "','" + title + "','" \
            + duration + "','" + media_type + "','" + media_id + "','" + file_hash + "','" + file_size + "','" + file_location + "','" + approved + "','" + archived + "')"

        self.cur_sync_emerg.execute(query)
        return self.con.last_insert_rowid()

    #
    #
    # Given a list of emergency broadcast IDs, remove anything that isn't in there. (they are no longer needed.)
    #
    def emergency_broadcast_remove_deleted(self, id_list):

        seperator = ','

	# convert our timestamp list to string values.
        id_list_string = []
        for broadcast_id in id_list:
            id_list_string.append(str(broadcast_id))

        not_in_string = seperator.join(id_list_string)

        self.cur_sync_emerg.execute('DELETE from emergency_broadcasts WHERE id NOT IN (' + not_in_string + ')')

        return True

    #
    # Given media id, show id, order number, filename, artist, title, duration, and media type, add show media.
    #
    def show_media_add(self, local_show_id, show_id, media_item):

        media_item['filename'] = self.escape(media_item['filename'])
        media_item['artist'] = self.escape(media_item['artist'])
        media_item['title'] = self.escape(media_item['title'])
        media_item['file_hash'] = self.escape(media_item['file_hash'])

        query = "INSERT into shows_media VALUES (null, '" + str(local_show_id) + "', '" + media_item['id'] + "','" + show_id + "','" + media_item['order'] + "','" + media_item['filename'] + "','" \
            + media_item['artist'] + "','" + media_item['title'] + "','" + media_item['offset'] + "','" + media_item['duration'] + "','" + media_item['type'] + "','" + media_item['file_hash'] + "','" \
            + media_item['file_size'] + "','" + media_item['file_location'] + "','" + media_item['approved'] + "','" + media_item['archived'] + "')"
        self.cur_sync_show.execute(query)
        return self.con.last_insert_rowid()

    def group_remove_old(self, local_show_id):
        rows = self.query('SELECT id from groups WHERE local_show_id=' + str(local_show_id))
	for row in rows:
            self.cur_sync_show.execute('DELETE from group_items where group_id=' + str(row['id']))
            self.cur_sync_show.execute('DELETE from groups where id=' + str(row['id']))

    def group_add(self, local_show_id, name):

	query = "INSERT into groups VALUES (null, '" + str(local_show_id) + "','" + name + "')"
        self.cur_sync_show.execute(query)
        return self.con.last_insert_rowid()

    def group_item_add(self, group_id, media_item):

        media_item['filename'] = self.escape(media_item['filename'])
        media_item['artist'] = self.escape(media_item['artist'])
        media_item['title'] = self.escape(media_item['title'])
        media_item['file_hash'] = self.escape(media_item['file_hash'])

        query = "INSERT into group_items VALUES (null, '" + str(group_id) + "', '" + media_item['id'] + "','" + media_item['order'] + "','" + media_item['filename'] + "','" \
            + media_item['artist'] + "','" + media_item['title'] + "','" + media_item['duration'] + "','" + media_item['type'] + "','" + media_item['file_hash'] + "','" \
            + media_item['file_size'] + "','" + media_item['file_location'] + "','" + media_item['approved'] + "','" + media_item['archived'] + "')"
        self.cur_sync_show.execute(query)
        return self.con.last_insert_rowid()

    #
    #
    # Return a dictionary (associate array) of format returned_list[filename]=media_id for all media required by remote.
    # This is based on the entries in shows_media and emergency_broadcasts.
    #
    def media_required(self):
        query = 'SELECT filename,media_id,file_hash,file_location,approved,archived,file_size,media_type from shows_media GROUP by media_id'
        rows = self.cur_sync_media_required.execute(query)

        media_list = {}

        for row in rows:
	    media_row = self.get_media_from_row(row)
            media_list[media_row['filename']] = media_row

        query = 'SELECT filename,media_id,file_hash,file_location,approved,archived,file_size,media_type from emergency_broadcasts GROUP by media_id'
        rows = self.cur_sync_media_required.execute(query)

        for row in rows:
	    media_row = self.get_media_from_row(row)
            media_list[media_row['filename']] = media_row

        query = 'SELECT filename,media_id,file_hash,file_location,approved,archived,file_size,media_type from group_items GROUP by media_id'
        rows = self.cur_sync_media_required.execute(query)

        for row in rows:
	    media_row = self.get_media_from_row(row)
            media_list[media_row['filename']] = media_row

        return media_list

    @staticmethod
    def get_media_from_row(row):
	media_row = {}
	media_row['filename'] = row[0]
	media_row['media_id'] = row[1]
	media_row['file_hash'] = row[2]
	media_row['file_size'] = row[6]
	media_row['file_location'] = row[3]
	media_row['approved'] = row[4]
	media_row['archived'] = row[5]
	media_row['media_type'] = row[7]
	return media_row

    #
    #
    # Given the present time, return the present show (associate array/dictionary).
    #
    def get_present_show(self, present_timestamp):

        rows = self.query('SELECT * from shows where datetime <= ' + str(present_timestamp) + ' order by datetime desc limit 1')

        for (rindex, row) in enumerate(rows):

            show_start_timestamp = row['datetime']
            show_end_timestamp = show_start_timestamp + float(row['duration'])

            if present_timestamp < show_end_timestamp:
                rows[rindex]['start_time'] = show_start_timestamp
                rows[rindex]['end_time'] = show_end_timestamp
                return rows[rindex]

        return None

    #
    # Given the present time, return the next show.  Returned as associative array/dictionary.
    #
    def get_next_show_times(self, present_timestamp):

        rows = self.query('SELECT datetime,duration from shows where datetime > ' + str(present_timestamp) + ' order by datetime limit 1')

        for (rindex, row) in enumerate(rows):

            show_start_timestamp = row['datetime']
            show_end_timestamp = show_start_timestamp + float(row['duration'])

            if present_timestamp < show_end_timestamp:
                rows[rindex]['start_time'] = show_start_timestamp
                rows[rindex]['end_time'] = show_end_timestamp
                return rows[rindex]

        return None

    def load_groups(self, local_show_id):

        group_rows = self.query('SELECT * from groups WHERE local_show_id=' + str(local_show_id))

	groups = [ ]
	for group_row in group_rows:
	    item_rows = self.query('SELECT * from group_items WHERE group_id=' + str(group_row['id']))

	    group_items = [ ]
	    for item_row in item_rows:
		group_items.append(item_row)

	    groups.append({ 'id' : group_row['id'], 'local_show_id' : group_row['local_show_id'], 'name' : group_row['name'], 'items' : group_items })

	return groups

    #
    #
    # Get a list of the show media given a show id. Returned as associative array/dictionary.
    #
    def get_show_media(self, local_show_id):
        query = "SELECT filename,order_num,duration,media_type,artist,title,media_id,file_location,offset,file_size from shows_media where local_show_id='" + str(local_show_id) + "' order by offset"
        rows = self.cur.execute(query)

        media = []

        for row in rows:
            media_data = {}
            media_data['filename'] = row[0]
            media_data['order_num'] = row[1]
            media_data['offset'] = row[8]
            media_data['duration'] = row[2]
            media_data['type'] = row[3]
            media_data['artist'] = row[4]
            media_data['title'] = row[5]
            media_data['media_id'] = row[6]
            media_data['file_location'] = row[7]
            media_data['media_type'] = row[3]
            media_data['file_size'] = row[9]

            media.append(media_data)

        if len(media) <= 0:
            return None
        else:
            return media

    #
    #
    # Get all present emergency broadcasts.  Returned as associative array/dictionary.
    #
    def get_emergency_broadcasts(self):

	# TODO previous broadcast array is used to get the next_play play data.
	# will need to record id into broadcast array index to make this easier...

        present_time = time.time()

        query = 'SELECT id,start_timestamp,end_timestamp,frequency,artist,title,filename,duration,media_type,media_id,file_location,file_size from emergency_broadcasts'
        rows = self.cur_sync_emerg.execute(query)

        broadcasts = {}

        has_broadcasts = False

        for row in rows:
            data = {}
            data['id'] = row[0]
            data['start'] = row[1]
            data['end'] = row[2]
            data['frequency'] = row[3]
            data['artist'] = row[4]
            data['title'] = row[5]
            data['filename'] = row[6]
            data['duration'] = row[7]
            data['type'] = row[8]
            data['media_type'] = row[8]
            data['media_id'] = row[9]
            data['file_location'] = row[10]
            data['file_size'] = row[11]

            data['next_play'] = False

	    # try to get next play time based on previous play time.
            if self.emergency_broadcasts != False:

                former_data = self.emergency_broadcasts.get(str(data['id']), None)

                if former_data != None:

                    data['last_play'] = self.emergency_broadcasts[str(data['id'])]['last_play']
                    check_next_play = data['last_play'] + data['frequency']

                    if check_next_play >= present_time:
                        data['next_play'] = check_next_play

	    # if we don't have a next play time, get it in a more usual way.
            if data['next_play'] == False:
                if data['start'] < present_time:
                    data['next_play'] = present_time
                else:
                    data['next_play'] = data['start']

            has_broadcasts = True

            broadcasts[str(data['id'])] = data

        if has_broadcasts == False:
            self.emergency_broadcasts = False
            return False
        else:

            self.emergency_broadcasts = broadcasts
            return broadcasts


class ObPlaylogData(ObData):

    def __init__(self):

	self.datadir = ObData.get_datadir()

        self.con = apsw.Connection(self.datadir + '/playlog.db')
        self.cur = self.con.cursor()

	# used by sync thread. (need separate cursor for each thread to use)
        self.cur_sync = self.con.cursor()

        if self.table_exists('playlog') != True:
            self.playlog_create_table()

    def playlog_create_table(self):
        self.cur.execute('CREATE TABLE playlog (id INTEGER PRIMARY KEY, media_id NUMERIC, artist TEXT, title TEXT, datetime NUMERIC, context TEXT, emerg_id NUMERIC, notes TEXT)')

    #
    # Add entry to play log.
    #
    # media_id : id of media being played (to match web app database)
    # artist : name of artist being played (in case information is lost in web app db)
    # title : title of media being played (in case information is lost in web app db)
    # datetime : unix timestamp of play start time (UTC/GMT)
    # context : what is the context of this media being played (should be 'show' or 'emerg')
    # emerg_id : if this is an emergency broadcast, what is the emergency broadcast id?
    # notes : any misc notes (in particular, offset if play is resumed part-way through).
    #
    def playlog_add(self, media_id, artist, title, datetime, context, emerg_id='', notes=''):

        artist = self.escape(artist)
        title = self.escape(title)
        notes = self.escape(notes)

        self.cur.execute("INSERT INTO playlog VALUES (null, '" + str(media_id) + "','" + artist + "','" + title + "','" + str(datetime) + "','" + context + "','" + str(emerg_id) + "','" + notes + "')"
                         )
        return self.con.last_insert_rowid()

    #
    # Get playlog from given timestamp (used for syncing with web app database)
    #
    def playlog_entries_since(self, timestamp):

        rows = self.cur_sync.execute("SELECT id,media_id,artist,title,datetime,context,emerg_id,notes from playlog WHERE datetime > '" + str(timestamp) + "'")

        return_array = []

        for row in rows:

            log = {}

            log['id'] = row[0]
            log['media_id'] = row[1]
            log['artist'] = row[2]
            log['title'] = row[3]
            log['datetime'] = row[4]
            log['context'] = row[5]
            log['emerg_id'] = row[6]
            log['notes'] = row[7]

            return_array.append(log)

        return return_array

    #
    # Remove playlog entries since ID (used after a successful sync with web app database)
    #
    def remove_playlog_entries_since(self, entryid):
        self.cur_sync.execute('DELETE from playlog WHERE id <= ' + str(entryid))
        return True



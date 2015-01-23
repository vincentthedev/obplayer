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
import obplayer.alerts

import traceback
import time

import socket
import sys
import os

import thread
import requests

import urlparse
import codecs

class ObAlertFetcher (obplayer.ObThread):
    def __init__(self, processor):
	obplayer.ObThread.__init__(self, 'ObAlertFetcher')
	self.daemon = True

	self.processor = processor
	self.socket = None
	self.buffer = ""
	self.receiving_data = False

    def close(self):
	if self.socket:
	    addr, port = self.socket.getsockname()
	    obplayer.Log.log("closing socket %s:%s" % (addr, port), 'alerts')
	    self.socket.shutdown(socket.SHUT_WR)
	    self.socket.close()
	    self.socket = None

    def read_alert_data(self):
	while True:
	    if self.buffer:
		if self.receiving_data is False:
		    i = self.buffer.find('<alert')
		    if i >= 0:
			self.buffer = self.buffer[i:]
			self.receiving_data = True

		if self.receiving_data is True:
		    data, endtag, remain = self.buffer.partition('</alert>')
		    if endtag:
			self.buffer = remain
			self.receiving_data = False
			return data + endtag

	    data = self.receive()
	    if not data:
		self.socket = None
		raise socket.error("TCP socket closed by remote end. (" + str(self.host) + ":" + str(self.port) + ")")
	    self.buffer = self.buffer + data

    def run(self):
	while True:
	    self.connect()
	    while True:
		try:
		    data = self.read_alert_data()
		    if (data):
			alert = obplayer.alerts.ObAlert(data)
			alert.print_data()
			self.processor.dispatch(alert)

			# TODO for testing only
			#with codecs.open(obplayer.ObData.get_datadir() + "/alerts/" + alert.identifier + '.xml', 'w', encoding='utf-8') as f:
			#    f.write(data)

		except socket.error, e:
		    obplayer.Log.log("Socket Error: " + str(e), 'alerts')
		    break

		except:
		    obplayer.Log.log("exception in " + self.name + " thread", 'error')
		    obplayer.Log.log(traceback.format_exc(), 'alerts')
	    self.close()
	    time.sleep(2)

    def stop(self):
	self.close()


class ObAlertTCPFetcher (ObAlertFetcher):
    def __init__(self, processor, hosts=None):
	ObAlertFetcher.__init__(self, processor)
	self.hosts = hosts

    def connect(self):
	if self.socket is not None:
	    self.close()

	for urlstring in self.hosts:
	    url = urlparse.urlparse(urlstring, 'http')
	    urlparts = url.netloc.split(':')
	    (self.host, self.port) = (urlparts[0], urlparts[1] if len(urlparts) > 1 else 80)
	    for res in socket.getaddrinfo(self.host, self.port, socket.AF_UNSPEC, socket.SOCK_STREAM):
		af, socktype, proto, canonname, sa = res
		try:
		    self.socket = socket.socket(af, socktype, proto)
		except socket.error as msg:
		    self.socket = None
		    continue

		try:
		    self.socket.connect(sa)
		except socket.error as msg:
		    self.socket.close()
		    self.socket = None
		    continue
		break

	    if self.socket is None:
		obplayer.Log.log("error connecting to alert broadcaster at " + str(self.host) + ":" + str(self.port), 'alerts')
		return False

	    else:
		obplayer.Log.log("connected to alert broadcaster at " + str(self.host) + ":" + str(self.port), 'alerts')
		return True

    def receive(self):
	return self.socket.recv(4096)

    def send(self, data):
	self.socket.send(data)


class ObAlertUDPFetcher (ObAlertFetcher):
    def __init__(self, processor, hosts=None):
	ObAlertFetcher.__init__(self, processor)
	self.hosts = hosts

    def connect(self):
	self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	#self.socket.bind(('', self.port))

    def receive(self):
	return self.socket.recv(4096)

    def send(self, data):
	self.socket.sendto(data, (self.host, self.port))


class ObAlertProcessor (object):
    def __init__(self):
	self.lock = thread.allocate_lock()
	self.next_alert_check = 0
	self.alert_list = { }
	self.active_alerts = { }

	self.dispatch_lock = thread.allocate_lock()
	self.dispatch_queue = [ ]

        self.streaming_hosts = [ obplayer.Config.setting('alerts_naad_stream1'), obplayer.Config.setting('alerts_naad_stream2') ]
        #self.streaming_hosts = [ "streaming1.naad-adna.pelmorex.com:8080", "streaming2.naad-adna.pelmorex.com:8080" ]
        self.archive_hosts = [ obplayer.Config.setting('alerts_naad_archive1'), obplayer.Config.setting('alerts_naad_archive2') ]
        #self.archive_hosts = [ "capcp1.naad-adna.pelmorex.com", "capcp2.naad-adna.pelmorex.com" ]
        self.target_geocode = obplayer.Config.setting('alerts_geocode')
        self.repeat_time = obplayer.Config.setting('alerts_repeat_time')

	self.ctrl = obplayer.Player.create_controller('alerts', 100, default_play_mode='overlap', allow_overlay=True)
	#self.ctrl.do_player_request = self.do_player_request

	self.thread = obplayer.ObThread('ObAlertProcessor', target=self.run)
	self.thread.daemon = True
	self.thread.start()

	self.fetcher = ObAlertTCPFetcher(self, self.streaming_hosts)
	self.fetcher.start()

    def add_alert(self, alert):
	with self.lock:
	    self.alert_list[alert.identifier] = alert

    def set_alert_active(self, alert):
	if alert.active is not True:
	    with self.lock:
		self.active_alerts[alert.identifier] = alert
		alert.active = True

    def set_alert_inactive(self, alert):
	if alert.active is not False:
	    with self.lock:
		alert.active = False
		del self.active_alerts[alert.identifier]

    def get_active_alerts(self):
	alerts = None
	with self.dispatch_lock:
	    alerts = self.active_alerts
	return alerts

    def inject_alert(self, filename):
	obplayer.Log.log("inject test alert from file " + filename, 'alerts')
	with open(filename, 'r') as f:
	    data = f.read()
	alert = obplayer.alerts.ObAlert(data)
	alert.add_geocode(self.target_geocode)
	alert.print_data()
	self.dispatch(alert)

    def dispatch(self, alert):
	with self.lock:
	    self.dispatch_queue.insert(0, alert)

    def handle_dispatch(self, alert):
	self.add_alert(alert)

	# deactivate any previous alerts that are cancelled or superceeded by this alert
	if alert.msgtype == 'update' or alert.msgtype == 'cancel':
	    for (_, identifier, _) in alert.references:
		if identifier in self.alert_list:
		    self.set_alert_inactive(self.alert_list[identifier])

	# TODO have a setting here so that exercise and test type alerts will be optionally displayed

	if alert.status == 'system':
	    self.fetch_references(alert.references)	# only fetch alerts referenced in system heartbeats
	    print "---- ACTIVE ----"
	    for a in self.active_alerts.itervalues():
		a.print_data()
	    print "---- END OF ACTIVE ----"

	if alert.status == 'actual' and alert.scope == 'public':
	    if alert.has_geocode(self.target_geocode):
		self.set_alert_active(alert)
		print "Active Alert:"
		alert.print_data()
		alert.next_play = 0
		if alert.broadcast_immediately():
		    self.next_alert_check = time.time()

    def fetch_references(self, references):
	for (sender, identifier, timestamp) in references:
	    if not identifier in self.alert_list:
		(urldate, _, _) = timestamp.partition('T')
		filename = obplayer.alerts.ObAlert.reference(timestamp, identifier)

		for host in self.archive_hosts:
		    url = "%s/%s/%s.xml" % (host, urldate, filename)
		    try:
			obplayer.Log.log("fetching alert %s using url %s" % (identifier, url), 'alerts')
			r = requests.get(url)

			# TODO for testing only
			#print r.text
			with codecs.open(obplayer.ObData.get_datadir() + "/alerts/" + filename + '.xml', 'w', encoding='utf-8') as f:
			    f.write(r.text)

			if r.status_code == 200:
			    alert = obplayer.alerts.ObAlert(r.text.encode('utf-8'))
			    self.handle_dispatch(alert)
			    break
		    except requests.ConnectionError:
			obplayer.Log.log("error fetching alert %s from %s" % (identifier, host), 'alerts')

    def run(self):
	self.next_expired_check = time.time() + 30
	self.next_alert_check = 0

	while not self.thread.stopflag.wait(1):
	    try:
		present_time = time.time()

		if len(self.dispatch_queue) > 0:
		    alert = None
		    with self.lock:
			alert = self.dispatch_queue.pop()

		    with self.dispatch_lock:
			self.handle_dispatch(alert)

		if present_time > self.next_expired_check:
		    self.next_expired_check = present_time + 30
		    with self.lock:
			for alert in self.active_alerts.itervalues():
			    if alert.is_expired():
				obplayer.Log.log("alert %s has expired" % (obplayer.alerts.ObAlert.reference(alert.sent, alert.identifier),), 'alerts')
				self.set_alert_inactive(alert)

		if present_time > self.next_alert_check:
		    obplayer.Log.log("playing active alerts (%d alert(s) to play)" % (len(self.active_alerts),), 'alerts')
		    with self.lock:
			for alert in self.active_alerts.itervalues():
			    alert_media = alert.get_media_info()
			    if alert_media:
				self.ctrl.add_request(media_type='audio', file_location="obplayer/alerts/data", filename="attention-signal.ogg", duration=4, artist=alert_media['artist'], title=alert_media['title'])
				self.ctrl.add_request(**alert_media)
		    self.next_alert_check = self.ctrl.get_requests_endtime() + self.repeat_time

	    except:
		obplayer.Log.log("exception in " + self.thread.name + " thread", 'error')
		obplayer.Log.log(traceback.format_exc(), 'error')



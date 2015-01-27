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

import xml.dom.minidom
import base64
import hashlib
import dateutil.parser

import traceback
import time

import socket
import sys
import os

import thread
import requests

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst, GstPbutils

def xml_get_text(element):
    text = ''
    for node in element.childNodes:
        if node.nodeType == node.TEXT_NODE:
            text = text + node.data
    return text

def xml_has_tag(element, tag):
    for node in element.childNodes:
	if node.nodeType == node.ELEMENT_NODE and node.nodeName == tag:
	    return True
    return False

def xml_get_tags(element, tag):
    children = [ ]
    for node in element.childNodes:
	if node.nodeType == node.ELEMENT_NODE and node.nodeName == tag:
	    children.append(node)
    return children

def xml_get_tag_values(element, tag):
    values = [ ]
    for child in xml_get_tags(element, tag):
	values.append(xml_get_text(child))
    return values

def xml_get_first_tag_value(element, tag, default=None):
    children = xml_get_tags(element, tag)
    if len(children) <= 0:
	return default
    return xml_get_text(children[0])



class ObAlert (object):
    def __init__(self, xmlcode=None):
	self.active = False
	self.times_played = 0
	self.media_info = None

	if xmlcode is not None:
	    self.parse_cap_xml(xmlcode)

    def parse_cap_xml(self, xmlcode):
	try:
	    alerts = xml.dom.minidom.parseString(xmlcode)
        except:
            obplayer.Log.log('error parsing emergency alert xml data', 'error')
            obplayer.Log.log(traceback.format_exc(), 'error')
	    print xmlcode
            return

	for alert in alerts.getElementsByTagName('alert'):
	    self.identifier = xml_get_first_tag_value(alert, 'identifier')
	    self.sender = xml_get_first_tag_value(alert, 'sender')
	    self.sent = xml_get_first_tag_value(alert, 'sent')
	    self.codes = xml_get_tag_values(alert, 'code')
	    self.status = xml_get_first_tag_value(alert, 'status', default="").lower()
	    self.msgtype = xml_get_first_tag_value(alert, 'msgType', default="").lower()
	    self.scope = xml_get_first_tag_value(alert, 'scope', default="").lower()
	    self.references = [ ref.split(',') for ref in xml_get_first_tag_value(alert, 'references', default="").split() ]

	    self.info = [ ]
	    for node in xml_get_tags(alert, 'info'):
		self.info.append(ObAlertInfo(node))

    def print_data(self):
	print self.identifier
	print self.sent + " by " + self.sender
	print "Status: " + self.status + " Type: " + self.msgtype

	if len(self.info) > 0:
	    print self.info[0].description

    def get_all_info(self, language):
	infos = [ ]
	lang = self.lang_ref(language)
	for info in self.info:
	    if info.language == lang:
		infos.append(info)
	return infos

    def get_first_info(self, language):
	lang = self.lang_ref(language)
	for info in self.info:
	    if info.language == lang:
		return info
	return None

    def has_geocode(self, code):
	for info in self.info:
	    for area in info.areas:
		if area.has_geocode(code):
		    return True
	return False

    def add_geocode(self, code):
	for info in self.info:
	    for area in info.areas:
		area.add_geocode(code)

    def is_expired(self):
	for info in self.info:
	    if not info.is_expired():
		return False
	return True

    def broadcast_immediately(self):
	for info in self.info:
	    val = info.get_parameter("layer:SOREM:1.0:Broadcast_Immediately");
	    if val.lower() == "yes":
		return True
	return False

    def generate_audio(self, language):
	info = self.get_first_info(language)
	if info is None:
	    return False

	# TODO there needs to be a better way to get the datadir
	location = obplayer.ObData.get_datadir() + "/alerts"
        if os.access(location, os.F_OK) == False:
            os.mkdir(location)
	filename = self.reference(self.sent, self.identifier)

	if len(info.resources) > 0:
	    if info.resources[0].write_file(location + "/" + filename) is False:
		return False

	elif info.description:
	    brief = info.description.split('\n\n', 1)
	    obplayer.Log.log("echo \"%s\" | text2wave > %s/%s" % (brief[0], location, filename), 'debug')
	    os.system("echo \"%s\" | text2wave > %s/%s" % (brief[0], location, filename))

	else:
	    return False

	d = GstPbutils.Discoverer()
	mediainfo = d.discover_uri("file:///%s/%s" % (location, filename))

	self.media_info = {
	    'media_type' : 'audio',
	    'artist' : 'Emergency Alert',
	    'title' : str(self.identifier),
	    'file_location' : location,
	    'filename' : filename,
	    'duration' : (mediainfo.get_duration() / float(Gst.SECOND)) + 2
	}

	# the NPAS Common Look and Feel guide states that audio content should not be more than 120 seconds
	if self.media_info['duration'] > 120:
	    self.media_info['duration'] = 120

	obplayer.Log.log("apparent duration of alert audio: " + str(mediainfo.get_duration()) + " (" + str(mediainfo.get_duration() / Gst.SECOND) + ")", 'debug')
	obplayer.Log.log(repr(self.media_info), 'debug')
	return True

    def get_media_info(self, language):
	if self.media_info is None:
	    self.generate_audio(language)
	return self.media_info

    @staticmethod
    def reference(timestamp, identifier):
	reference = timestamp + "I" + identifier
	reference = reference.translate({ ord('-') : ord('_'), ord(':') : ord('_'), ord('+') : ord('p') })
	return reference

    @staticmethod
    def lang_ref(language):
	if language == 'english':
	    return 'en-CA'
	elif language == 'french':
	    return 'fr-CA'
	else:
	    raise Exception("Unsupported language: " + language)


class ObAlertInfo (object):
    def __init__(self, element):
	self.parse_info(element)

    def parse_info(self, info):
	self.language = xml_get_first_tag_value(info, 'language', 'en-US')
	self.event = xml_get_first_tag_value(info, 'event')
	self.urgency = xml_get_first_tag_value(info, 'urgency')
	self.severity = xml_get_first_tag_value(info, 'severity')
	self.certainty = xml_get_first_tag_value(info, 'certainty')

	self.effective = xml_get_first_tag_value(info, 'effective')
	self.onset = xml_get_first_tag_value(info, 'onset')
	self.expires = xml_get_first_tag_value(info, 'expires')

	self.categories = xml_get_tag_values(info, 'category')
	self.responsetypes = xml_get_tag_values(info, 'responseType')

	self.sender = xml_get_first_tag_value(info, 'senderName')
	self.headline = xml_get_first_tag_value(info, 'headline')
	self.description = xml_get_first_tag_value(info, 'description')
	self.instruction = xml_get_first_tag_value(info, 'instruction')

	self.parameters = [ ]
	for parameter in xml_get_tags(info, 'parameter'):
	    name = xml_get_first_tag_value(parameter, 'valueName')
	    val = xml_get_first_tag_value(parameter, 'value')
	    if val is not None:
		self.parameters.append([ name, val ])

	self.eventcodes = [ ]
	for eventcode in xml_get_tags(info, 'eventCode'):
	    name = xml_get_first_tag_value(eventcode, 'valueName')
	    code = xml_get_first_tag_value(eventcode, 'value')
	    if code is not None:
		self.eventcodes.append([ name, code ])

	self.areas = [ ]
	for node in xml_get_tags(info, 'area'):
	    self.areas.append(ObAlertArea(node))

	self.resources = [ ]
	for node in xml_get_tags(info, 'resource'):
	    self.resources.append(ObAlertResource(node))

    def is_expired(self):
	# TODO i don't trust this one bit
	if self.expires:
	    expires = time.mktime(dateutil.parser.parse(self.expires).timetuple())
	    if time.time() > expires:
		return True
	return False

    def get_parameter(self, name):
	for param in self.parameters:
	    if param[0] == name:
		return param[1];
	return None


class ObAlertArea (object):
    def __init__(self, element):
	self.parse_area(element)

    def parse_area(self, area):
	self.description = xml_get_first_tag_value(area, 'areaDesc')
	self.altitude = xml_get_first_tag_value(area, 'altitude')
	self.ceiling = xml_get_first_tag_value(area, 'ceiling')

	self.polygons = xml_get_tag_values(area, 'polygon')
	self.circles = xml_get_tag_values(area, 'circle')

	self.geocodes = [ ]
	for geocode in xml_get_tags(area, 'geocode'):
	    name = xml_get_first_tag_value(geocode, 'valueName')
	    code = xml_get_first_tag_value(geocode, 'value')
	    if code is not None:
		self.geocodes.append([ name, code ])

    def has_geocode(self, code):
	for geocode in self.geocodes:
	    #print geocode[1]
	    # TODO this is a bit of a hack
	    if geocode[0] == 'profile:CAP-CP:Location:0.3' and geocode[1].startswith(code):
		return True
	return False

    def add_geocode(self, code):
	self.geocodes.append([ 'profile:CAP-CP:Location:0.3', code ])


class ObAlertResource (object):
    def __init__(self, element):
	self.parse_resource(element)

    def parse_resource(self, resource):
	self.description = xml_get_first_tag_value(resource, 'resourceDesc')
	self.mimetype = xml_get_first_tag_value(resource, 'mimeType')

	self.size = xml_get_first_tag_value(resource, 'size')
	self.uri = xml_get_first_tag_value(resource, 'uri')

	self.data = None
	derefuri = xml_get_first_tag_value(resource, 'derefUri')
	if derefuri is not None:
	    digest = xml_get_first_tag_value(resource, 'digest')
	    calculated_digest = hashlib.sha1(derefuri).hexdigest()
	    if digest != calculated_digest:
		obplayer.Log.log("emergency alert resource corrupted: " + str(self.uri), 'error')
	    else:
		try:
		    self.data = base64.b64decode(derefuri)
		except:
		    obplayer.Log.log("error parsing base64 resource from emergency alert", 'error')

	elif self.uri is not None:
	    try:
		obplayer.Log.log("fetching alert resource %s" % (self.uri,), 'alerts')
		r = requests.get(self.uri)

		if r.status_code == requests.codes.ok:
		    self.data = r.content
		else:
		    obplayer.Log.log("error fetching alert resource %s: returned status code %s" % (self.uri, r.status_code), 'alerts')
	    except requests.exceptions.RequestException:
		obplayer.Log.log("connection error while fetching alert resource %s" % (self.uri,), 'alerts')

    def write_file(self, filename):
	if not self.data:
	    return False
	with open(filename, 'wb') as f:
	    f.write(self.data)


def parse_alert_file(xmlfile):
    with open(xmlfile, 'r') as f:
	alert = ObAlert(f.read())
    return alert


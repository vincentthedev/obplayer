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

import gobject
from datetime import datetime


class ObGui:

    def __init__(self):
        pass

    def create_window(self):

        if obplayer.Main.headless:
            return
        else:

            global ObGuiSettings, gtk, pygtk

            import pygtk
            import gtk

        builder = gtk.Builder()
        builder.add_from_file('obplayer/ui.glade')

	# SET SOME COLORS
        gtk_black = gtk.gdk.Color(0, 0, 0)

	# MAIN WINDOW
        self.gui_window = builder.get_object('main_window')
        self.gui_window.set_title('Openbroadcaster GTK Remote')
        self.gui_window.resize(640, 480)
        self.gui_window_fullscreen = False

	# MISC WIDGETS
        self.gui_toolbar = builder.get_object('toolbar')
        self.gui_statusbar = builder.get_object('statusbar')

	# SUMMARY AND LOG
        self.gui_infotabs = builder.get_object('infotabs')
        self.gui_summary_text = builder.get_object('summary_text')

        self.gui_log_text = builder.get_object('log_text')
        self.gui_log_textview = builder.get_object('log_textview')
        self.gui_log_lines = 0

	# self.gui_log_textview.modify_base(gtk.STATE_NORMAL, gtk_black)
	#
	# self.gui_log_text_error = self.gui_log_text.create_tag(None, foreground='#550000', weight=800)
        self.gui_log_text_error = self.gui_log_text.create_tag(None, foreground='#550000')
        self.gui_log_text_main = self.gui_log_text.create_tag(None, foreground='#000000')
        self.gui_log_text_emerg = self.gui_log_text.create_tag(None, foreground='#550000')
        self.gui_log_text_sync = self.gui_log_text.create_tag(None, foreground='#000055')
        self.gui_log_text_scheduler = self.gui_log_text.create_tag(None, foreground='#005555')
        self.gui_log_text_player = self.gui_log_text.create_tag(None, foreground='#005500')
        self.gui_log_text_data = self.gui_log_text.create_tag(None, foreground='#333333')
        self.gui_log_text_http = self.gui_log_text.create_tag(None, foreground='#333300')

        self.summary_treeview = builder.get_object('summary_treeview')
        self.summary_store = builder.get_object('summary_store')

        column = gtk.TreeViewColumn('column0', gtk.CellRendererText(), text=0)
        column.set_clickable(True)
        column.set_resizable(True)
        self.summary_treeview.append_column(column)

        column = gtk.TreeViewColumn('column1', gtk.CellRendererText(), text=1)
        column.set_clickable(True)
        column.set_resizable(True)
        self.summary_treeview.append_column(column)

        self.summary_iter = {}

        self.summary_iter['av_track'] = self.summary_store.append(('AV Track', ''))
        self.summary_iter['av_id'] = self.summary_store.append(('AV ID', ''))
        self.summary_iter['av_artist'] = self.summary_store.append(('AV Artist', ''))
        self.summary_iter['av_title'] = self.summary_store.append(('AV Title', ''))
        self.summary_iter['av_duration'] = self.summary_store.append(('AV Duration', ''))
        self.summary_iter['image_track'] = self.summary_store.append(('Image Track', ''))
        self.summary_iter['image_id'] = self.summary_store.append(('Image ID', ''))
        self.summary_iter['image_artist'] = self.summary_store.append(('Image Artist', ''))
        self.summary_iter['image_title'] = self.summary_store.append(('Image Title', ''))
        self.summary_iter['image_duration'] = self.summary_store.append(('Image Duration', ''))

        self.summary_iter['show_id'] = self.summary_store.append(('Show ID', ''))
        self.summary_iter['show_name'] = self.summary_store.append(('Show Name', ''))
        self.summary_iter['show_description'] = self.summary_store.append(('Show Description', ''))
        self.summary_iter['sync_status'] = self.summary_store.append(('Sync Status', ''))

	# DRAWING AREA
        self.gui_drawing_area = builder.get_object('drawingarea_slideshow')
        self.gui_drawing_area_alpha = 1
        self.gui_drawing_area.connect('expose_event', self.drawing_area_expose)
        self.gui_drawing_area.set_size_request(250, 250)
        self.gui_drawing_area.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self.gui_drawing_area.modify_bg(gtk.STATE_NORMAL, gtk_black)

        self.gui_gst_area = builder.get_object('drawingarea_gst')
        self.gui_gst_area_alpha = 1
        self.gui_gst_area.set_size_request(250, 250)
        self.gui_gst_area.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self.gui_gst_area.modify_bg(gtk.STATE_NORMAL, gtk_black)

        self.gui_drawing_area_viewport = builder.get_object('drawingarea_slideshow_viewport')
        self.gui_gst_area_viewport = builder.get_object('drawingarea_gst_viewport')

        self.gui_gst_area_viewport.hide()

	import threading
	print threading.current_thread()

        self.pixbuf = False
        self.pixbuf_original = False
        self.next_pixbuf = False
        self.next_pixbuf_original = False

	# track our fullscreen pointer hide timeout event id.
        self.fullscreen_hide_pointer_id = None

	# connect signals
        builder.connect_signals(self)

	# start minimized?
        if obplayer.Main.args.minimize:
            self.gui_window.iconify()

	# go fullscreen?
        if obplayer.Main.args.fullscreen:
            self.fullscreen_toggle(None)

	# show main window.
	if obplayer.Main.headless == False:
	   self.gui_window.show();

    def set_media_summary_item(self, name, value):
        if obplayer.Main.headless:
            return

        self.summary_store.set_value(self.summary_iter[name], 1, value)

    def set_media_summary(self, media, track):
        if obplayer.Main.headless:
            return

        gobject.idle_add(self.set_media_summary_idleadd, media, track)

    def set_media_summary_idleadd(self, media, track):
        if obplayer.Main.headless:
            return

	# figure out what we're setting
        if media['media_type'] == 'image':
            mode = 'image'
        else:
            mode = 'av'

        if str(media['media_id']) == '0':
            media_id = ''
        else:
            media_id = media['media_id']

        self.set_media_summary_item(mode + '_id', str(media_id))
        self.set_media_summary_item(mode + '_artist', media['artist'])
        self.set_media_summary_item(mode + '_title', media['title'])
        self.set_media_summary_item(mode + '_duration', str(media['duration']))
        self.set_media_summary_item(mode + '_track', str(track))

    def set_show_summary(self, show_id, name, description):
        if obplayer.Main.headless:
            return

        gobject.idle_add(self.set_show_summary_idleadd, show_id, name, description)

    def set_show_summary_idleadd(self, show_id, name, description):
        if obplayer.Main.headless:
            return

        if str(show_id) == '0':
            show_id = ''

        self.set_media_summary_item('show_id', str(show_id))
        self.set_media_summary_item('show_name', name)
        self.set_media_summary_item('show_description', description)

    def reset_media_summary(self, mode):
        if obplayer.Main.headless:
            return

        gobject.idle_add(self.reset_media_summary_idleadd, mode)

    def reset_media_summary_idleadd(self, mode):
        if obplayer.Main.headless:
            return

        if mode == 'av' or mode == 'all':
            self.set_media_summary_item('av_id', '')
            self.set_media_summary_item('av_artist', '')
            self.set_media_summary_item('av_title', '')
            self.set_media_summary_item('av_duration', '')
            self.set_media_summary_item('av_track', '')

        if mode == 'image' or mode == 'all':
            self.set_media_summary_item('image_id', '')
            self.set_media_summary_item('image_artist', '')
            self.set_media_summary_item('image_title', '')
            self.set_media_summary_item('image_duration', '')
            self.set_media_summary_item('image_track', '')

    def reset_show_summary(self):
        if obplayer.Main.headless:
            return

        gobject.idle_add(self.reset_show_summary_idleadd)

    def reset_show_summary_idleadd(self):
        if obplayer.Main.headless:
            return

        self.set_media_summary_item('show_id', '')
        self.set_media_summary_item('show_name', '')
        self.set_media_summary_item('show_description', '')

    def pointer_position_watch(self, widget, event):
        if obplayer.Main.headless:
            return

        if self.gui_window_fullscreen == False:
            return

        self.fullscreen_show_pointer()

        if self.fullscreen_hide_pointer_id != None:
            gobject.source_remove(self.fullscreen_hide_pointer_id)

        self.fullscreen_hide_pointer_id = gobject.timeout_add(3000, self.fullscreen_hide_pointer)

        if event.y < 20:
            self.gui_toolbar.show()
        else:

            self.gui_toolbar.hide()

    def fullscreen_toggle(self, widget):
        if obplayer.Main.headless:
            return

        if self.gui_window_fullscreen == False:
            self.gui_window.fullscreen()
            self.gui_window_fullscreen = True
            self.gui_toolbar.hide()
            self.gui_infotabs.hide()
            self.fullscreen_hide_pointer_id = gobject.timeout_add(1000, self.fullscreen_hide_pointer)
        else:

            self.gui_window.unfullscreen()
            self.gui_window_fullscreen = False
            self.gui_toolbar.show()
            self.gui_infotabs.show()
            self.fullscreen_show_pointer()

    def fullscreen_hide_pointer(self):
        if obplayer.Main.headless:
            return

        if self.gui_window_fullscreen == False:
            return

        pix = gtk.gdk.Pixmap(self.gui_window.window, 1, 1, 1)
        color = gtk.gdk.Color()
        cursor = gtk.gdk.Cursor(pix, pix, color, color, 0, 0)
        self.gui_window.window.set_cursor(cursor)

        self.gui_toolbar.hide()

        return False  # gobject.timeout_add for pointer show/hide on fullscreen, using return false to avoid repeated calls.

    def fullscreen_show_pointer(self):
        if obplayer.Main.headless:
            return

        self.gui_window.window.set_cursor(None)

    def pixbuf_resize_to_drawing_area(self, pixbuf):
        if obplayer.Main.headless:
            return

        org_img_size = (pixbuf.get_width(), pixbuf.get_height())
        org_img_size_ratio = float(org_img_size[0]) / float(org_img_size[1])

        target_img_size = (self.gui_drawing_area.allocation.width, self.gui_drawing_area.allocation.height)
        target_img_size_ratio = float(target_img_size[0]) / float(target_img_size[1])

        if org_img_size_ratio >= target_img_size_ratio:
            img_size = (target_img_size[0], org_img_size[1] * (float(target_img_size[0]) / float(org_img_size[0])))
        else:

            img_size = (org_img_size[0] * (float(target_img_size[1]) / float(org_img_size[1])), target_img_size[1])

        return pixbuf.scale_simple(int(img_size[0]), int(img_size[1]), gtk.gdk.INTERP_BILINEAR)

    def drawing_area_resize_event(self, widget, event):
        if obplayer.Main.headless:
            return

        if self.pixbuf_original != False:
            self.pixbuf = self.pixbuf_resize_to_drawing_area(self.pixbuf_original)
            self.gui_drawing_area.queue_draw()

    def drawing_area_expose(self, da, event):
        if obplayer.Main.headless:
            return

        if self.pixbuf != False:

            imgw = self.pixbuf.get_width()
            if imgw < self.gui_drawing_area.allocation.width:
                offset_x = int((self.gui_drawing_area.allocation.width - imgw) / 2)
            else:
                offset_x = 0

            imgh = self.pixbuf.get_height()
            if imgh < self.gui_drawing_area.allocation.height:
                offset_y = int((self.gui_drawing_area.allocation.height - imgh) / 2)
            else:
                offset_y = 0

            self.cairo = da.window.cairo_create()
            self.cairo.set_source_pixbuf(self.pixbuf, offset_x, offset_y)
            self.cairo.paint_with_alpha(self.gui_drawing_area_alpha)
            self.cairo.stroke()
        else:
            try:
                self.cairo.destroy()
            except:
                pass

    def drawing_area_transition_timer(self, action):
        if obplayer.Main.headless:
            return

        if action == 'fade':

            if self.drawing_area_transition_mode == 'out' and self.pixbuf != False:
                if self.gui_drawing_area_alpha <= 0:
                    self.drawing_area_transition_mode = 'in'
                    self.pixbuf = self.next_pixbuf
                    self.pixbuf_original = self.next_pixbuf_original
                else:

                    self.gui_drawing_area_alpha -= 0.05
                    self.gui_drawing_area.queue_draw()

            if self.drawing_area_transition_mode == 'in' and self.pixbuf != False:
                if self.gui_drawing_area_alpha >= 1:
                    return False
                else:

                    self.gui_drawing_area_alpha += 0.05

            self.gui_drawing_area.queue_draw()

        return True

    def drawing_area_image_update(self, filename=False):
        if obplayer.Main.headless:
            return

        gobject.idle_add(self.drawing_area_image_update_idleadd, filename)

    def drawing_area_image_update_idleadd(self, filename=False):
        if obplayer.Main.headless:
            return

        if filename != False:
            self.next_pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(filename, self.gui_drawing_area.allocation.width, self.gui_drawing_area.allocation.height)
            self.next_pixbuf_original = self.next_pixbuf
            self.next_pixbuf = self.pixbuf_resize_to_drawing_area(self.next_pixbuf_original)
        else:

            self.next_pixbuf = False
            self.next_pixbuf_original = False

        if self.pixbuf != False:
            self.drawing_area_transition_mode = 'out'
            gobject.timeout_add(50, self.drawing_area_transition_timer, 'fade')
        else:

            self.gui_drawing_area_alpha = 0
            self.pixbuf = self.next_pixbuf
            self.pixbuf_original = self.next_pixbuf_original
            self.drawing_area_transition_mode = 'in'
            gobject.timeout_add(50, self.drawing_area_transition_timer, 'fade')

    def set_sync_status(self, message):
        if obplayer.Main.headless:
            return

        gobject.idle_add(self.set_sync_status_idleadd, message)

    def set_sync_status_idleadd(self, message):
        if obplayer.Main.headless:
            return

        self.set_media_summary_item('sync_status', message)

    def summary_text_set(self, text):
        if obplayer.Main.headless:
            return

        self.gui_summary_text.set_text(text)

    def log_text_add(self, text, mtype):
        if obplayer.Main.headless:
            return

        gobject.idle_add(self.log_text_add_idleadd, text, mtype)

    def log_text_add_idleadd(self, text, mtype):
        if obplayer.Main.headless:
            return

        if mtype == 'error':
            tag = self.gui_log_text_error
        elif mtype == 'main':
            tag = self.gui_log_text_main
        elif mtype == 'emerg':
            tag = self.gui_log_text_emerg
        elif mtype == 'sync':
            tag = self.gui_log_text_sync
        elif mtype == 'player':
            tag = self.gui_log_text_player
        elif mtype == 'scheduler':
            tag = self.gui_log_text_scheduler
        elif mtype == 'data':
            tag = self.gui_log_text_data
        elif mtype == 'http':
            tag = self.gui_log_text_http
        else:
            tag = self.gui_log_text_main

        self.gui_log_text.insert_with_tags(self.gui_log_text.get_end_iter(), text + '\n', tag)

	# add 1 to the number of log lines.  remove first line if we are over our max.

        if self.gui_log_lines > 20:
            delete_start_iter = self.gui_log_text.get_iter_at_line(0)
            delete_end_iter = self.gui_log_text.get_iter_at_line(1)
            self.gui_log_text.delete(delete_start_iter, delete_end_iter)
        else:

            self.gui_log_lines = self.gui_log_lines + 1

	# scroll to end of log after inserting.
        self.gui_log_textview.scroll_to_iter(self.gui_log_text.get_end_iter(), 0.0)

        return False

    def application_shutdown(self, widget):
        obplayer.Main.application_shutdown(widget)



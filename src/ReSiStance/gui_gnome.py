#!/usr/bin/env python
# -*- coding: utf-8 -*-

#########################################################################
#    Copyright (C) 2011 Chus Picos Vilar <chuspicos@gmail.com>
#
#    This file is part of ReSiStance
#
#    ReSiStance is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    ReSiStance is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with ReSiStance.  If not, see <http://www.gnu.org/licenses/>.
#########################################################################

from resistanceWindow import ResistanceWindow
from resistanceWindowContent import ResistanceWindowContent
from pango import ELLIPSIZE_END
from portrait import FremantleRotation
from utils import *
from threading import Thread
from webkit import WebView
import calendar
import constants
import feedparser
import gettext
import glib
import gobject
import gtk
import subprocess
import os
import pygtk
pygtk.require('2.0')
import time
import urllib2
import urllib
import atk

_ = gettext.gettext

resistance_window = ResistanceWindow()

google_reader_pixbuf = gtk.gdk.pixbuf_new_from_file(constants.GOOGLE_READER_ICON_FILE)

# SYSTEM COLORS
#color_style = gtk.rc_get_style_by_paths(gtk.settings_get_default() , 'GtkButton', 'osso-logical-colors', gtk.Button)
#ACTIVE_TEXT_COLOR = color_style.lookup_color('ActiveTextColor').to_string()
#DEFAULT_TEXT_COLOR = color_style.lookup_color('DefaultTextColor').to_string()
#SECONDARY_TEXT_COLOR = color_style.lookup_color('SecondaryTextColor').to_string()
#del color_style

SECONDARY_TEXT_COLOR = "grey"

def get_feed_title_markup(title, subtitle = None):

    if subtitle:
        return '<span size="x-large">%s</span>\n<span face="monospace" size="medium">%s</span>' % \
            (glib.markup_escape_text(unescape(title)),glib.markup_escape_text(unescape(subtitle)))
    else:
        return '<span size="x-large">%s</span>' % (glib.markup_escape_text(unescape(title)))

def get_feed_subtitle_markup(subtitle):

    return '<span>%s</span>' % \
        (glib.markup_escape_text(unescape(subtitle)))

def get_visual_unread_text(unread_count):
    if unread_count:
        return '<span size="x-large"> %d </span>' % unread_count
    else:
        return ''

class FeedsView(gtk.TreeView): 

    DUMMY_FEED_STATUS = -1

    def __init__(self):
        super(FeedsView, self).__init__()

        text_renderer = gtk.CellRendererText()
        text_renderer.set_property('ellipsize', ELLIPSIZE_END)

        pix_renderer = gtk.CellRendererPixbuf()

        # Add columns
        # Feed icon column
        column = gtk.TreeViewColumn(_('Icon'), pix_renderer, pixbuf = FeedsWindow.FEEDS_MODEL_PIXBUF_COLUMN)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_resizable(True)
        column.set_fixed_width(100)
        self.append_column(column);       
        
        # Feed google icon column
        column = gtk.TreeViewColumn(_('Sync'), pix_renderer, pixbuf = FeedsWindow.FEEDS_MODEL_SYNC_ICON_COLUMN)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_resizable(True)
        column.set_fixed_width(50)
        self.append_column(column);

        #Title/subtitle column
        column = gtk.TreeViewColumn(_('Name'), text_renderer, markup = FeedsWindow.FEEDS_MODEL_TITLE_COLUMN)
        # This allows the column header ('Name') to be clickable and sort/order items
        column.set_sort_column_id(1)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_resizable(True)
        column.set_expand(True)
        self.append_column(column);

        # Unread entries column
        date_renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('Unread'), date_renderer, markup = FeedsWindow.FEEDS_MODEL_READ_COLUMN)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_resizable(True)
        column.set_fixed_width(200)
        self.append_column(column);

class FeedsWindow(ResistanceWindowContent):

    FEEDS_MODEL_PIXBUF_COLUMN, FEEDS_MODEL_SYNC_ICON_COLUMN, FEEDS_MODEL_TITLE_COLUMN, FEEDS_MODEL_SUBTITLE_COLUMN, \
        FEEDS_MODEL_READ_COLUMN, FEEDS_MODEL_VISITS_COLUMN, FEEDS_MODEL_SYNC_COLUMN, \
        FEEDS_MODEL_ID_COLUMN, FEEDS_MODEL_HREF_COLUMN, FEEDS_MODEL_LABEL_VISIBLE_COLUMN = range(10)

    def __init__(self, manager, settings, conn_manager, title=None):
        super(FeedsWindow, self).__init__()

        self.manager = manager
        self.manager.connect('feed-added', self._on_feed_added_update_label)
        self.settings = settings
        self._conn_manager = conn_manager
        self._filter_label_id = constants.ALL_LABEL_ID

        self._create_menu()

        # Feeds
        self.view = FeedsView()

        if title:
            self._hbox = gtk.HBox()
            self._title_label = gtk.Label(unescape(title))           
            self._title_label.set_alignment(0.5, 0.5)
            self._hbox.pack_start(self._title_label, True, True)
        else:
            self._hbox = None        

        self.view.columns_autosize()
        store = gtk.ListStore(gtk.gdk.Pixbuf, gtk.gdk.Pixbuf, str, str, str, int, bool, int, str, bool)
        model_filter = store.filter_new()
        model_filter.set_visible_column(self.FEEDS_MODEL_LABEL_VISIBLE_COLUMN)
        self.view.set_model (model_filter)
        self.view.connect ("row-activated", self._on_feed_activated)
        self.view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.view.show()

        self.view.connect('button-press-event', self._button_press_handler)

        resistance_window.window_content(self, self._hbox)

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)

        self.pack_start(scroll, True, True, 0)
        scroll.add(self.view)
        scroll.show()

        self.status_bar = gtk.Statusbar()      
        self.context_id = self.status_bar.get_context_id('Feedswindow statusbar')
        self.pack_start(self.status_bar, False, True, 0)
        self.status_bar.show()

        #To count the number of messages
        self.messages_counter = 0
        #Capture the activity to manage the statusbar
        resistance_window.window.connect('key-press-event', self._clear_status_bar)
        resistance_window.window.connect('button-press-event', self._clear_status_bar)
        self.view.connect('button-press-event', self._clear_status_bar)

        self.sync_message = None

        # Apply settings
        self.settings.load()
        self._sort(self.settings.feeds_order)
        if self.settings.feeds_order == constants.DESCENDING_ORDER:
            self.descending_filter_button.set_active(True)
        elif self.settings.feeds_order == constants.VISITS_ORDER:
            self.visits_filter_button.set_active(True)

        # Load Feeds (could be none)
        try:
            load_message = self.status_bar.push(self.context_id, _('Loading...'))
            self.messages_counter += 1
            self.manager.load_feeds_summary(self._feeds_summary_loaded, load_message)
        except IOError:
            self.status_bar.remove_message(self.context_id, load_message)
            self._new_feed_cb()

    def _set_title(self, title):        
        if self._hbox:
            self._title_label.set_text(title)

    def _clear_status_bar(self, widget, event=None):
        gobject.timeout_add(3000, self._clear_messages)

    def _clear_messages(self):
        for message in range(self.messages_counter):
            self.status_bar.pop(self.context_id)

    def set_filter_label_id(self, filter_label_id):

        if filter_label_id == self._filter_label_id:
            return

        self._filter_label_id = filter_label_id

        # Refilter
        store = self.view.get_model().get_model()
        for row in store:
            feed_id = row[FeedsWindow.FEEDS_MODEL_ID_COLUMN]
            row[FeedsWindow.FEEDS_MODEL_LABEL_VISIBLE_COLUMN] = self.manager.feed_has_label(feed_id, filter_label_id)

        if self.settings.show_labels_startup:
            # Button visibility        
            self._check_label_button_visibility()

    def _check_label_button_visibility(self):
        show_add = False
        show_remove = False
        if self._filter_label_id != constants.ALL_LABEL_ID:
            store = self.view.get_model().get_model()
            for row in store:
                feed_id = row[FeedsWindow.FEEDS_MODEL_ID_COLUMN]
                if (self.manager.feed_has_label(feed_id, self._filter_label_id)):
                    show_remove = True
                else:
                    show_add = True
        
        self._add_to_label_button.set_sensitive(show_add)
        self._remove_from_label_button.set_sensitive(show_remove)
         

    def _add_dummy_feed(self, url, sync=False):

        model_filter = self.view.get_model()
        store = model_filter.get_model()
        feed_iter = store.append()
        store.set(feed_iter,
                  self.FEEDS_MODEL_PIXBUF_COLUMN, None,
                  self.FEEDS_MODEL_TITLE_COLUMN, get_feed_title_markup(_('Retrieving info...')),
                  self.FEEDS_MODEL_SUBTITLE_COLUMN, get_feed_subtitle_markup(url),
                  self.FEEDS_MODEL_READ_COLUMN, '',
                  self.FEEDS_MODEL_VISITS_COLUMN, 0,
                  self.FEEDS_MODEL_SYNC_COLUMN, sync,
                  self.FEEDS_MODEL_ID_COLUMN, self.view.DUMMY_FEED_STATUS,
                  self.FEEDS_MODEL_HREF_COLUMN, url,
                  self.FEEDS_MODEL_LABEL_VISIBLE_COLUMN, True)

        return model_filter.convert_child_iter_to_iter(feed_iter)

    def _on_feed_activated(self, treeview, path, column):
        feed_iter = self.view.get_model().get_iter(path)
        feed_id = self.view.get_model().get_value(feed_iter, self.FEEDS_MODEL_ID_COLUMN)
        # Check that we're not trying to open a dummy feed
        if feed_id == self.view.DUMMY_FEED_STATUS:
            self.status_bar.push(self.context_id, _('Wait until feed is refreshed'))
            self.messages_counter += 1
            return
        
        feed_data = self.manager.get_feed_data(feed_id)
        # Load feed data on demand
        if not feed_data:
            row_reference = gtk.TreeRowReference(self.view.get_model(), path)
            self.manager.load(feed_id, self._feed_data_loaded_cb, row_reference)
            return

        self._show_entries_window(path)

    def _show_entries_window(self, path):
        model_filter = self.view.get_model()
        feed_iter = model_filter.get_iter(path)
        feed_id = model_filter.get_value(feed_iter, self.FEEDS_MODEL_ID_COLUMN)
        summary = self.manager.get_feed_summary(feed_id)
        feed_data = self.manager.get_feed_data(feed_id)

        news_window = EntriesWindow(feed_data, self.manager, self.settings, self._conn_manager, self, path)
        news_window.show()

        # Update the visits count
        summary.visits += 1
        store_feed_iter = model_filter.convert_iter_to_child_iter(feed_iter)
        model_filter.get_model().set_value(store_feed_iter, self.FEEDS_MODEL_VISITS_COLUMN, summary.visits)

    def _feed_data_loaded_cb(self, feed_data, row_reference, error):
        if not feed_data:
            print _('Error loading feed data')
            return

        self._show_entries_window(row_reference.get_path())

    def _button_press_handler(self, treeview, event):
        if event.button == 3:
            # Figure out which item they right clicked on
            path = treeview.get_path_at_pos(int(event.x),int(event.y))
            # Get the selection
            selection = self.view.get_selection()

            # Get the selected path(s)
            selected_rows = selection.get_selected_rows()

            if path is None:
                self._context_menu(treeview, event)
                return True
            # If they didnt right click on a currently selected row, change the selection
            #if not selection.path_is_selected(path):
            elif path[0] not in selected_rows[1]:
                selection.unselect_all()
                selection.select_path(path[0])
                
            if selection.count_selected_rows() > 0:       
                self._context_menu(treeview, event, path)

            return True

    def _context_menu(self, widget, event, path=None, data=None):
        menu = gtk.Menu()

        update_item = gtk.MenuItem(_('Update'))
        update_item.set_sensitive(False)
        update_item.connect('activate', self._update_button_clicked_cb)
        menu.append(update_item)

        remove_item = gtk.MenuItem(_('Remove'))
        remove_item.set_sensitive(False)
        remove_item.connect('activate', self._remove_button_clicked_cb)
        menu.append(remove_item)

        separator = gtk.SeparatorMenuItem()
        menu.append(separator)

        menu_item = gtk.MenuItem(_('New Feed'))
        menu_item.connect('activate', self._new_feed_cb)
        menu.append(menu_item)

        menu_item = gtk.MenuItem(_('Update All'))
        menu_item.connect('activate', self._update_all_cb)
        menu.append(menu_item)

        menu_item = gtk.MenuItem(_('Export Feeds'))
        menu_item.connect('activate', self._export_feed_cb)
        menu.append(menu_item)

        menu_item = gtk.MenuItem(_('Import Feeds'))
        menu_item.connect('activate', self._import_feed_cb)
        menu.append(menu_item)

        menu_item = gtk.MenuItem(_('Find Feeds'))
        menu_item.connect('activate', self._find_feed_cb)
        menu.append(menu_item)

        add_greader_item = gtk.MenuItem(_('Add GReader'))
        add_greader_item.set_sensitive(False)
        add_greader_item.connect('activate', self._subscribe_feed_cb, True)
        menu.append(add_greader_item)

        remove_greader_item = gtk.MenuItem(_('Remove GReader'))
        remove_greader_item.set_sensitive(False)
        remove_greader_item.connect('activate', self._subscribe_feed_cb, False)
        menu.append(remove_greader_item)

        if self.settings.show_labels_startup:
            self.add_label_item = gtk.MenuItem(_('Add to Label'))
            self.add_label_item.set_sensitive(False)
            self.add_label_item.connect('activate', self._add_feed_to_label_cb)
            menu.append(self.add_label_item)

            self.remove_label_item = gtk.MenuItem(_('Remove from Label'))
            self.remove_label_item.set_sensitive(False)
            self.remove_label_item.connect('activate', self._remove_feed_from_label_cb)
            menu.append(self.remove_label_item)

            if self._filter_label_id != constants.ALL_LABEL_ID:
                self.add_label_item.set_sensitive(self._add_to_label_button.get_sensitive())
                self.remove_label_item.set_sensitive(self._remove_from_label_button.get_sensitive())

        if path:
            update_item.set_sensitive(True)
            remove_item.set_sensitive(True)
            add_greader_item.set_sensitive(True)
            remove_greader_item.set_sensitive(True)

        menu.show_all()

        menu.popup(None, None, None, event.button, event.get_time())
        return True

    def _update_button_clicked_cb(self, button):
        selection = self.view.get_selection()
        selected_rows = selection.get_selected_rows()
        model, paths = selected_rows
        if not paths: 
            self.status_bar.push(self.context_id, _('Please select at least one Feed'))
            self.messages_counter += 1
            return

        self.update_cont = 1
        total = len(paths)

        # Quickly show feedback to user
        self.status_bar.push(self.context_id, _('Updating...'))
        self.messages_counter += 1
        button.set_sensitive(False)

        model_filter = self.view.get_model()
        for path in paths:
            feed_iter = model_filter.get_iter(path)
            feed_id = model_filter.get_value(feed_iter, self.FEEDS_MODEL_ID_COLUMN)

            self.manager.update_feed(feed_id, self._feed_updated_cb, total)

    def _feed_updated_cb(self, retval, data, error):
        self.status_bar.push(self.context_id, _('Updated ') + str(self.update_cont) + '/' + str(data))
        self.messages_counter += 1

        self.update_cont += 1

    def _feeds_summary_loaded(self, feeds_summary, user_data, error):
        if user_data:
            self.status_bar.push(self.context_id, _('Loaded'))
            self.messages_counter += 1

        # Iterate over summaries and fill the model
        model_filter = self.view.get_model()
        store = model_filter.get_model()
        if feeds_summary == None:
            return
        if len(feeds_summary) == 0:
            self.export_opml_button.set_sensitive(False)
        for summary in feeds_summary:
            feed_iter = store.append()
            visible = self.manager.feed_has_label(summary.feed_id, self._filter_label_id)
            store.set(feed_iter,
                      self.FEEDS_MODEL_TITLE_COLUMN, get_feed_title_markup(summary.title, summary.subtitle),
                      self.FEEDS_MODEL_SUBTITLE_COLUMN, get_feed_subtitle_markup(summary.subtitle),
                      self.FEEDS_MODEL_READ_COLUMN, get_visual_unread_text(summary.unread),
                      self.FEEDS_MODEL_VISITS_COLUMN, summary.visits,
                      self.FEEDS_MODEL_SYNC_COLUMN, summary.sync,
                      self.FEEDS_MODEL_ID_COLUMN, summary.feed_id,
                      self.FEEDS_MODEL_HREF_COLUMN, summary.href,
                      self.FEEDS_MODEL_LABEL_VISIBLE_COLUMN, visible)
            # Favicon might require a network download
            path = store.get_path(feed_iter)
            row_reference = gtk.TreeRowReference(store, path)
            self.manager.get_favicon(summary.favicon, self._get_favicon_cb, row_reference)

            if summary.sync:        
                store.set(feed_iter, self.FEEDS_MODEL_SYNC_ICON_COLUMN, google_reader_pixbuf)

        if self.settings.show_labels_startup:
            self._check_label_button_visibility()

    def _get_favicon_cb(self, pixbuf, row_reference, error):
        if pixbuf == None:
            return

        store = self.view.get_model().get_model()
        feed_iter = store.get_iter(row_reference.get_path())
        store.set(feed_iter, self.FEEDS_MODEL_PIXBUF_COLUMN, pixbuf)

    def _create_menu(self):
        self.handlebox = gtk.HandleBox()
        self.toolbar = gtk.Toolbar()
        self.toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        self.toolbar.set_style(gtk.TOOLBAR_BOTH)
        self.toolbar.set_border_width(5)
        self.toolbar.set_tooltips(True)
        self.handlebox.add(self.toolbar)

        agr = resistance_window.resistance_window_agr()

        button = gtk.ToolButton() 
        button.set_stock_id(gtk.STOCK_ADD)
        button.set_label(_('New Feed'))
        button.connect('clicked', self._new_feed_cb)
        button.connect('clicked', self._clear_status_bar)
        button.set_tooltip_text( _('Add a new feed [Ctrl+N]'))
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>N")
        button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        self.toolbar.insert(button, 0)        

        button = gtk.ToolButton() 
        button.set_stock_id(gtk.STOCK_REMOVE)
        button.set_label(_('Remove Feed'))
        button.connect('clicked', self._remove_button_clicked_cb)
        button.connect('clicked', self._clear_status_bar)
        button.set_tooltip_text( _('Remove one or more feeds [Ctrl+D]'))
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>D")
        button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        self.toolbar.insert(button, 1)        

        button = gtk.ToolButton() 
        button.set_stock_id(gtk.STOCK_REFRESH)
        button.set_label(_('Update all'))
        button.connect('clicked', self._update_all_cb)
        button.connect('clicked', self._clear_status_bar)
        button.set_tooltip_text( _('Update the entries of the feeds [Ctrl+R]'))
        self._update_all_button = button
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>R")
        button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        separator_1 = gtk.SeparatorToolItem()
         
        self.toolbar.insert(button, 2)
        self.toolbar.insert(separator_1, 3) 

        button = gtk.ToolButton() 
        export_icon = gtk.gdk.pixbuf_new_from_file(constants.EXPORT_ICON_FILE)
        export_image = gtk.Image()
        export_image.set_from_pixbuf(export_icon)
        button.set_icon_widget(export_image)
        button.set_label(_('Export'))
        button.connect('clicked', self._export_feed_cb)
        button.connect('clicked', self._clear_status_bar)
        button.set_tooltip_text( _('Export the list of feeds in an opml file [Ctrl+E]'))
        self.export_opml_button = button
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>E")
        button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        self.toolbar.insert(button, 4)

        button = gtk.ToolButton()
        import_icon = gtk.gdk.pixbuf_new_from_file(constants.IMPORT_ICON_FILE)
        import_image = gtk.Image()
        import_image.set_from_pixbuf(import_icon)
        button.set_icon_widget(import_image)
        button.set_label(_('Import'))
        button.connect('clicked', self._import_feed_cb)
        button.connect('clicked', self._clear_status_bar)
        button.set_tooltip_text( _('Import a list of feeds from an opml file [Ctrl+I]'))
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>I")
        button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        separator_2 = gtk.SeparatorToolItem()

        self.toolbar.insert(button, 5)
        self.toolbar.insert(separator_2, 6)

        self.ascending_filter_button = gtk.RadioToolButton(None, gtk.STOCK_SORT_ASCENDING)
        self.ascending_filter_button.set_label(_('A-Z'))
        self.ascending_filter_button.set_active(False)
        self.ascending_filter_button.connect('toggled', self._sort_ascending_cb)
        #self.ascending_filter_button.connect('clicked', self._clear_status_bar)
        self.ascending_filter_button.set_tooltip_text(_('Sort the feeds in ascending order [Ctrl+T]'))
        self.toolbar.insert(self.ascending_filter_button, 7)
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>T")
        self.ascending_filter_button.add_accelerator('toggled', agr, key, mod, gtk.ACCEL_VISIBLE)

        self.descending_filter_button = gtk.RadioToolButton(self.ascending_filter_button, gtk.STOCK_SORT_DESCENDING)
        self.descending_filter_button.set_label(_('Z-A'))
        self.descending_filter_button.set_active(False)
        self.descending_filter_button.connect('toggled', self._sort_descending_cb)
        #self.descending_filter_button.connect('clicked', self._clear_status_bar)
        self.descending_filter_button.connect('clicked', self._sort_descending_cb)
        self.descending_filter_button.set_tooltip_text(_('Sort the feeds in descending order [Ctrl+Z]'))
        self.toolbar.insert(self.descending_filter_button, 8)
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>Z")
        self.descending_filter_button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        self.visits_filter_button = gtk.RadioToolButton(self.ascending_filter_button, gtk.STOCK_ABOUT)
        self.visits_filter_button.set_label(_('Favorites'))
        self.visits_filter_button.set_active(False)
        self.visits_filter_button.connect('toggled', self._sort_visits_cb)
        #self.visits_filter_button.connect('clicked', self._clear_status_bar)
        self.visits_filter_button.set_tooltip_text(_('Sort the feeds according to the most read [Ctrl+V]'))
        self.toolbar.insert(self.visits_filter_button, 9)
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>V")
        self.visits_filter_button.add_accelerator('toggled', agr, key, mod, gtk.ACCEL_VISIBLE)

        separator_3 = gtk.SeparatorToolItem()
        self.toolbar.insert(separator_3, 10)

        button = gtk.ToolButton() 
        button.set_stock_id(gtk.STOCK_FIND)
        button.set_label(_('Find'))
        button.connect('clicked', self._find_feed_cb)
        button.connect('clicked', self._clear_status_bar)
        button.set_tooltip_text( _('Find feeds by keywords [Ctrl+F]'))
        self.toolbar.insert(button, 11)
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>F")
        button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        button = gtk.ToolButton() 
        button.set_stock_id(gtk.STOCK_PREFERENCES)
        button.set_label(_('Settings'))
        button.connect('clicked', self._preferences_cb)
        button.connect('clicked', self._clear_status_bar)
        button.set_tooltip_text( _('Select your personal settings [Ctrl+S]'))
        self.toolbar.insert(button, 12)
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>S")
        button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        separator_4 = gtk.SeparatorToolItem()
        self.toolbar.insert(separator_4, 13)

        button = gtk.ToolButton() 
        google_icon = gtk.gdk.pixbuf_new_from_file(constants.GOOGLE_READER_ICON_FILE)
        google_image = gtk.Image()
        google_image.set_from_pixbuf(google_icon)
        button.set_icon_widget(google_image)
        button.set_label(_('Add GReader'))
        button.connect('clicked', self._subscribe_feed_cb, True)
        button.connect('clicked', self._clear_status_bar)
        button.set_tooltip_text( _('Add feeds to Google Reader [Ctrl+G] Use menu Settings to add your user and password'))
        self._sync_feed_button = button
        self.toolbar.insert(button, 14)
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>G")
        button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        button = gtk.ToolButton() 
        google_icon = gtk.gdk.pixbuf_new_from_file(constants.GOOGLE_READER_REMOVE_ICON_FILE)
        google_image = gtk.Image()
        google_image.set_from_pixbuf(google_icon)
        button.set_icon_widget(google_image)
        button.set_label(_('Remove GReader'))
        button.connect('clicked', self._subscribe_feed_cb, False)
        button.connect('clicked', self._clear_status_bar)
        button.set_tooltip_text( _('Remove feeds to Google Reader [Ctrl+Alt+G] Use menu Settings to add your user and password'))
        self._sync_feed_remove_button = button
        self.toolbar.insert(button, 15)
        #shortcut
        key, mod = gtk.accelerator_parse("<Control><Alt>G")
        button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        separator_5 = gtk.SeparatorToolItem()
        self.toolbar.insert(separator_5, 16)

        if self.settings.show_labels_startup:
            button = gtk.ToolButton() 
            add_to_label_icon = gtk.gdk.pixbuf_new_from_file(constants.ADD_TO_LABEL_ICON_FILE)
            add_to_label_image = gtk.Image()
            add_to_label_image.set_from_pixbuf(add_to_label_icon)
            button.set_icon_widget(add_to_label_image)
            button.set_label(_('Add to Label'))
            button.connect('clicked', self._add_feed_to_label_cb)
            button.connect('clicked', self._clear_status_bar)
            button.set_tooltip_text( _('Add feeds to this label [Ctrl+L]'))
            self._add_to_label_button = button
            self.toolbar.insert(button, 17)
            #shortcut
            key, mod = gtk.accelerator_parse("<Control>L")
            button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

            button = gtk.ToolButton() 
            remove_from_label_icon = gtk.gdk.pixbuf_new_from_file(constants.REMOVE_FROM_LABEL_ICON_FILE)
            remove_from_label_image = gtk.Image()
            remove_from_label_image.set_from_pixbuf(remove_from_label_icon)
            button.set_icon_widget(remove_from_label_image)
            button.set_label(_('Remove from Label'))
            button.connect('clicked', self._remove_feed_from_label_cb)
            button.connect('clicked', self._clear_status_bar)
            button.set_tooltip_text( _('Remove feeds from this label [Ctrl+Shift+L]'))
            self._remove_from_label_button = button
            self.toolbar.insert(button, 18)
            #shortcut
            key, mod = gtk.accelerator_parse("<Control><Shift>L")
            button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        self.pack_start(self.handlebox, False, False, 0)
        self.toolbar.show_all()
        self.handlebox.show_all()

    def _sort_ascending_cb(self, button):
        if not button.get_active():
            return
        self.settings.feeds_order = constants.ASCENDING_ORDER
        self._sort(constants.ASCENDING_ORDER)

    def _sort_descending_cb(self, button):
        if not button.get_active():
            return
        self.settings.feeds_order = constants.DESCENDING_ORDER
        self._sort(constants.DESCENDING_ORDER)

    def _sort_visits_cb(self, button):
        if not button.get_active():
            return
        self.settings.feeds_order = constants.VISITS_ORDER
        self._sort(constants.VISITS_ORDER)

    def _sort(self, order):
        store = self.view.get_model().get_model()
        if (order == constants.ASCENDING_ORDER):
            store.set_sort_column_id(self.FEEDS_MODEL_TITLE_COLUMN, gtk.SORT_ASCENDING)
        elif (order == constants.DESCENDING_ORDER):
            store.set_sort_column_id(self.FEEDS_MODEL_TITLE_COLUMN, gtk.SORT_DESCENDING)
        else:
            store.set_sort_column_id(self.FEEDS_MODEL_VISITS_COLUMN, gtk.SORT_DESCENDING)

    def _new_feed_cb(self, button=None):
        dialog = NewFeedDialog(self)
        dialog.connect('response', self._new_feed_response_cb)
        dialog.show_all()

    def _new_feed_response_cb(self, dialog, response):

        if response == gtk.RESPONSE_ACCEPT:

            url = dialog.entry.get_text()

            # Quickly show feedback to user
            self.status_bar.push(self.context_id, _('Adding...'))
            self.messages_counter += 1

            # Insert a dummy row while information is retrieved
            feed_iter = self._add_dummy_feed(url)
            path = self.view.get_model().get_path(feed_iter)
            row_reference = gtk.TreeRowReference(self.view.get_model(), path)

            # Add feed to manager
            self.manager.add_feed(url, False, self._feed_added_cb, row_reference)

            dialog.destroy()

    def _feed_added_cb(self, pixbuf_and_data, row_reference=None, error=None, stop_progress=True):
        # Remove progress information
        if stop_progress:
            self.status_bar.push(self.context_id, _('Added'))
            self.messages_counter += 1

        model_filter = self.view.get_model()
        store = model_filter.get_model()
        if row_reference != None:
            store_path = model_filter.convert_path_to_child_path(row_reference.get_path())
            feed_iter = store.get_iter(store_path)
        else:
            feed_iter = store.append()

        # Check that the feed data was retrieved
        if error:
            message = _('Could not retrieve feed')
            href = store.get_value (feed_iter, self.FEEDS_MODEL_HREF_COLUMN)
            if href:
                message += ' from ' + href
            store.remove(feed_iter)
            self.status_bar.push(self.context_id, message)
            self.messages_counter += 1
            self._warning_message(message)
            return

        self.export_opml_button.set_sensitive(True)

        if self.settings.show_labels_startup:
            self._update_labels_menu()            

        pixbuf, new_feed_data = pixbuf_and_data
        self.export_opml_button.set_sensitive(True)
        # Update model
        feed_id = get_feed_id(new_feed_data)
        summary = self.manager.get_feed_summary(feed_id)
        subtitle = get_feed_subtitle(new_feed_data)
        visible = self.manager.feed_has_label(summary.feed_id, self._filter_label_id)
        store.set(feed_iter,
                  self.FEEDS_MODEL_PIXBUF_COLUMN, pixbuf,
                  self.FEEDS_MODEL_TITLE_COLUMN, get_feed_title_markup(new_feed_data.feed.title, subtitle),
                  self.FEEDS_MODEL_SUBTITLE_COLUMN, get_feed_subtitle_markup(subtitle),
                  self.FEEDS_MODEL_READ_COLUMN, get_visual_unread_text(len(new_feed_data.entries)),
                  self.FEEDS_MODEL_VISITS_COLUMN, summary.visits,
                  self.FEEDS_MODEL_SYNC_COLUMN, summary.sync,
                  self.FEEDS_MODEL_ID_COLUMN, feed_id,
                  self.FEEDS_MODEL_HREF_COLUMN, new_feed_data.href,
                  self.FEEDS_MODEL_LABEL_VISIBLE_COLUMN, visible)

        if summary.sync:
            store.set(feed_iter, self.FEEDS_MODEL_SYNC_ICON_COLUMN, google_reader_pixbuf)

    def _warning_message(self, message):
        gtk.gdk.threads_enter()
        dialog = gtk.MessageDialog(None,
                               gtk.DIALOG_MODAL, gtk.MESSAGE_INFO, gtk.BUTTONS_CLOSE, message)
        dialog.run()
        dialog.destroy()
        gtk.gdk.threads_leave()
        return

    def _remove_button_clicked_cb(self, button):
        selection = self.view.get_selection()
        selected_rows = selection.get_selected_rows()
        model_filter, paths = selected_rows
        if not paths:
            self.status_bar.push(self.context_id, _('Please select at least one Feed'))
            self.messages_counter += 1

            return

        dialog = gtk.MessageDialog(None,
                               gtk.DIALOG_MODAL,
                               type=gtk.MESSAGE_QUESTION,
                               buttons=gtk.BUTTONS_YES_NO)
        dialog.set_markup("<b>%s</b>" % _('Do you want to delete these feeds?'))
        dialog.connect('response', self._remove_cb, model_filter, paths)
        response = dialog.run()
        dialog.destroy()

    def _remove_cb(self, dialog, response, model_filter, paths):
        if response == gtk.RESPONSE_YES:
            removed = []
            unsubscribe = []
            if len(paths) == len(self.manager.get_feed_summaries()):
                self.export_opml_button.set_sensitive(False)
            for path in paths:
                try:
                    self.manager.remove_feed(model_filter[path][FeedsWindow.FEEDS_MODEL_ID_COLUMN])
                except IOError:
                    self.status_bar.push(self.context_id, _('File error while removing Feed'))
                    self.messages_counter += 1
                    if len(self.manager.get_feed_summaries()) != 0:
                        self.export_opml_button.set_sensitive(True)
                else:
                    removed.append(gtk.TreeRowReference(model_filter, path))
                    # Remove from Google Reader if needed
                    if model_filter[path][FeedsWindow.FEEDS_MODEL_SYNC_COLUMN]:
                        unsubscribe.append(model_filter[path][FeedsWindow.FEEDS_MODEL_HREF_COLUMN])
            
            if self.settings.show_labels_startup:
                self._update_labels_menu()

            if len(unsubscribe):
                message = _('Do you want to remove the selected feeds from Google Reader?')

                dialog = gtk.MessageDialog(None,
                                   gtk.DIALOG_MODAL,
                                   type=gtk.MESSAGE_QUESTION,
                                   buttons=gtk.BUTTONS_YES_NO)
                dialog.set_markup("<b>%s</b>" % message)
                dialog.connect('response', self._remove_from_google_cb, unsubscribe)
                response = dialog.run()
                dialog.destroy()

            store = model_filter.get_model()
            for reference in removed:
                filter_iter = model_filter.get_iter(reference.get_path())
                store.remove(model_filter.convert_iter_to_child_iter(filter_iter))

            # Save data
            self.manager.save()

    def _preferences_cb(self, button):
        settings_window = SettingsWindow(self.manager, self.settings, self._conn_manager, self)

    def _remove_from_google_cb(self, dialog, response, unsubscribe):
        if response == gtk.RESPONSE_YES:
            for feed_url in unsubscribe:
                self.manager.subscribe_feed_google(feed_url, False)

    def _restore_normal_mode(self, button):
        self.view.get_selection().unselect_all()

    def _multiple_update_cb(self, retval, user_data, error, static = {"count" : 0}):
        ''' Simulating a static variable with a default argument hack '''
        num_operations, callback, data, row_reference = user_data

        if row_reference:
            model_filter = self.view.get_model()
            store = model_filter.get_model()
            store_path = model_filter.convert_path_to_child_path(row_reference.get_path())
            store_feed_iter = store.get_iter(store_path)
            feed_id = store.get_value(store_feed_iter, self.FEEDS_MODEL_ID_COLUMN)
            summary = self.manager.get_feed_summary(feed_id)
            feed_data = self.manager.get_feed_data(feed_id)
            if feed_data:
                unread_count = len([entry for entry in feed_data.entries if entry.read == False])
                store.set_value(store_feed_iter, self.FEEDS_MODEL_READ_COLUMN, \
                                    get_visual_unread_text(unread_count))

        static['count'] += 1
        # If all add operations have finished then call the all-done-callback
        if static['count'] == num_operations:
            static['count'] = 0
            if callback:
                callback(data)

    def _update_multiple_feeds(self, callback=None, data=None):

        model_filter = self.view.get_model()
        num_rows = len(model_filter)
        feed_iter = model_filter.get_iter_first()
        while feed_iter:
            # Create a row reference
            row_reference = gtk.TreeRowReference(model_filter, model_filter.get_path(feed_iter))
            # Update feed
            self.manager.update_feed(model_filter.get_value(feed_iter, self.FEEDS_MODEL_ID_COLUMN),self._multiple_update_cb, (num_rows, callback, data, row_reference))
            feed_iter = model_filter.iter_next(feed_iter)


    def _update_all_cb(self, button):
        # Quickly show feedback to user
        self.status_bar.push(self.context_id, _('Updating...'))
        self.messages_counter += 1

        # Ask manager to update feed
        self._update_multiple_feeds(self._all_feeds_updated_cb)

    def _all_feeds_updated_cb(self, data):
        self.status_bar.push(self.context_id, _('Updated'))
        self.messages_counter += 1

        # Do not update read/unread status if all the feeds failed to sync
        synced_feeds = [row[self.FEEDS_MODEL_ID_COLUMN] for row in self.view.get_model() \
                            if row[self.FEEDS_MODEL_SYNC_COLUMN]]
        if len(synced_feeds) == 0:
            return

        # Update read/unread status
        self.status_bar.push(self.context_id, _('Synchronizing read/unread status with Google Reader'))
        self.messages_counter += 1
        self.sync_message = self.status_bar.push(self.context_id, _('Synchronizing read/unread status...'))
        self.manager.sync_google_reader_read_status(self._sync_google_reader_read_status_cb)

    def _export_feed_cb(self, button):

        chooser = gtk.FileChooserDialog('Export feeds', None, gtk.FILE_CHOOSER_ACTION_SAVE, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                    gtk.STOCK_SAVE, gtk.RESPONSE_OK))

        chooser.set_current_folder(constants.HOME_PATH)
        chooser.set_current_name('resistance-feeds.opml')

        #Overwrite the file if already exists
        chooser.set_do_overwrite_confirmation(True)
        chooser.set_default_response(gtk.RESPONSE_OK)

        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            self.status_bar.push(self.context_id, _('Exporting...'))
            self.messages_counter += 1
            self.manager.export_opml(chooser.get_filename(), self._feed_exported_cb)
        elif response == gtk.RESPONSE_CANCEL:
            print 'Closed, no files selected'
        chooser.destroy()

    def _feed_exported_cb(self, retval, user_data, error):
        if not error:
            message = _('Feeds exported')
        else:
            message = _('Error exporting feeds')

        self.status_bar.push(self.context_id, message)
        self.messages_counter += 1

    def _import_feed_cb(self, button):

        #Calling a file chooser
        chooser = gtk.FileChooserDialog(_('Select file to import'), None, gtk.FILE_CHOOSER_ACTION_OPEN,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))

        # Don't like this at all. Isn't there any define in the platform ?
        chooser.set_current_folder(constants.HOME_PATH)
        chooser.set_default_response(gtk.RESPONSE_OK)

        #Filter for opml files
        filter = gtk.FileFilter()
        filter.set_name("OPML")
        filter.add_pattern("*.opml")
        chooser.add_filter(filter)

        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            self.status_bar.push(self.context_id, _('Importing...'))
            self.messages_counter += 1
            self.manager.import_opml(chooser.get_filename(), self._import_opml_cb)
        elif response == gtk.RESPONSE_CANCEL:
            print 'Closed, no files selected'

        chooser.destroy()

    def _import_opml_cb(self, feed_url_list, data, error):
        if error:
            self.status_bar.push(self.context_id, _('Error importing feeds OPML file'))
            self.messages_counter += 1
            return

        if len(feed_url_list) == 0:
            self.status_bar.push(self.context_id, _('No feeds to import in OPML file'))
            self.messages_counter += 1
            return

        self.status_bar.push(self.context_id, _('Imported. Adding...'))
        self.messages_counter += 1
        self._add_multiple_feeds(feed_url_list, callback=self._save_feeds_after_multiple_add)

    def _multiple_add_cb(self, pixbuf_and_data, user_data, error, static = {"count" : 0}):
        ''' Simulating a static variable with a default argument hack '''
        num_operations, callback, data, row_reference = user_data

        self._feed_added_cb(pixbuf_and_data, row_reference, error, stop_progress=False)
        static['count'] += 1
        # If all add operations have finished then call the all-done-callback
        if static['count'] == num_operations:
            self.status_bar.push(self.context_id, _('Imported. Added'))
            self.messages_counter += 1
            static['count'] = 0
            if callback:
                callback(data)
        else:
            pass

    def _add_multiple_feeds(self, urls, sync=False, callback=None, data=None):
        # Quickly show feedback to user
        self.status_bar.push(self.context_id, _('Adding...'))
        self.messages_counter += 1
        for url in urls:
            # Insert a dummy row while information is retrieved
            feed_iter = self._add_dummy_feed(url, sync)
            path = self.view.get_model().get_path(feed_iter)
            row_reference = gtk.TreeRowReference(self.view.get_model(), path)

            # Add feed to manager
            self.manager.add_feed(url, sync, self._multiple_add_cb,
                                  (len(urls), callback, data, row_reference))

    def _subscribe_feed_cb(self, button, subscribe):
        message = _('Subscribing...') if subscribe else _('Unsubscribing...')
        self.status_bar.push(self.context_id, message)
        self.messages_counter += 1

        selection = self.view.get_selection()
        selected_rows = selection.get_selected_rows()
        model_filter, paths = selected_rows
        if not paths:
            self.status_bar.push(self.context_id, _('Please select at least one Feed'))
            self.messages_counter += 1

            return

        self.update_cont = 1
        total = len(paths)
        for path in paths:
            try:
                # Disable buttons while subscription takes place
                self._update_all_button.set_sensitive(False)
                self._sync_feed_button.set_sensitive(False)
                self._sync_feed_remove_button.set_sensitive(False)

                summary = self.manager.get_feed_summary(model_filter[path][FeedsWindow.FEEDS_MODEL_ID_COLUMN])
                self.manager.subscribe_feed_google(summary.href, subscribe, self._feed_subscribed_cb, [summary, subscribe, total, path])

            except IOError:
                self.status_bar.push(self.context_id, _('File error while subscribing Feed'))
                self.messages_counter += 1

    def _feed_subscribed_cb(self, synced, user_data, error):
        feed_data = user_data[0]
        subscribe = user_data[1]
        total = user_data[2]
        path = user_data[3]  

        message = _('Subscribed') if feed_data.sync else _('Unsubscribed')
        self.status_bar.push(self.context_id, message + str(self.update_cont) + '/' + str(total))
        self.messages_counter += 1

        summary = self.manager.get_feed_summary(get_feed_id(feed_data)) 

        self.update_cont += 1
        if not synced:
            if summary.sync:
                message = _('Error removing from Google Reader')
            else:
                message = _('Error adding to Google Reader')
        else:
            summary.sync = subscribe
            if summary.sync:
                message = _('Added to Google Reader')
                sync_icon = google_reader_pixbuf
            else:
                message = _('Removed from Google Reader')
                sync_icon = None

            model_filter = self.view.get_model()
            store = model_filter.get_model()
            store_path = model_filter.convert_path_to_child_path(path)
            store_feed_iter = store.get_iter(store_path)  

            store.set(store_feed_iter, self.FEEDS_MODEL_SYNC_ICON_COLUMN, sync_icon)

        self.status_bar.push(self.context_id, message)
        self.messages_counter += 1

        # Restore sensitiviness
        self._sync_feed_button.set_sensitive(True)
        self._update_all_button.set_sensitive(True)
        self._sync_feed_remove_button.set_sensitive(True)

    def _sync_google_reader_read_status_cb(self, synced, user_data, error):
        if not synced:
            self.status_bar.push(self.context_id, _('Error syncing read status with Google Reader'))
            self.messages_counter += 1
            if user_data:
                user_data[0].set_sensitive(True)
            return
        else:
            self.status_bar.push(self.context_id, _('Synchronized'))
            self.messages_counter += 1

        # TODO: Update counters
        store = self.view.get_model().get_model()
        for row in store:
            if row[self.FEEDS_MODEL_SYNC_COLUMN]:
                feed_data = self.manager.get_feed_data(row[self.FEEDS_MODEL_ID_COLUMN])
                unread_count = len([entry for entry in feed_data.entries if entry.read == False])
                row[self.FEEDS_MODEL_READ_COLUMN] = get_visual_unread_text(unread_count)

        if user_data:
            user_data[0].set_sensitive(True)
        
        if self.sync_message:
            self.status_bar.remove_message(self.context_id, self.sync_message)

    def _all_synchronized_feeds_added_cb(self, user_data):
        ''' Called after adding all the feeds retrieved from Google Reader '''

        label_feeds = user_data[1]
        if len(label_feeds) > 0:
            message = '%s\n%s' % (_('Do you want to retrieve labels from GoogleReader?'),
                                    _('Note: no future synchronization of labels will be performed'))

            gtk.gdk.threads_enter()
            dialog = gtk.MessageDialog(None,
                               gtk.DIALOG_MODAL,
                               type=gtk.MESSAGE_QUESTION,
                               buttons=gtk.BUTTONS_YES_NO)
            dialog.set_markup("<b>%s</b>" % message)
            dialog.connect('response', self._add_labels_confirmation_response_cb, label_feeds)
            response = dialog.run()
            dialog.destroy()
            gtk.gdk.threads_leave()

        # Do not update read/unread status if all the feeds failed to sync
        synced_feeds = 0
        for row in self.view.get_model():
            if row[self.FEEDS_MODEL_ID_COLUMN]:
                synced_feeds += 1

        if not synced_feeds:
            return
        # Update read/unread status
        self.status_bar.push(self.context_id, _('Synchronizing read/unread status with Google Reader'))
        self.messages_counter += 1
        self.manager.sync_google_reader_read_status(self._sync_google_reader_read_status_cb, user_data)

    def _add_labels_confirmation_response_cb(self, dialog, response, label_feeds):
        if response != gtk.RESPONSE_YES:
            return

        all_labels = self.manager.get_label_list()
        for label_name in label_feeds.keys():
            summaries = [summary for summary in self.manager.get_feed_summaries()
                         if summary.href in label_feeds[label_name]]
            feed_ids = [summary.feed_id for summary in summaries]
            label_ids = [label_data[0] for label_data in all_labels if label_data[1] == label_name]
            label_id = self.manager.create_label(label_name) if len(label_ids) == 0 else label_ids[0]
            self.manager.add_feeds_to_label(feed_ids, label_id)

    def _feeds_synchronized(self, retval, user_data, error):
        if retval == None:
            self.status_bar.push(self.context_id, _('Feeds synchronized'))
            self.messages_counter += 1
          
            gtk.gdk.threads_enter()
            dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_INFO, gtk.BUTTONS_CLOSE, _('Authentication error'))
            dialog.run()
            dialog.destroy()            
            gtk.gdk.threads_leave()

            if user_data:
                user_data.set_sensitive(True)

            return

        urls, label_feeds = retval

        if urls == None:
            self.status_bar.push(self.context_id, _('Error synchronizing feeds'))
            self.messages_counter += 1
            if user_data:
                user_data.set_sensitive(True)
            return
        elif urls == []:
            self.status_bar.push(self.context_id, _('No feeds in Google Reader to synchronize'))
            self.messages_counter += 1
            if user_data:
                user_data.set_sensitive(True)
            return

        # Update sync status of current feeds. We use the info from
        # the model in order to properly update the UI
        model = self.view.get_model()
        store = model.get_model()
        for row in store:
            summary = self.manager.get_feed_summary(row[self.FEEDS_MODEL_ID_COLUMN])
            if summary.href in urls:
                if not summary.sync:
                    summary.sync = True
                    row[self.FEEDS_MODEL_SYNC_COLUMN] = True
                    sync_icon = google_reader_pixbuf
                    #Update de UI
                    store_path = model.convert_path_to_child_path(row.path)
                    store_feed_iter = store.get_iter(store_path)  
                    store.set(store_feed_iter, self.FEEDS_MODEL_SYNC_ICON_COLUMN, sync_icon)
                urls.remove(summary.href)
            else:
                if summary.sync:
                    summary.sync = False
                    row[self.FEEDS_MODEL_SYNC_COLUMN] = False
                    sync_icon = None
                    #Update de UI
                    store_path = model.convert_path_to_child_path(row.path)
                    store_feed_iter = store.get_iter(store_path)  

                    store.set(store_feed_iter, self.FEEDS_MODEL_SYNC_ICON_COLUMN, sync_icon)

        if urls:
            # Add feeds to UI asynchronously
            self._add_multiple_feeds(urls, True, self._all_synchronized_feeds_added_cb, [user_data, label_feeds])

        elif user_data:
            user_data.set_sensitive(True)

    def _find_feed_cb(self, button):
        dialog = FindFeedsDialog(self)
        dialog.connect('response', self._find_feed_response_cb)
        dialog.show_all()

    def _find_feed_response_cb(self, dialog, response):
        if response == gtk.RESPONSE_ACCEPT:
            keywords = dialog.entry.get_text()

            # Quickly show feedback to user
            self.find_message = self.status_bar.push(self.context_id, _('Finding...'))

            self.manager.find_feed(keywords, self._found_cb, dialog)
            dialog.set_response_sensitive(gtk.RESPONSE_ACCEPT, False)

            # Disable canceling
            dialog.connect('delete-event', lambda widget,event : True)

    def _save_feeds_after_multiple_add(self, data=None):
        self.manager.save()

    def _find_window_urls_found_cb(self, find_window, urls):
        if len(urls):
            self._add_multiple_feeds(urls, callback=self._save_feeds_after_multiple_add)

    def _found_cb(self, feeds_info, dialog, error):
        if feeds_info == None:
            # Something went wrong
            self.status_bar.push(self.context_id, _('Error finding feeds. Server error.'))
            self.messages_counter += 1
            dialog.destroy()
            return

        news_window = FindWindow(self.manager, self.settings, self._conn_manager, feeds_info, self)
        news_window.show()

        news_window.connect('urls-found', self._find_window_urls_found_cb)

        dialog.set_response_sensitive(gtk.RESPONSE_ACCEPT, True)
        self.status_bar.remove_message(self.context_id, self.find_message)

        dialog.destroy()

    def _save_feeds_after_multiple_add(self, data=None):
        self.manager.save()

    def _add_feed_to_label_cb(self, button):
        dialog = FeedSelectionDialog(self, self.manager, gtk.STOCK_ADD, True, self._filter_label_id)
        dialog.connect('response', self._feeds_selected_cb, True)
        dialog.show()

    def _remove_feed_from_label_cb(self, button):
        dialog = FeedSelectionDialog(self, self.manager, gtk.STOCK_REMOVE, False, self._filter_label_id)
        dialog.connect('response', self._feeds_selected_cb, False)
        dialog.show()

    def _feeds_selected_cb(self, dialog, response, add_to_label):
        if response != gtk.RESPONSE_ACCEPT:
            return

        selected_feeds = dialog.get_selected_feed_ids()
        if add_to_label:
            self.manager.add_feeds_to_label(selected_feeds, self._filter_label_id)
        else:
            self.manager.remove_feeds_from_label(selected_feeds, self._filter_label_id)

        # Update view
        store = self.view.get_model().get_model()
        for row in store:
            if row[FeedsWindow.FEEDS_MODEL_ID_COLUMN] in selected_feeds:
                row[FeedsWindow.FEEDS_MODEL_LABEL_VISIBLE_COLUMN] = add_to_label

        if self.settings.show_labels_startup:
            self._update_labels_menu()

        dialog.destroy()

    def _on_feed_added_update_label(self, manager, feed_id):
        if self._filter_label_id == constants.ALL_LABEL_ID:
            return
        self.manager.add_feeds_to_label([feed_id], self._filter_label_id)

    def _update_labels_menu(self):
        if self._filter_label_id == constants.ALL_LABEL_ID:
            self._add_to_label_button.set_sensitive(False)
            self._remove_from_label_button.set_sensitive(False)
        else:
            feeds_label = self.manager.get_feeds_for_label(self._filter_label_id)
            summaries = self.manager.get_feed_summaries()
            summaries_ids = []
            for summary in summaries:
                summaries_ids.append(summary.feed_id)
            count = 0
            for feed_label_id in feeds_label:
                if feed_label_id in summaries_ids:
                    count += 1

            self._remove_from_label_button.set_sensitive(count != 0)
            self._add_to_label_button.set_sensitive(count != len(summaries))


class FeedSelectionView(gtk.TreeView):
    def __init__(self):
        super(FeedSelectionView, self).__init__()

        text_renderer = gtk.CellRendererText()
        text_renderer.set_property('ellipsize', ELLIPSIZE_END)

        pix_renderer = gtk.CellRendererPixbuf()

        # Add columns
        # Feed icon column
        column = gtk.TreeViewColumn(_('Icon'), pix_renderer, pixbuf = FeedSelectionDialog.FEED_SELECT_MODEL_PIXBUF_COLUMN)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_resizable(True)
        column.set_fixed_width(100)
        self.append_column(column);       

        #Title/subtitle column
        column = gtk.TreeViewColumn(_('Name'), text_renderer, markup = FeedSelectionDialog.FEED_SELECT_MODEL_NAME_COLUMN)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_resizable(True)
        column.set_expand(True)
        self.append_column(column);


class FeedSelectionDialog(gtk.Dialog):
    FEED_SELECT_MODEL_PIXBUF_COLUMN, FEED_SELECT_MODEL_NAME_COLUMN, FEED_SELECT_MODEL_ID_COLUMN = range(3)

    def __init__(self, parent, manager, button_label, exclude, label_id):
        super(FeedSelectionDialog, self).__init__(_('Select Feeds'), None,
                                                  gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                                  (button_label, gtk.RESPONSE_ACCEPT))

        self.set_size_request(600, 480)

        self.area = self.vbox
        self.area.view = FeedSelectionView()

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        self.area.pack_start(scroll, True, True, 0)
        scroll.add(self.area.view)
        scroll.show()

        store = gtk.ListStore(gtk.gdk.Pixbuf, str, int)

        model_filter = store.filter_new()
        self.area.view.set_model (model_filter)
        self.area.view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.area.view.show()

        feed_summaries = manager.get_feed_summaries()
        for summary in feed_summaries:
            has_label = manager.feed_has_label(summary.feed_id, label_id)
            if label_id == constants.ALL_LABEL_ID or \
                    has_label if not exclude else not has_label:
                feed_iter = store.append()
                store.set(feed_iter, FeedSelectionDialog.FEED_SELECT_MODEL_ID_COLUMN, summary.feed_id,
                          FeedSelectionDialog.FEED_SELECT_MODEL_NAME_COLUMN, get_feed_title_markup(summary.title))
                # Favicon
                path = store.get_path(feed_iter)
                row_reference = gtk.TreeRowReference(store, path)
                manager.get_favicon(summary.favicon, self._get_favicon_cb, row_reference)

    def _get_favicon_cb(self, pixbuf, row_reference, error):
        if pixbuf == None:
            return

        store = self.area.view.get_model().get_model()
        feed_iter = store.get_iter(row_reference.get_path())
        store.set(feed_iter, FeedSelectionDialog.FEED_SELECT_MODEL_PIXBUF_COLUMN, pixbuf)

    def _selection_changed(self, selector, user_data):
        rows = selector.get_selected_rows(0)
        self.set_response_sensitive(gtk.RESPONSE_ACCEPT, False if len(rows) == 0 else True)

    def get_selected_feed_ids(self):
        selection = self.area.view.get_selection()
        selected_rows = selection.get_selected_rows()
        model, paths = selected_rows
        
        feed_ids = []
        for path in paths:
            item_iter = self.area.view.get_model().get_iter(path)
            feed_ids.append(self.area.view.get_model().get_value(item_iter, self.FEED_SELECT_MODEL_ID_COLUMN))
        return feed_ids


class NewFeedDialog(gtk.Dialog):

    def __init__(self, parent):
        super(NewFeedDialog, self).__init__(_('New Feed'), None,
                                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                            (_('Add'), gtk.RESPONSE_ACCEPT))

        self.entry = gtk.Entry()
        entry_accessible = self.entry.get_accessible()
        entry_accessible.set_name(_('Entry for new address'))
        self.entry.connect('changed', self._entry_changed_cb)

        caption = gtk.HBox(False, 16)
        label = gtk.Label(_('Address') + ':')
        label_accessible = label.get_accessible()
        label_accessible.set_name(_('Address'))
        label_accessible.add_relationship(atk.RELATION_LABEL_FOR, entry_accessible)
        label_accessible.set_role(atk.ROLE_LABEL)
        caption.pack_start(label, False, False)
        caption.pack_start(self.entry)
        self.vbox.add(caption)

        self.can_accept = False
        self.set_response_sensitive(gtk.RESPONSE_ACCEPT, self.can_accept)

        self.add_events(gtk.gdk.KEY_PRESS_MASK)
        self.connect('key-press-event', self.on_dialog_key_press)
        
    def on_dialog_key_press(self, dialog, event):
        #Accept the dialog if you pulse enter key
        if event.keyval == gtk.keysyms.Return and self.can_accept:                      
            dialog.response(gtk.RESPONSE_ACCEPT)

    def _entry_changed_cb(self, entry):
        self.can_accept = len(entry.get_text()) > 0
        self.set_response_sensitive(gtk.RESPONSE_ACCEPT, self.can_accept)

class EntriesView(gtk.TreeView):

    def __init__(self, feed_title):
        super(EntriesView, self).__init__()

        self.fallback_author = feed_title

        # Add columns
        pix_renderer = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn(_('Icon'), pix_renderer, pixbuf = 0)
        column.set_resizable(True)
        column.set_fixed_width(100)
        self.append_column(column);

        text_renderer = gtk.CellRendererText()
        text_renderer.set_property('ellipsize', ELLIPSIZE_END)
        column = gtk.TreeViewColumn(_('Name'), text_renderer, markup = EntriesWindow.ENTRIES_MODEL_TEXT_COLUMN)
        column.set_resizable(True)
        column.set_expand(True)
        self.append_column(column);

        date_renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('Date'), date_renderer, markup = EntriesWindow.ENTRIES_MODEL_DATE_COLUMN)
        column.set_resizable(True)
        column.set_fixed_width(300)
        self.append_column(column);

    def get_visual_entry_text(self, entry):

        # TODO: show entry.summary ?
        author = get_author_from_item(entry)
        if author == '':
            author = self.fallback_author

        words = entry.title.rsplit(":")
        if len(words) > 1 and author == words[0].lstrip():
            title = words[1].lstrip()
        else:
            title = entry.title

        if 'read' in entry and entry['read'] == True:
             color = ' foreground="grey"'
        else:
             color = ''

        return '<span' + color + '>' \
            + gobject.markup_escape_text(unescape(author)) \
            + '</span>\n<span size="medium" ' + color + '>' \
            + gobject.markup_escape_text(unescape(title)) + '</span>'

    def get_visual_entry_date(self, entry):
        if entry.has_key('updated_parsed') == False:
            if entry.has_key('updated'):
                return '<span size="xx-small">%s</span>' % \
                    entry.updated
            else:
                return ''

        now = time.localtime()

        # Today
        if now.tm_yday == entry.updated_parsed.tm_yday:
            return '<span size="medium">%s</span>' % \
                time.strftime('%X', entry.updated_parsed)
        # This week
        elif now.tm_yday - entry.updated_parsed.tm_yday < 7 and \
                entry.updated_parsed.tm_wday < now.tm_wday:
            return '<span size="medium">%s</span>' % \
                time.strftime('%A', entry.updated_parsed)
        # This year
        elif now.tm_year == entry.updated_parsed.tm_year:
            return '<span size="medium">%s</span>' % \
                time.strftime('%d %B', entry.updated_parsed)
        # Anything else
        else:
            return '<span size="medium">%s</span>' % \
                time.strftime('%x', entry.updated_parsed)

class EntriesWindow(ResistanceWindowContent):

    ENTRIES_MODEL_TEXT_COLUMN = 1
    ENTRIES_MODEL_DATA_COLUMN = 2
    ENTRIES_MODEL_DATE_COLUMN = 3
    ENTRIES_MODEL_DATE_PARSED_COLUMN = 4

    def __init__(self, feed_data, manager, settings, conn_manager, feeds_window, path):
        super(EntriesWindow, self).__init__()

        self.manager = manager
        self.settings = settings
        self.feed_data = feed_data
        self._conn_manager = conn_manager

        self.feed_data = feed_data
        self.feeds_window = feeds_window
        self.path = path
        self.hbox = gtk.HBox()

        self.title_label = gtk.Label(unescape(self.feed_data.feed.title))           
        self.title_label.set_alignment(0.5, 0.5)
        self.hbox.pack_start(self.title_label, True, True)          

        itunes =  'itunes' in self.feed_data.namespaces
            
        # Feeds
        self.view = EntriesView(feed_data.feed.title)
        entries_model = gtk.ListStore(gtk.gdk.Pixbuf, str, gobject.TYPE_PYOBJECT, str, int)
        entries_model.set_sort_column_id(self.ENTRIES_MODEL_DATE_PARSED_COLUMN, gtk.SORT_DESCENDING)
        filter_model = entries_model.filter_new()
        filter_model.set_visible_func(self._row_visible_cb)
        self.view.set_model (filter_model)
        self.view.connect ("row-activated", self._on_entry_activated, itunes)
        self.view.show()

        self.view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.view.connect('button-press-event', self._button_press_handler, itunes)

        self._create_toolbar()
            
        if not itunes:
            self._download_all_button.set_sensitive(False)        

        resistance_window.window_content(self, self.hbox)

        # Draw entries
        self._add_entries()

        self.align = gtk.Alignment(0, 0, 1, 1)
        self.align.set_padding(4, 0 , 16, 16)

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        
        self.pack_start(scroll, True, True, 0)
        scroll.add(self.view)
        scroll.show()
        self.scroll = scroll

        self.status_bar = gtk.Statusbar()      
        self.context_id = self.status_bar.get_context_id('Entrieswindow statusbar')
        self.pack_start(self.status_bar, False, True, 0)
        self.status_bar.show()

        #To count the number of messages
        self.messages_counter = 0
        #Capture the activity to manage the statusbar
        resistance_window.window.connect('key-press-event', self._clear_status_bar)
        resistance_window.window.connect('button-press-event', self._clear_status_bar)
        self.view.connect('button-press-event', self._clear_status_bar)

    def _clear_status_bar(self, widget, event=None):
        gobject.timeout_add(3000, self._clear_messages)

    def _clear_messages(self):
        for message in range(self.messages_counter):
            self.status_bar.pop(self.context_id)

    def _create_toolbar(self):
        self.handlebox = gtk.HandleBox()
        self.toolbar = gtk.Toolbar()
        self.toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        self.toolbar.set_style(gtk.TOOLBAR_BOTH)
        self.toolbar.set_border_width(5)
        self.handlebox.add(self.toolbar)

        agr = resistance_window.resistance_window_agr()

        self._update_feed_button = gtk.ToolButton() 
        self._update_feed_button.set_stock_id(gtk.STOCK_REFRESH)
        self._update_feed_button.set_label(_('Update feed'))
        self._update_feed_button.connect('clicked', self._update_feed_cb)
        self._update_feed_button.connect('clicked', self._clear_status_bar)
        self._update_feed_button.set_tooltip_text( _('Update this feed [Ctrl+R]'))
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>R")
        self._update_feed_button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        separator_1 = gtk.SeparatorToolItem()
        self.toolbar.insert(self._update_feed_button, 0)
        self.toolbar.insert(separator_1, 1) 

        self._all_filter_button = gtk.RadioToolButton(None, gtk.STOCK_DND_MULTIPLE) 
        self._all_filter_button.set_label(_('Show All'))
        self._all_filter_button.set_active(True)
        self._all_filter_button.connect('toggled', self._show_all_cb)
        self._all_filter_button.set_tooltip_text( _('Show all entries [Ctrl+A]'))
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>A")
        self._all_filter_button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)        

        self._unread_filter_button = gtk.RadioToolButton(self._all_filter_button, gtk.STOCK_DND) 
        self._unread_filter_button.set_label(_('Show Unread'))
        self._unread_filter_button.set_active(False)
        self._unread_filter_button.connect('toggled', self._show_unread_cb)
        self._unread_filter_button.set_tooltip_text( _('Show only unread entries [Ctrl+U]'))
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>U")
        self._unread_filter_button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)        

        if self.settings.entries_filter == constants.SHOW_UNREAD_FILTER:
            self._unread_filter_button.set_active(True)

        separator_2 = gtk.SeparatorToolItem()
         
        self.toolbar.insert(self._all_filter_button, 2)
        self.toolbar.insert(self._unread_filter_button, 3)
        self.toolbar.insert(separator_2, 4) 

        self._mark_read_button = gtk.ToolButton() 
        self._mark_read_button.set_stock_id(gtk.STOCK_APPLY)
        self._mark_read_button.set_label(_('Mark read'))
        self._mark_read_button.connect('clicked', self._mark_read_button_clicked_cb, True)
        self._mark_read_button.connect('clicked', self._clear_status_bar)
        self._mark_read_button.set_tooltip_text( _('Choose entries to mark as read [Ctrl+M]'))
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>M")
        self._mark_read_button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        self._mark_not_read_button = gtk.ToolButton() 
        self._mark_not_read_button.set_stock_id(gtk.STOCK_CANCEL)
        self._mark_not_read_button.set_label(_('Mark unread'))
        self._mark_not_read_button.connect('clicked', self._mark_read_button_clicked_cb, False)
        self._mark_not_read_button.connect('clicked', self._clear_status_bar)
        self._mark_not_read_button.set_tooltip_text( _('Choose entries to mark as not read [Ctrl+N]'))
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>N")
        self._mark_not_read_button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        self.toolbar.insert(self._mark_read_button, 5)
        self.toolbar.insert(self._mark_not_read_button, 6)

        separator_3 = gtk.SeparatorToolItem()
        self.toolbar.insert(separator_3, 7) 

        self._download_all_button = gtk.ToolButton()
        self._download_all_button.set_stock_id(gtk.STOCK_OPEN)
        self._download_all_button.set_label(_('Download all'))
        self._download_all_button.connect('clicked', self._download_all_items_cb)
        self._download_all_button.connect('clicked', self._clear_status_bar)
        self._download_all_button.set_tooltip_text( _('Download the files [Ctrl+D]'))
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>D")
        self._download_all_button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        self.toolbar.insert(self._download_all_button, 8)

        self._sync_feed_button = gtk.ToolButton() 
        google_icon = gtk.gdk.pixbuf_new_from_file(constants.GOOGLE_READER_ICON_FILE)
        google_image = gtk.Image()
        google_image.set_from_pixbuf(google_icon)
        self._sync_feed_button.set_icon_widget(google_image)
        summary = self.manager.get_feed_summary(get_feed_id(self.feed_data))
        label = _('Remove GReader') if summary.sync else _('Add GReader')
        self._sync_feed_button.set_label(label)
        self._sync_feed_button.connect('clicked', self._subscribe_feed_cb)
        self._sync_feed_button.connect('clicked', self._clear_status_bar)
        self._sync_feed_button.set_tooltip_text( _('Add or remove the feed to Google Reader [Ctrl+G] Use menu Settings to add your user and password'))
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>G")
        self._sync_feed_button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        self.toolbar.insert(self._sync_feed_button, 9)

        separator_4 = gtk.SeparatorToolItem()
        self.toolbar.insert(separator_4, 10) 

        self.pack_start(self.handlebox, False, False, 0)
        self.toolbar.show_all()
        self.handlebox.show_all()

    def _show_unread_cb(self, button, button_type='radiobutton'):
        if button_type=='radiobutton' and not button.get_active():
            return
        elif button_type=='menu':
            self._unread_filter_button.set_active(True)    
        self.settings.entries_filter = constants.SHOW_UNREAD_FILTER
        self.view.get_model().refilter()

    def _show_all_cb(self, button, button_type='radiobutton'):
        if button_type=='radiobutton' and not button.get_active():
            return
        elif button_type=='menu':
            self._all_filter_button.set_active(True)
        self.settings.entries_filter = constants.SHOW_ALL_FILTER
        self.view.get_model().refilter()

    def _row_visible_cb(self, model, iter):
        if self.settings.entries_filter == constants.SHOW_ALL_FILTER:
            return True

        entry = model.get_value(iter, self.ENTRIES_MODEL_DATA_COLUMN)
        if not entry:
            return False

        return not entry.read

    def _add_entries(self):
        model = self.view.get_model().get_model()

        for entry in self.feed_data.entries:
            entry_iter = model.append()
            if 'updated_parsed' in entry:
                date = entry.updated_parsed
            elif 'published_parsed' in entry:
                date = entry.published_parsed
            elif 'created_parsed' in entry:
                date = entry.created_parsed
            else:
                date = 0
            model.set(entry_iter,
                      self.ENTRIES_MODEL_TEXT_COLUMN, self.view.get_visual_entry_text(entry),
                      self.ENTRIES_MODEL_DATA_COLUMN, entry,
                      self.ENTRIES_MODEL_DATE_COLUMN, self.view.get_visual_entry_date(entry),
                      self.ENTRIES_MODEL_DATE_PARSED_COLUMN, calendar.timegm(date) if date else 0)

    def _button_press_handler(self, treeview, event, itunes):
        if event.button == 3:
            # Figure out which item they right clicked on
            path = treeview.get_path_at_pos(int(event.x),int(event.y))
            # Get the selection
            selection = self.view.get_selection()

            # Get the selected path(s)
            selected_rows = selection.get_selected_rows()

            if path is None:
                self._context_menu(treeview, event, itunes)
                return True
            # If they didnt right click on a currently selected row, change the selection
            elif path[0] not in selected_rows[1]:
                selection.unselect_all()
                selection.select_path(path[0])
                
            if selection.count_selected_rows() > 0:       
                self._context_menu(treeview, event, itunes, path)

            return True

    def _context_menu(self, widget, event, itunes, path=None, data=None):
        menu = gtk.Menu()

        mark_read_item = gtk.MenuItem('Mark Read')
        mark_read_item.set_sensitive(False)
        mark_read_item.connect('activate', self._mark_read_button_clicked_cb, True)
        menu.append(mark_read_item)

        mark_unread_item = gtk.MenuItem('Mark Unread')
        mark_unread_item.set_sensitive(False)
        mark_unread_item.connect('activate', self._mark_read_button_clicked_cb, False)
        menu.append(mark_unread_item)

        download_item = gtk.MenuItem('Download')
        if not itunes:
            download_item.set_sensitive(False)
        download_item.connect('activate', self._download_item_cb)
        menu.append(download_item)

        separator = gtk.SeparatorMenuItem()
        menu.append(separator)

        menu_item = gtk.MenuItem('Update Feed')
        menu_item.connect('activate', self._update_feed_cb)
        menu.append(menu_item)

        menu_item = gtk.MenuItem('Show All')
        menu_item.connect('activate', self._show_all_cb, 'menu')
        menu.append(menu_item)

        menu_item = gtk.MenuItem('Show Unread')
        menu_item.connect('activate', self._show_unread_cb, 'menu')
        menu.append(menu_item)

        download_all_item = gtk.MenuItem('Download All')
        if not itunes:
            download_all_item.set_sensitive(False)
        download_all_item.connect('activate', self._download_all_items_cb)
        menu.append(download_all_item)

        menu_item = gtk.MenuItem('Add to Google Reader')
        menu_item.connect('activate', self._subscribe_feed_cb)
        menu.append(menu_item)

        if path:
            mark_read_item.set_sensitive(True)
            mark_unread_item.set_sensitive(True)

        menu.show_all()

        menu.popup(None, None, None, event.button, event.get_time())
        return True

    def _on_entry_activated(self, treeview, path, column, itunes):
        item_window = ItemWindow(self.feed_data, self.manager, self.settings, self._conn_manager, treeview.get_model(), path, itunes)

        item_window.connect('item-read', self._item_read_cb)
        item_window.set_item_from_model(treeview.get_model(), path)
        item_window.show()

    def _item_read_cb(self, item_window, path):
        filter_model = self.view.get_model()
        entry = filter_model[path][self.ENTRIES_MODEL_DATA_COLUMN]

        # Set item as read and update the UI
        entry['read'] = True
        child_path = filter_model.convert_path_to_child_path(path)
        filter_model.get_model()[child_path][self.ENTRIES_MODEL_TEXT_COLUMN] = self.view.get_visual_entry_text(entry)

        feed_id = get_feed_id(self.feed_data)
        summary = self.manager.get_feed_summary(feed_id)

        # Mark item as read in Google Reader. Do it in an idle as we
        # don't want to delay the item rendering
        if summary.sync and self._conn_manager.is_online():
            glib.idle_add(self._mark_as_read_google_idle_cb, entry)

        # TODO: Update counters
        model_filter = self.feeds_window.view.get_model()
        store = model_filter.get_model()
        store_path = model_filter.convert_path_to_child_path(self.path)
        store_feed_iter = store.get_iter(store_path)  
        feed_data = self.manager.get_feed_data(feed_id)

        unread_count = len([entry for entry in feed_data.entries if entry.read == False])

        store.set(store_feed_iter, self.feeds_window.FEEDS_MODEL_READ_COLUMN, get_visual_unread_text(unread_count))

    def _mark_as_read_google_idle_cb(self, entry):
        if not self._conn_manager.is_online():
            return

        self.manager.mark_as_read_synchronize(self.feed_data.href, entry.link, True,
                                              self._mark_as_read_google_cb)
        return False

    def _mark_as_read_google_cb(self, synced, user_data, error):
        if not synced:
            self.status_bar.push(self.context_id, _('Error syncing read status with Google Reader'))
            self.messages_counter += 1

    def _update_feed_cb(self, button):
        url = self.feed_data.href

        # Quickly show feedback to user
        self.status_bar.push(self.context_id, _('Updating...'))
        self.messages_counter += 1
        button.set_sensitive(False)

        # Ask manager to update feed
        self.manager.update_feed(get_feed_id(self.feed_data), self._feed_updated_cb, None)

    def _feed_updated_cb(self, retval, data, error):
        # Update read/unread status if the feed was subscribed
        summary = self.manager.get_feed_summary(get_feed_id(self.feed_data))
        if summary.sync:
            self.status_bar.push(self.context_id, _('Synchronizing read/unread status with Google Reader'))
            self.messages_counter += 1
            self.manager.sync_google_reader_read_status(self._sync_google_reader_read_status_cb)
        else:
            self.status_bar.push(self.context_id, _('Updated'))
            self.messages_counter += 1
            self._update_feed_button.set_sensitive(True)

        self._update_feed_button.set_sensitive(True)

        self.view.get_model().get_model().clear()
        self._add_entries()

    def _subscribe_feed_cb(self, button):
        summary = self.manager.get_feed_summary(get_feed_id(self.feed_data))
        message = _('Unubscribing...') if summary.sync else _('Subscribing...')
        self.status_bar.push(self.context_id, message)
        self.messages_counter += 1

        # Disable buttons while subscription takes place
        self._update_feed_button.set_sensitive(False)
        self._sync_feed_button.set_sensitive(False)

        self.manager.subscribe_feed_google(summary.href, not summary.sync, self._feed_subscribed_cb)

    def _feed_subscribed_cb(self, synced, user_data, error):
        summary = self.manager.get_feed_summary(get_feed_id(self.feed_data))
        message = _('Subscribed') if summary.sync else _('Unsubscribed')
        self.status_bar.push(self.context_id, message)
        self.messages_counter += 1

        if not synced:
            if summary.sync:
                message = _('Error removing from Google Reader')
            else:
                message = _('Error adding to Google Reader')
        else:
            summary.sync = not summary.sync
            if summary.sync:
                message = _('Added to Google Reader')
                sync_icon = google_reader_pixbuf
            else:
                message = _('Removed from Google Reader')
                sync_icon = None

            model_filter = self.feeds_window.view.get_model()
            store = model_filter.get_model()
            store_path = model_filter.convert_path_to_child_path(self.path)
            store_feed_iter = store.get_iter(store_path)  

            store.set(store_feed_iter, self.feeds_window.FEEDS_MODEL_SYNC_ICON_COLUMN, sync_icon)

        self.status_bar.push(self.context_id, message)
        self.messages_counter += 1

        # Update the menu
        label = _('Remove GReader') if summary.sync else _('Add GReader')
        self._sync_feed_button.set_label(label)

        # Restore sensitiviness
        self._sync_feed_button.set_sensitive(True)
        self._update_feed_button.set_sensitive(True)

    def _sync_google_reader_read_status_cb(self, synced, user_data, error):
        self.status_bar.push(self.context_id, _('Synchronized read/unread status'))
        self.messages_counter += 1
        self._update_feed_button.set_sensitive(True)

        if not synced:
            self.status_bar.push(self.context_id, _('Error syncing read status with Google Reader'))
            self.messages_counter += 1
            return

        #Update UI
        model_filter = self.view.get_model()
        store = model_filter.get_model()
        for row in store:
            entry = row[self.ENTRIES_MODEL_DATA_COLUMN]
            row[self.ENTRIES_MODEL_TEXT_COLUMN] = self.view.get_visual_entry_text(entry)

    def _mark_read_button_clicked_cb(self, button, read):
        selection = self.view.get_selection()
        selected_rows = selection.get_selected_rows()
        model, paths = selected_rows
        if not paths:
            self.status_bar.push(self.context_id, _('Please select at least one Entry'))
            self.messages_counter += 1

            return

        online = self._conn_manager.is_online()
        summary = self.manager.get_feed_summary(get_feed_id(self.feed_data))
        for path in paths:
            entry = model[path][self.ENTRIES_MODEL_DATA_COLUMN]
            entry.read = read
            child_path = model.convert_path_to_child_path(path)
            model.get_model()[child_path][self.ENTRIES_MODEL_TEXT_COLUMN] = self.view.get_visual_entry_text(entry)
            if summary.sync and online:
                self.manager.mark_as_read_synchronize(self.feed_data.href, model[path][2].link,
                                                      read, self._mark_as_read_sync_cb)

        # TODO: Update counters
        model_filter = self.feeds_window.view.get_model()
        store = model_filter.get_model()
        store_path = model_filter.convert_path_to_child_path(self.path)
        store_feed_iter = store.get_iter(store_path)  
        feed_id = get_feed_id(self.feed_data)
        summary = self.manager.get_feed_summary(feed_id)
        feed_data = self.manager.get_feed_data(feed_id)

        unread_count = len([entry for entry in feed_data.entries if entry.read == False])

        store.set(store_feed_iter, self.feeds_window.FEEDS_MODEL_READ_COLUMN, get_visual_unread_text(unread_count))

    def _mark_as_read_sync_cb(self, synced, user_data, error):
        if not synced:
            self.status_bar.push(self.context_id, _('Error syncing read status with Google Reader'))
            self.messages_counter += 1

    def _download_all_items_cb(self, button):
        folder = self.settings.auto_download_folder

        urls = []
        paths_files = []
        for entry in self.feed_data.entries:
            try:
                url = entry['enclosures'][0]['href']
                urls.append(url)
                paths_files.append(folder + os.path.basename(urllib.url2pathname(url)))
            except:
                pass

        self.status_bar.push(self.context_id, _('Downloading...'))
        self.messages_counter += 1

        self.manager.download_all_items(urls, paths_files, self._all_items_downloaded_cb)

    def _all_items_downloaded_cb(self, downloaded, user_data, error):
        if downloaded:
            message = _('Items downloaded')
        else:
            message = _('Error downloading items')
        self.status_bar.push(self.context_id, message)
        self.messages_counter += 1

    def _download_item_cb(self, button):
        selection = self.view.get_selection()
        selected_rows = selection.get_selected_rows()
        model, paths = selected_rows
     
        self.status_bar.push(self.context_id, _('Downloading...'))
        self.messages_counter += 1
        folder = self.settings.auto_download_folder

        self.download_cont = 1
        total = len(paths)
        for path in paths:
            item_iter = self.view.get_model().get_iter(path)
            item = self.view.get_model().get_value(item_iter, self.ENTRIES_MODEL_DATA_COLUMN)
              
            url_file = item.enclosures[0]['href']
            file = os.path.basename(urllib.url2pathname(url_file))
             
            self.manager.download_item(url_file, folder+file, self._item_downloaded_cb, total)

    def _item_downloaded_cb(self, downloaded, user_data, error):
        if downloaded:
            message = _('Item downloaded')
        else:
            message = _('Error downloading item')
        self.status_bar.push(self.context_id, message + ' ' + str(self.download_cont) + '/' + str(user_data))
        self.messages_counter += 1

        self.download_cont = self.download_cont + 1

    def _restore_normal_mode(self):
        resistance_window.return_cb()

class ItemWindowHeader(gtk.HBox):

    def __init__(self, homogeneous, spacing, itunes):
        super(ItemWindowHeader, self).__init__(homogeneous, spacing)

        # Header
        header_vbox = gtk.VBox()
        navigation_hbox = gtk.HBox(False, 0)
        open_web_browser = gtk.HBox(False, 0)

        # Author and URL
        self.title = gtk.Label('')
        self.title.set_alignment(0, 0.5)
        self.title.set_ellipsize(ELLIPSIZE_END)
        header_vbox.pack_start(self.title, True, False)
        self.title.show()
        header_vbox.show()

        agr = resistance_window.resistance_window_agr()

        #Download
        if itunes:
            self._download_button = gtk.Button(_('Download'))
            self._download_button.set_tooltip_text( _('Download the item [Ctrl+D] Use menu Settings to configure a folder '))
            key, mod = gtk.accelerator_parse("<Control>D")
            self._download_button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)
            open_web_browser.pack_start(self._download_button, False, False, 0)

        #Open web browser with the item
        self.button_open = gtk.Button(_('Open browser'))
        self.button_open.set_tooltip_text( _('Open the item in a web browser [Ctrl+O]'))
        key, mod = gtk.accelerator_parse("<Control>O")
        self.button_open.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)        

        open_web_browser.pack_start(self.button_open, False, False, 0)
        open_web_browser.show_all()

        # Navigation buttons. Sizes are important. We set the size of the icon but
        # we let the button grow as needed
        self.button_up = gtk.Button()
        button_up_img = gtk.Image()
        button_up_img.set_from_icon_name(gtk.STOCK_GO_UP, gtk.ICON_SIZE_MENU)
        self.button_up.set_image(button_up_img)
        self.button_up.set_tooltip_text( _('Read the previous item [Ctrl+Up-arrow]'))
        key, mod = gtk.accelerator_parse("<Control>Up")
        self.button_up.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        self.button_down = gtk.Button()
        button_down_img = gtk.Image()
        button_down_img.set_from_icon_name(gtk.STOCK_GO_DOWN, gtk.ICON_SIZE_MENU)
        self.button_down.set_image(button_down_img)
        self.button_down.set_tooltip_text( _('Read the next item [Ctrl+Down-arrow]'))
        key, mod = gtk.accelerator_parse("<Control>Down")
        self.button_down.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        navigation_hbox.pack_start(self.button_up, False, False, 0)
        navigation_hbox.pack_start(self.button_down, False, False, 0)
        navigation_hbox.show_all()

        self.pack_start(header_vbox, True, True)
        self.pack_start(open_web_browser, False, False)
        self.pack_start(navigation_hbox, False, False)

    def _link_button_clicked(self, link_button):
        print 'Open ' + link_button.get_uri()

    def set_item(self, item):

        self.item = item

        self.title.set_markup('<span size="medium">  ' + unescape(item.title) + '</span>')

class ItemWindow(ResistanceWindowContent):
    __gsignals__ = {
        "item-read": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT, )),
        }

    def __init__(self, feed_data, manager, settings, conn_manager, model, path, itunes):
        super(ItemWindow, self).__init__()

        self.feed_data = feed_data
        self.manager = manager
        self.settings = settings
        self._conn_manager = conn_manager

        # Header
        self.item_window_header = ItemWindowHeader(False, 16, itunes)
        self.item_window_header.button_up.connect("clicked", self._up_button_clicked)
        self.item_window_header.button_up.connect("clicked", self._clear_status_bar)
        self.item_window_header.button_down.connect("clicked", self._down_button_clicked)
        self.item_window_header.button_down.connect("clicked", self._clear_status_bar)
        self.item_window_header.button_open.connect("clicked", self._open_button_clicked, model, path)
        self.item_window_header.button_open.connect("clicked", self._clear_status_bar)
        if itunes:
            self.item_window_header._download_button.connect("clicked", self._download_item_cb)

        resistance_window.window_content(self, self.item_window_header)

        # HTML renderer
        self.view = WebView()
        self.view.set_full_content_zoom(True)

        # Disable text selection
        self.view.connect("motion-notify-event", lambda w, ev: True)

        # Set some settings
        wbk_settings = self.view.get_settings()
        wbk_settings.set_property('default_font_size', self.settings.default_font_size)
        wbk_settings.set_property('auto-load-images', self.settings.auto_load_images)
        wbk_settings.set_property('auto-shrink-images', True)

        self.view.show()

        self.item_window_header.show()

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        
        self.pack_start(scroll, True, True, 0)
        scroll.add(self.view)
        scroll.show()

        #Status bar
        self.status_bar = gtk.Statusbar()      
        self.context_id = self.status_bar.get_context_id('Itemwindow statusbar')
        self.pack_start(self.status_bar, False, True, 0)
        self.status_bar.show()

        #To count the number of messages
        self.messages_counter = 0
        #Capture the activity to manage the statusbar
        self.view.connect('button-press-event', self._clear_status_bar)

    def _clear_status_bar(self, widget, event=None):
        gobject.timeout_add(3000, self._clear_messages)

    def _clear_messages(self):
        for message in range(self.messages_counter):
            self.status_bar.pop(self.context_id)

    def _up_button_clicked(self, button):

        # http://faq.pygtk.org/index.py?req=show&file=faq13.051.htp
        path = self.model.get_path(self.model_iter)
        position = path[-1]
        if position == 0:
            return
        prev_path = list(path)[:-1]
        prev_path.append(position - 1)
        self.model_iter = self.model.get_iter(tuple(prev_path))

        if self.model_iter == None:
            return

        item = self.model.get_value(self.model_iter, EntriesWindow.ENTRIES_MODEL_DATA_COLUMN)
        self.set_item(item)

    def _down_button_clicked(self, button):

        if self.model_iter == None:
            return

        self.model_iter = self.model.iter_next(self.model_iter)

        item = self.model.get_value(self.model_iter, EntriesWindow.ENTRIES_MODEL_DATA_COLUMN)
        self.set_item(item)

    def _open_button_clicked(self, button, model, path):
        
        self.model = model
        self.model_iter = model.get_iter(path)

        item_iter = model.get_iter(path)
        item = model.get_value(item_iter, EntriesWindow.ENTRIES_MODEL_DATA_COLUMN)
        self._open_url(item['id'])

    def _open_url(self, url):
        subprocess.call(['xdg-open', url])

    def set_item_from_model(self, model, path):

        self.model = model
        self.model_iter = model.get_iter(path)

        item_iter = model.get_iter(path)
        item = model.get_value(item_iter, EntriesWindow.ENTRIES_MODEL_DATA_COLUMN)

        self.item_window_header.set_item(item)
        self.set_item(item)

    def set_item(self, item):

        # Set item in header
        self.item_window_header.set_item(item)

        # Get content type and body
        content_type = 'text/html'
        if 'summary' in item:
            if 'summary_detail' in item and 'type' in item.summary_detail:
                content_type = item.summary_detail.type
            body = item.summary
        elif 'content' in item:
            # We are only considering the first content. TODO check more?
            if 'type' in item.content[0]:
                content_type = item.content[0].type
            body = item.content[0].value
        else:
            # Should never happen
            body = _('No text')

        # Write HTML
        self.view.load_string(body.encode(self.feed_data.encoding), content_type, self.feed_data.encoding, '')
        self.view.connect('new-window-policy-decision-requested',self.on_click_uri)

        # Update button sensitiviness
        path = self.model.get_path(self.model_iter)
        position = path[-1]
        if position == 0:
            self.item_window_header.button_up.set_sensitive(False)
        elif position == len(self.model) - 1:
            self.item_window_header.button_down.set_sensitive(False)
            toolbar_button_list[1].set_sensitive(False)
        else:
            self.item_window_header.button_up.set_sensitive(True)
            self.item_window_header.button_down.set_sensitive(True)

        # Mark item as read
        item['read'] = True

        # Emit item read
        self.emit('item-read', self.model.get_path(self.model_iter))

    def on_click_uri(self, view, frame, request, action, policy):
        uri = request.get_uri()
        self._open_url(uri)

    def _download_item_cb(self, button):
        item = self.item_window_header.item
        url_file = item.enclosures[0]['href']
        file = os.path.basename(urllib.url2pathname(url_file))
        folder = self.settings.auto_download_folder

        self.status_bar.push(self.context_id, _('Downloading...'))
        self.messages_counter += 1
        self.manager.download_item(url_file, folder+file, self._item_downloaded_cb)

    def _item_downloaded_cb(self, downloaded, user_data, error):
        if downloaded:
            message = _('Item downloaded')
        else:
            message = _('Error downloading item')
        self.status_bar.push(self.context_id, message)
        self.messages_counter += 1

class FindFeedsDialog(gtk.Dialog):
    def __init__(self, parent):
        super(FindFeedsDialog, self).__init__(_('Find Feeds'), None,
                                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                            (_('Find'), gtk.RESPONSE_ACCEPT))


        self.entry = gtk.Entry()
        entry_accessible = self.entry.get_accessible()
        entry_accessible.set_name(_('Entry for keywords'))
        self.entry.connect('changed', self._entry_changed_cb)

        caption = gtk.HBox(False, 16)
        label = gtk.Label(_('Keywords') + ':')
        label_accessible = label.get_accessible()
        label_accessible.set_name(_('Keywords'))
        label_accessible.add_relationship(atk.RELATION_LABEL_FOR, entry_accessible)
        label_accessible.set_role(atk.ROLE_LABEL)
        caption.pack_start(label, False, False)
        caption.pack_start(self.entry)
        self.vbox.add(caption)

        self.can_accept = False
        self.set_response_sensitive(gtk.RESPONSE_ACCEPT, self.can_accept)

        self.add_events(gtk.gdk.KEY_PRESS_MASK)
        self.connect('key-press-event', self.on_dialog_key_press)
        
    def on_dialog_key_press(self, dialog, event):
        #Accept the dialog if you pulse enter key
        if event.keyval == gtk.keysyms.Return and self.can_accept:                      
            dialog.response(gtk.RESPONSE_ACCEPT)

    def _entry_changed_cb(self, entry):
        self.can_accept = len(entry.get_text()) > 0
        self.set_response_sensitive(gtk.RESPONSE_ACCEPT, self.can_accept)

    def _delete_event_cb(self, widget, event):
        return True #stop the signal propagation

class FindView(gtk.TreeView):

    FIND_SITE_VIEW = 0

    def __init__(self):
        super(FindView, self).__init__()

        # Add columns
        text_renderer = gtk.CellRendererText()
        text_renderer.set_property('ellipsize', ELLIPSIZE_END)
        column = gtk.TreeViewColumn('Name', text_renderer, markup=self.FIND_SITE_VIEW)
        column.set_expand(True)
        self.append_column(column)

class FindWindow(ResistanceWindowContent):
    __gsignals__ = {
        "urls-found": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT, )),
        }

    FIND_MODEL_SITE_COLUMN = 0
    FIND_MODEL_URL_COLUMN = 1

    def __init__(self, manager, settings, conn_manager, feedsinfo, feedsWindow):
        super(FindWindow, self).__init__()

        self.manager = manager
        self.settings = settings
        self._conn_manager = conn_manager

        self.feeds_info = feedsinfo

        self.hbox = gtk.HBox()

        self.button_add = gtk.Button(_("Add"))
        self.button_add.connect('clicked', self._add_button_clicked_cb)
        self.button_add.set_alignment(0, 0)
        self.title_label = gtk.Label(_('Select Feeds to add'))
        self.title_label.set_alignment(0.5, 0.5)

        self.hbox.pack_start(self.title_label, True, True)          
        self.hbox.pack_start(self.button_add, False, False)

        resistance_window.window_content(self, self.hbox)

        self.view = FindView()
        self.view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.view.get_selection().unselect_all()

        self.view.set_model (gtk.ListStore(str, str))

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)

        self.pack_start(scroll, True, True, 0)
        scroll.add(self.view)
        scroll.show()

        store = self.view.get_model()

        for feed_info in self.feeds_info:
            feed_iter = store.append()

            store.set(feed_iter,
                      self.FIND_MODEL_SITE_COLUMN, gobject.markup_escape_text(unescape(feed_info['sitename'])),
                      self.FIND_MODEL_URL_COLUMN, feed_info['dataurl'])

        self.view.show()

        self.status_bar = gtk.Statusbar()      
        self.context_id = self.status_bar.get_context_id('Feedswindow statusbar')
        self.pack_start(self.status_bar, False, True, 0)
        self.status_bar.show()

        #To count the number of messages
        self.messages_counter = 0
        #Capture the activity to manage the statusbar
        self.view.connect('button-press-event', self._clear_status_bar)

    def _clear_status_bar(self, widget, event=None):
        gobject.timeout_add(3000, self._clear_messages)

    def _clear_messages(self):
        for message in range(self.messages_counter):
            self.status_bar.pop(self.context_id)    

    def _add_button_clicked_cb(self, button):
        selection = self.view.get_selection()
        selected_rows = selection.get_selected_rows()
        model, paths = selected_rows
        if not paths:
            self.status_bar.push(self.context_id, _('Please select at least one Feed'))
            self.messages_counter += 1
            return

        urls = [model[path][self.FIND_MODEL_URL_COLUMN] for path in paths]

        self.emit('urls-found', urls)
        resistance_window.return_cb()

class SettingsWindow(ResistanceWindowContent):

    def __init__(self, manager, settings, conn_manager, feedswindow):
        super(SettingsWindow, self).__init__()

        self.manager = manager
        self.settings = settings
        self._conn_manager = conn_manager
        self.feedswindow = feedswindow

        self.hbox = gtk.HBox()
        self.button_save = gtk.Button(_('Save'))
        self.button_save.connect('clicked', self._preferences_response_cb)
        self.button_save.set_alignment(0, 0)
        title_label = gtk.Label(_('Settings'))
        title_label.set_alignment(0.5, 0.5)

        self.hbox.pack_start(title_label, True, True)          
        self.hbox.pack_start(self.button_save, False, False)

        resistance_window.window_content(self, self.hbox)        

        separator = gtk.HSeparator()
        self.pack_start(separator, False, True, 0)
        separator.show()

        self.vbox = gtk.VBox()

        #Visual settings (group)
        subtitle_label = gtk.Label(_('Visual Settings'))
        subtitle_label.set_alignment(0.01, 0.5)

        self.vbox.pack_start(subtitle_label, False, False, 10) 

        labels_group = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)

        #Screen orientation
        hbox = gtk.HBox()
        label = gtk.Label(_('Screen orientation'))
        label.set_alignment(xalign=0, yalign=0.5)
        labels_group.add_widget(label)
        hbox.pack_start(label, False, True, 35)

        orientation_hbox = gtk.HBox()
        button = gtk.RadioButton(None, "Automatic")
        #button.connect("toggled", self.callback, "radio button 1")
        orientation_hbox.pack_start(button, False, True, 5)
        button.show()
   
        button = gtk.RadioButton(button, "Landscape")
        #button.connect("toggled", self.callback, "radio button 2")
        button.set_active(True)
        orientation_hbox.pack_start(button, False, True, 5)
        button.show()
   
        button = gtk.RadioButton(button, "Portrait")
        #button.connect("toggled", self.callback, "radio button 3")
        orientation_hbox.pack_start(button, False, True, 5)
        button.show()

        hbox.pack_start(orientation_hbox, False, True)
        self.vbox.pack_start(hbox, False, False) 
 
        hbox.set_sensitive(False)

        #Default font size
        hbox = gtk.HBox()
        label = gtk.Label(_('Default font size'))
        label_accessible = label.get_accessible()
        label_accessible.set_name(_('Default font size'))
        label.set_alignment(xalign=0, yalign=0.5)
        labels_group.add_widget(label)
        hbox.pack_start(label, False, True, 35)

        self.font_size_combobox = gtk.combo_box_new_text()
        combobox_accessible = self.font_size_combobox.get_popup_accessible()
        combobox_accessible.set_role(atk.ROLE_COMBO_BOX)
        label_accessible.add_relationship(atk.RELATION_LABEL_FOR, combobox_accessible)
        for i in constants.font_size_range:
            self.font_size_combobox.append_text(str(i))
        self.font_size_combobox.set_active(0)
        hbox.pack_start(self.font_size_combobox, False, True)
        self.vbox.pack_start(hbox, False, False) 

        #Auto load images
        hbox = gtk.HBox()
        self.auto_load_images = gtk.CheckButton(_('Auto load images'))
        self.auto_load_images.set_alignment(xalign=0, yalign=0.5)
        labels_group.add_widget(self.auto_load_images)
        self.auto_load_images.show()
        hbox.pack_start(self.auto_load_images, False, True, 35)

        self.vbox.pack_start(hbox, False, False)

        #Labels
        hbox = gtk.HBox()
        self.show_labels_startup = gtk.CheckButton(_('Show labels at start-up'))
        self.show_labels_startup.set_alignment(xalign=0, yalign=0.5)
        labels_group.add_widget(self.show_labels_startup)
        self.show_labels_startup.show()
        hbox.pack_start(self.show_labels_startup, False, True, 35)

        self.vbox.pack_start(hbox, False, False)

        #Update settings (group)
        subtitle_label = gtk.Label(_('Update Settings'))
        subtitle_label.set_alignment(0.01, 0.5)

        self.vbox.pack_start(subtitle_label, False, False, 10)

        #Automatically download
        hbox = gtk.HBox()
        self.automatic_download = gtk.CheckButton(_('Automatically download Podcasts'))
        self.automatic_download.set_alignment(xalign=0, yalign=0.5)
        labels_group.add_widget(self.automatic_download)
        self.automatic_download.show()
        hbox.pack_start(self.automatic_download, False, True, 35)

        self.vbox.pack_start(hbox, False, False)

        #Auto download folder
        hbox = gtk.HBox()
        label = gtk.Label(_('Auto download folder'))
        label_accessible = label.get_accessible()
        label_accessible.set_name(_('Auto download folder'))
        label_accessible.set_role(atk.ROLE_LABEL)
        label.set_alignment(xalign=0, yalign=0.5)
        labels_group.add_widget(label)
        hbox.pack_start(label, False, True, 35)

        self.entry_folder = gtk.Entry()
        entry_accessible = self.entry_folder.get_accessible()
        entry_accessible.set_name(_('Entry for auto download folder'))
        label_accessible.add_relationship(atk.RELATION_LABEL_FOR, entry_accessible)
        self.entry_folder.set_text(self.settings.auto_download_folder)
        self.entry_folder.set_editable(False)
        hbox.pack_start(self.entry_folder, True, True)

        self.folder_button = gtk.Button()
        image = gtk.Image()
        image.set_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_BUTTON)
        self.folder_button.set_image(image)
        self.folder_button.connect('clicked', self._download_folder_cb)
        hbox.pack_start(self.folder_button, False, True, 5)

        self.vbox.pack_start(hbox, False, False)

        # Load settings
        self.auto_load_images.set_active(self.settings.auto_load_images)
        self.show_labels_startup.set_active(self.settings.show_labels_startup)
        self.automatic_download.set_active(self.settings.auto_download)
        try:
            font_size_index = constants.font_size_range.index(self.settings.default_font_size)
        except ValueError:
            # defaults to 16pt
            font_size_index = constants.font_size_range.index(16)
        self.font_size_combobox.set_active(font_size_index)

        #Google reader settings (group)
        subtitle_label = gtk.Label(_('Google Reader Settings'))
        subtitle_label.set_alignment(0.01, 0.5)

        self.vbox.pack_start(subtitle_label, False, False, 10)

        hbox = gtk.HBox()
        self.entry_user = gtk.Entry()
        self.entry_password = gtk.Entry()
        self.force_sync_button = gtk.Button(_('Synchronize now'))
        self.synchronize_feeds = gtk.CheckButton(_('Synchronize with Google Reader'))
        self.synchronize_feeds.set_alignment(xalign=0, yalign=0.5)
        labels_group.add_widget(self.synchronize_feeds)
        self.synchronize_feeds.connect('clicked', self._synchronize_feeds_cb)
        self.synchronize_feeds.set_active(self.settings.sync_global)
        self.synchronize_feeds.show()
        hbox.pack_start(self.synchronize_feeds, False, True, 35)

        self.vbox.pack_start(hbox, False, False)

        hbox = gtk.HBox()
        label_user = gtk.Label(_('User') + ':')
        label_user_accessible = label_user.get_accessible()
        label_user_accessible.set_name(_('User'))
        label_user_accessible.set_role(atk.ROLE_LABEL)
        label_user.set_alignment(xalign=0, yalign=0.5)
        labels_group.add_widget(label_user)
        hbox.pack_start(label_user, False, True, 35)
        entry_user_accessible = self.entry_user.get_accessible()
        entry_user_accessible.set_name(_('Entry for user'))
        self.entry_user.set_text(self.settings.user)
        self.entry_user.set_sensitive(self.settings.sync_global)
        hbox.pack_start(self.entry_user, False, True)

        self.vbox.pack_start(hbox, False, False)

        hbox = gtk.HBox()
        label_password = gtk.Label(_('Password') + ':')
        label_password_accessible = label_password.get_accessible()
        label_password_accessible.set_name(_('Password'))
        label_password_accessible.set_role(atk.ROLE_LABEL)
        label_password.set_alignment(xalign=0, yalign=0.5)
        labels_group.add_widget(label_password)
        hbox.pack_start(label_password, False, True, 35)
        entry_password_accessible = self.entry_password.get_accessible()
        entry_password_accessible.set_name(_('Entry for password'))
        self.entry_password.set_visibility(False)
        self.entry_password.set_text(self.settings.password)
        self.entry_password.set_sensitive(self.settings.sync_global)
        hbox.pack_start(self.entry_password, False, True)

        self.vbox.pack_start(hbox, False, False)

        #Synchronize now
        hbox = gtk.HBox()
        self.force_sync_button.set_sensitive(self.settings.sync_global)
        self.force_sync_button.connect('clicked', self._settings_sync_google_reader_cb, self)
        self.force_sync_button.connect('clicked', self._block)
        hbox.pack_start(self.force_sync_button, False, True, 35)

        self.vbox.pack_start(hbox, False, False)

        self.pack_start(self.vbox, True, True)

        self.show_all()

        self.back_button = resistance_window.get_back_button()
        self.back_button.disconnect(resistance_window.get_button_back_connect_id())
        self.back_button.connect('clicked', self._show_message)

    def _block(self, button):
        self.set_sensitive(False)
        dialog = gtk.MessageDialog(None,
                               gtk.DIALOG_MODAL, gtk.MESSAGE_INFO, gtk.BUTTONS_CLOSE, _('Synchronizing. Wait window activation'))
        dialog.run()
        dialog.destroy()

    def _show_message(self, button = None):
        dialog = gtk.MessageDialog(None,
                               gtk.DIALOG_MODAL,
                               type=gtk.MESSAGE_QUESTION,
                               buttons=gtk.BUTTONS_YES_NO)
        dialog.set_markup("<b>%s</b>" % _('Do you want return without save?'))
        dialog.connect('response', self._back_response_cb)
        response = dialog.run()
        dialog.destroy()

    def _back_response_cb(self, dialog, response):
        if response == gtk.RESPONSE_YES:
            resistance_window.return_cb()

    def _download_folder_cb(self, button):
        chooser = gtk.FileChooserDialog(_('Autodownload folder'), None, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                    gtk.STOCK_SAVE, gtk.RESPONSE_OK))

        chooser.set_title(_('Select a folder for automatic downloads'))
        chooser.set_current_folder(constants.MYDOCS_DIR)

        chooser.set_default_response(gtk.RESPONSE_OK)

        response = chooser.run()
        folder = chooser.get_filename() + '/'
        chooser.destroy()

        self.settings.auto_download_folder = folder
        self.entry_folder.set_text(folder)

    def _synchronize_feeds_cb(self, button):
        self.entry_user.set_sensitive(button.get_active())
        self.entry_password.set_sensitive(button.get_active())
        self.force_sync_button.set_sensitive(button.get_active())

    def _settings_sync_google_reader_cb(self, button, settings_window = None):
        self._preferences_response_cb(None, False)

        # Quickly show feedback to user
        self.feedswindow.status_bar.push(self.feedswindow.context_id, _('Synchronizing...'))
        self.feedswindow.messages_counter += 1
        self.feedswindow.manager.sync_with_google_reader(self.feedswindow._feeds_synchronized, settings_window)

    def _preferences_response_cb(self, button, back=True):
        model = self.font_size_combobox.get_model()
        index = self.font_size_combobox.get_active()
        self.settings.default_font_size = int(model[index][0])
        self.settings.auto_load_images = self.auto_load_images.get_active()
        self.settings.show_labels_startup = self.show_labels_startup.get_active()
        self.settings.auto_download = self.automatic_download.get_active()
        self.settings.sync_global = self.synchronize_feeds.get_active()
        self.settings.user = self.entry_user.get_text()
        self.settings.password = self.entry_password.get_text()
        self.settings.sync_global = self.synchronize_feeds.get_active()

        if back:
            resistance_window.return_cb()

class LabelsWindow(ResistanceWindowContent):

    LABELS_MODEL_PIXBUF_COLUMN, LABELS_MODEL_NAME_COLUMN, LABELS_MODEL_ID_COLUMN = range(3)

    def __init__(self, manager, settings, conn_manager):
        super(LabelsWindow, self).__init__()

        self._manager = manager
        self._settings = settings
        self._conn_manager = conn_manager
        self._feeds_window = None
        self._folder_icon = None
        self._rotation_manager = None

        self._manager.connect('label-created', self._on_label_created_cb)

        self._view = gtk.TreeView()
        self._view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)

        pixbuf_renderer = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn(_('Icon'), pixbuf_renderer, pixbuf=LabelsWindow.LABELS_MODEL_PIXBUF_COLUMN)
        column.set_expand(False)
        self._view.append_column(column)

        text_renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('Name'), text_renderer, markup=LabelsWindow.LABELS_MODEL_NAME_COLUMN)
        column.set_expand(True)
        self._view.append_column(column)

        self._view.connect ("row-activated", self._on_label_activated)
        self._view.show()

        resistance_window.window_content(self, None)

        # Sorting by name but with some exceptions
        #   All Feeds
        #   Feed a
        #   Feed b
        store = gtk.ListStore(gtk.gdk.Pixbuf, str, int)
        self._view.set_model(store)
        store.set_sort_column_id(LabelsWindow.LABELS_MODEL_NAME_COLUMN, gtk.SORT_ASCENDING)

        self._create_menu()

        self.align = gtk.Alignment(0, 0, 1, 1)
        self.align.set_padding(4, 0 , 16, 16)

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)

        self.pack_start(scroll, True, True, 0)
        scroll.add(self._view)
        scroll.show()

        self.status_bar = gtk.Statusbar()  
        status_bar_accessible = self.status_bar.get_accessible()
        status_bar_accessible.set_name(_('Status bar'))
        status_bar_accessible.set_role(atk.ROLE_STATUSBAR)
        self.context_id = self.status_bar.get_context_id('Labelswindow statusbar')
        self.pack_start(self.status_bar, False, True, 0)
        self.status_bar.show()

        #To count the number of messages
        self.messages_counter = 0
        #Capture the activity to manage the statusbar
        resistance_window.window.connect('key-press-event', self._clear_status_bar)
        resistance_window.window.connect('button-press-event', self._clear_status_bar)
        self._view.connect('button-press-event', self._clear_status_bar)

        # Load Labels (could be none)
        self._manager.load_labels(self._load_labels_cb)

    def _get_folder_icon(self):
        if not self._folder_icon:
            self._folder_icon = gtk.icon_theme_get_default().load_icon(gtk.STOCK_DIRECTORY, 32, 0)
        return self._folder_icon

    def _create_menu(self):
        self.handlebox = gtk.HandleBox()
        self.toolbar = gtk.Toolbar()
        self.toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        self.toolbar.set_style(gtk.TOOLBAR_BOTH)
        self.toolbar.set_border_width(5)
        self.toolbar.set_tooltips(True)
        self.handlebox.add(self.toolbar)

        agr = resistance_window.resistance_window_agr()

        button = gtk.ToolButton() 
        button.set_stock_id(gtk.STOCK_ADD)
        button.set_label(_('New Label'))
        button.connect('clicked', self._create_label_cb)
        button.connect('clicked', self._clear_status_bar)
        button.set_tooltip_text( _('Add a new label [Ctrl+N]'))
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>N")
        button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        self.toolbar.insert(button, 0)       

        self._remove_button = gtk.ToolButton() 
        self._remove_button.set_stock_id(gtk.STOCK_REMOVE)
        self._remove_button.set_label(_('Remove Label'))
        self._remove_button.connect('clicked', self._remove_label_cb)
        self._remove_button.connect('clicked', self._clear_status_bar)
        self._remove_button.set_tooltip_text( _('Remove labels [Ctrl+D]'))
        #shortcut
        key, mod = gtk.accelerator_parse("<Control>D")
        self._remove_button.add_accelerator('clicked', agr, key, mod, gtk.ACCEL_VISIBLE)

        self.toolbar.insert(self._remove_button, 1)    

        self.pack_start(self.handlebox, False, False, 0)
        self.toolbar.show_all()
        self.handlebox.show_all()

    def _load_labels_cb(self, retval, user_data, error):
        if error:
            self.status_bar.push(self.context_id, _('Error loading labels.'))
            self.messages_counter += 1
            return

        labels = self._manager.get_label_list()
        store = self._view.get_model()

        folder_icon = self._get_folder_icon()
        for label_data in labels:
            feed_iter = store.append()
            store.set(feed_iter, LabelsWindow.LABELS_MODEL_ID_COLUMN, label_data[0],
                      LabelsWindow.LABELS_MODEL_NAME_COLUMN, gobject.markup_escape_text(label_data[1]),
                      LabelsWindow.LABELS_MODEL_PIXBUF_COLUMN, folder_icon)

        # Add special labels
        all_feeds_icon = gtk.icon_theme_get_default().load_icon(gtk.STOCK_HOME, 32, 0)
        feed_iter = store.append()
        store.set(feed_iter, LabelsWindow.LABELS_MODEL_NAME_COLUMN, _('All Feeds'),
                  LabelsWindow.LABELS_MODEL_ID_COLUMN, constants.ALL_LABEL_ID,
                  LabelsWindow.LABELS_MODEL_PIXBUF_COLUMN, all_feeds_icon)

        if len(labels) == 0:
            self._remove_button.set_sensitive(False)


    def _create_label_cb(self, button):
        dialog = NewLabelDialog(self)
        dialog.connect('response', self._create_label_response_cb)
        dialog.show_all()

    def _create_label_response_cb(self, dialog, response):
        if response != gtk.RESPONSE_ACCEPT:
            return

        # We do not need to add it to the view. The 'label-created'
        # signal handler will do it for us.
        label_name = dialog.entry.get_text()
        label_id = self._manager.create_label(label_name)

        if not label_id:
            self.status_bar.push(self.context_id, _('Label not created. Already exists.'))
            self.messages_counter += 1
            dialog.destroy()
            return

        dialog.destroy()

    def _on_label_created_cb(self, manager, label_id):
        label_name = manager.get_label_name(label_id)

        # Add label to the view
        store = self._view.get_model()
        feed_iter = store.append()
        store.set(feed_iter, LabelsWindow.LABELS_MODEL_NAME_COLUMN, gobject.markup_escape_text(label_name),
                  LabelsWindow.LABELS_MODEL_ID_COLUMN, label_id,
                  LabelsWindow.LABELS_MODEL_PIXBUF_COLUMN, self._get_folder_icon())

        self._remove_button.set_sensitive(True)

    def _on_label_activated(self, treeview, path, column):
        label_iter = self._view.get_model().get_iter(path)
        label_id = self._view.get_model().get_value(label_iter, LabelsWindow.LABELS_MODEL_ID_COLUMN)

        if label_id == constants.ALL_LABEL_ID:
            name = _('All Feeds')
        else:
            name = self._manager.get_label_name(label_id)  
        
        if not self._feeds_window:
            self._feeds_window = FeedsWindow(self._manager, self._settings, self._conn_manager, name)
        else:
            self._feeds_window._set_title(name)
            # Do not destroy the Feeds Window keep it cached instead
            resistance_window.window_content(self._feeds_window, None)
        self._feeds_window.set_filter_label_id(label_id)

    def _remove_label_cb(self, button):
        selection = self._view.get_selection()
        selected_rows = selection.get_selected_rows()
        store, paths = selected_rows
        if not paths:
            self.status_bar.push(self.context_id, _('Please select at least one Label'))
            self.messages_counter += 1
            return

        dialog = gtk.MessageDialog(None,
                               gtk.DIALOG_MODAL,
                               type=gtk.MESSAGE_QUESTION,
                               buttons=gtk.BUTTONS_YES_NO)
        dialog.set_markup("<b>%s</b>" % _('Do you want to delete these labels?'))
        dialog.connect('response', self._remove_cb, store, paths)
        response = dialog.run()
        dialog.destroy()

    def _remove_cb(self, dialog, response, store, paths):
        if response == gtk.RESPONSE_YES:
            removed = []
            for path in paths:
                if path[0] != 0:
                    self._manager.remove_label(store[path][LabelsWindow.LABELS_MODEL_ID_COLUMN])
                    removed.append(gtk.TreeRowReference(store, path))

            for reference in removed:
                store.remove(store.get_iter(reference.get_path()))

            if len(self._manager.get_label_list()) == 0:
                self._remove_button.set_sensitive(False)

    def _clear_status_bar(self, widget, event=None):
        gobject.timeout_add(3000, self._clear_messages)

    def _clear_messages(self):
        for message in range(self.messages_counter):
            self.status_bar.pop(self.context_id)

class NewLabelDialog(gtk.Dialog):

    def __init__(self, parent):
        super(NewLabelDialog, self).__init__(_('New Label'), None,
                                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                            (_('Add'), gtk.RESPONSE_ACCEPT))

        self.entry = gtk.Entry()
        entry_accessible = self.entry.get_accessible()
        entry_accessible.set_name(_('Entry for label name'))
        entry_accessible.set_description(_('Write here a name for the new label'))
        self.entry.connect('changed', self._entry_changed_cb)

        caption = gtk.HBox(False, 16)
        label = gtk.Label(_('Label name') + ':')
        label_accessible = label.get_accessible()
        label_accessible.set_name(_('Label name'))
        label_accessible.add_relationship(atk.RELATION_LABEL_FOR, entry_accessible)
        label_accessible.set_role(atk.ROLE_LABEL)
        caption.pack_start(label, False, False)
        caption.pack_start(self.entry)
        self.vbox.add(caption)

        self.can_accept = False
        self.set_response_sensitive(gtk.RESPONSE_ACCEPT, self.can_accept)

        self.add_events(gtk.gdk.KEY_PRESS_MASK)
        self.connect('key-press-event', self.on_dialog_key_press)
        
    def on_dialog_key_press(self, dialog, event):
        #Accept the dialog if you pulse enter key
        if event.keyval == gtk.keysyms.Return and self.can_accept:                      
            dialog.response(gtk.RESPONSE_ACCEPT)

    def _entry_changed_cb(self, entry):
        self.can_accept = len(entry.get_text()) > 0
        self.set_response_sensitive(gtk.RESPONSE_ACCEPT, self.can_accept)


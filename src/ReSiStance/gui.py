#!/usr/bin/env python
# -*- coding: utf-8 -*-

#########################################################################
#    Copyright (C) 2010, 2011 Sergio Villar Senin <svillar@igalia.com>
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

from feedmanager import ReSiStanceFeedSummary
from pango import ELLIPSIZE_END
from portrait import FremantleRotation
from renderers import FeedCellRenderer, CellRendererRoundedRectangleText
from threading import Thread
from utils import *
from webkit import WebView
import calendar
import constants
import feedparser
import gettext
import glib
import gobject
import gtk
import hildon
import os
import osso
import pygtk
pygtk.require('2.0')
import time
import urllib2
import urllib

_ = gettext.gettext

class FeedsView(hildon.GtkTreeView):

    DUMMY_FEED_STATUS = -1

    def __init__(self, ui_mode):
        super(FeedsView, self).__init__(ui_mode)

        # Feed icon column
        pix_renderer = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn('Icon', pix_renderer, pixbuf = FeedsWindow.FEEDS_MODEL_PIXBUF_COLUMN)
        column.set_expand(False)
        self.append_column(column);

        # Feed title column
        #google_reader_pixbuf = gtk.gdk.pixbuf_new_from_file(constants.GOOGLE_READER_ICON_FILE)
        google_reader_pixbuf = gtk.gdk.pixbuf_new_from_file('../../data/prism-google-reader.png')
        text_renderer = FeedCellRenderer(google_reader_pixbuf)
        text_renderer.set_property('xalign', 0)
        text_renderer.set_property('xpad', 8)

        column = gtk.TreeViewColumn('Name', text_renderer, title=FeedsWindow.FEEDS_MODEL_TITLE_COLUMN, subtitle=FeedsWindow.FEEDS_MODEL_SUBTITLE_COLUMN, sync=FeedsWindow.FEEDS_MODEL_SYNC_COLUMN, id=FeedsWindow.FEEDS_MODEL_ID_COLUMN)
        column.set_expand(True)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column);

        # Unread entries column
        unread_renderer = CellRendererRoundedRectangleText()
        unread_renderer.set_property('xpad', 8)
        unread_renderer.set_property('xalign', 0.5)
        column = gtk.TreeViewColumn('Unread', unread_renderer, text = FeedsWindow.FEEDS_MODEL_READ_COLUMN)
        column.set_expand(False)
        self.append_column(column);

        # TODO: Fixed size to improve panning ?

class InputTextDialog(gtk.Dialog):
    def __init__(self, parent, title, button_label, caption_label, input_mode):
        super(InputTextDialog, self).__init__(title, parent,
                                              gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                              (button_label, gtk.RESPONSE_ACCEPT))

        self.entry = hildon.Entry(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.entry.set_input_mode(input_mode)
        self.entry.connect('changed', self._entry_changed_cb)

        caption = gtk.HBox(False, 16)
        caption.pack_start(gtk.Label(caption_label + ':'), False, False)
        caption.pack_start(self.entry)
        self.vbox.add(caption)

        self.set_response_sensitive(gtk.RESPONSE_ACCEPT, False)

    def _entry_changed_cb(self, entry):
        if len(entry.get_text()) > 0:
            self.set_response_sensitive(gtk.RESPONSE_ACCEPT, True)
        else:
            self.set_response_sensitive(gtk.RESPONSE_ACCEPT, False)

    def _delete_event_cb(self, widget, event):
        return True #stop the signal propagation

class SettingsDialog(gtk.Dialog):
    RESPONSE_SYNC_GOOGLE = 1

    def __init__(self, parent, settings):
        super(SettingsDialog, self).__init__(_('Settings'), parent,
                                                gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                                (gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT))

        self.settings = settings

        self.set_size_request(parent.get_size()[0], parent.get_size()[1])
        self.panel = hildon.PannableArea()
        list_panel = gtk.VBox(2)
        self.panel.add_with_viewport(list_panel)
        self.vbox.pack_start(self.panel, True)

        visual_label = gtk.Label(_('Visual Settings'))
        visual_label.set_alignment(0.5, 0.75)
        list_panel.pack_start(visual_label)

        # Orientation picker
        self.selector_orientation = hildon.TouchSelector(text=True)
        for caption in FremantleRotation.MODE_CAPTIONS:
            self.selector_orientation.append_text(caption)
        self.picker_orientation = hildon.PickerButton(gtk.HILDON_SIZE_FINGER_HEIGHT,
                                                      hildon.BUTTON_ARRANGEMENT_VERTICAL)
        self.picker_orientation.set_selector(self.selector_orientation)
        self.picker_orientation.set_alignment(0, 0.5, 0, 0)
        self.picker_orientation.set_title(_("Screen orientation"))
        list_panel.pack_start(self.picker_orientation)
        self.picker_orientation.show()

        # Font size picker
        self.selector_font_size = hildon.TouchSelector(text=True)
        for i in constants.font_size_range:
            self.selector_font_size.append_text(str(i))
        self.picker_font_size = hildon.PickerButton(gtk.HILDON_SIZE_FINGER_HEIGHT,
                                                      hildon.BUTTON_ARRANGEMENT_VERTICAL)
        self.picker_font_size.set_selector(self.selector_font_size)
        self.picker_font_size.set_alignment(0, 0.5, 0, 0)
        self.picker_font_size.set_title(_("Default font size"))
        list_panel.pack_start(self.picker_font_size)
        self.picker_font_size.show()

        # Load images check button
        self.auto_load_images = hildon.CheckButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.auto_load_images.set_label(_('Auto load images'))
        list_panel.pack_start(self.auto_load_images)
        self.auto_load_images.show()

        # Labels
        self.show_labels_startup = hildon.CheckButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.show_labels_startup.set_label(_('Show labels at start-up'))
        list_panel.pack_start(self.show_labels_startup)
        self.show_labels_startup.show()

        update_label = gtk.Label(_('Update Settings'))
        update_label.set_alignment(0.5, 0.75)
        list_panel.pack_start(update_label)

        # Auto update at startup
        self.auto_update_startup = hildon.CheckButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.auto_update_startup.set_label(_('Auto-update at start-up'))
        list_panel.pack_start(self.auto_update_startup)
        self.auto_update_startup.show()

        # Delete old check button
        self.delete_old = hildon.CheckButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.delete_old.set_label(_('Delete old items when updating'))
        list_panel.pack_start(self.delete_old)
        self.delete_old.show()

        # Automatic download check button
        self.automatic_download = hildon.CheckButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.automatic_download.set_label(_('Automatically download Podcasts'))
        self.automatic_download.connect('clicked', self._auto_download_cb)
        list_panel.pack_start(self.automatic_download)
        self.automatic_download.show()

        self.picker_download_folder = hildon.Button(gtk.HILDON_SIZE_FINGER_HEIGHT,
                                                      hildon.BUTTON_ARRANGEMENT_VERTICAL)
        self.picker_download_folder.set_title(_('Auto Download Folder'))
        self.picker_download_folder.set_value(self.settings.auto_download_folder)
        self.picker_download_folder.set_alignment(0, 0.5, 0, 0)
        self.picker_download_folder.connect('clicked', self._download_folder_cb)
        self.picker_download_folder.set_style(hildon.BUTTON_STYLE_PICKER)
        self.picker_download_folder.set_sensitive(self.settings.auto_download)
        list_panel.pack_start(self.picker_download_folder)
        self.picker_download_folder.show()

        # Load settings
        self.auto_load_images.set_active(self.settings.auto_load_images)
        self.automatic_download.set_active(self.settings.auto_download)
        self.selector_orientation.set_active(0, self.settings.rotation_mode)
        self.delete_old.set_active(self.settings.delete_old)
        self.auto_update_startup.set_active(self.settings.auto_update_startup)
        self.show_labels_startup.set_active(self.settings.show_labels_startup)
        try:
            font_size_index = constants.font_size_range.index(self.settings.default_font_size)
        except ValueError:
            # defaults to 16pt
            font_size_index = constants.font_size_range.index(16)
        self.selector_font_size.set_active(0, font_size_index)

        google_label = gtk.Label(_('Google Reader Settings'))
        google_label.set_alignment(0.5, 0.75)
        list_panel.pack_start(google_label)

        self.entry_user = hildon.Entry(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.entry_user.set_input_mode(gtk.HILDON_GTK_INPUT_MODE_FULL)
        self.entry_user.set_text(self.settings.user)
        self.entry_user.set_sensitive(self.settings.sync_global)

        self.entry_password = hildon.Entry(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.entry_password.set_input_mode(gtk.HILDON_GTK_INPUT_MODE_FULL | gtk.HILDON_GTK_INPUT_MODE_INVISIBLE)
        self.entry_password.set_text(self.settings.password)
        self.entry_password.set_sensitive(settings.sync_global)

        # Synchronize feed check button
        self.synchronize_feeds = hildon.CheckButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.synchronize_feeds.set_label(_('Synchronize with Google Reader'))
        list_panel.pack_start(self.synchronize_feeds)
        self.synchronize_feeds.set_active(self.settings.sync_global)
        self.synchronize_feeds.show()

        caption = gtk.HBox(False, 16)
        label_user = gtk.Label(_('User') + ':')
        label_user.set_alignment(xalign=0, yalign=0.5)
        label_password = gtk.Label(_('Password') + ':')
        label_password.set_alignment(xalign=0, yalign=0.5)

        labels_group = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
        labels_group.add_widget(label_user)
        labels_group.add_widget(label_password)

        caption = gtk.HBox(False, 16)
        caption.pack_start(label_user, False, False)
        caption.pack_start(self.entry_user, True, True)
        list_panel.pack_start(caption)

        caption = gtk.HBox(False, 16)
        caption.pack_start(label_password, False, False)
        caption.pack_start(self.entry_password, True, True)
        list_panel.pack_start(caption)

        self._force_sync_button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self._force_sync_button.set_label(_('Synchronize Now'))
        self._force_sync_button.set_sensitive(self.settings.sync_global)
        list_panel.pack_start(self._force_sync_button)

        # Connect signals
        self._force_sync_button.connect('clicked', self._settings_sync_google_reader_cb)
        self.synchronize_feeds.connect('clicked', self._synchronize_feeds_cb)

    def _settings_sync_google_reader_cb(self, button):
        self.response(self.RESPONSE_SYNC_GOOGLE)

    def _auto_download_cb(self, button):
        self.picker_download_folder.set_sensitive(button.get_active())

    def _download_folder_cb(self, button):
        stack = hildon.WindowStack.get_default()
        window = stack.peek()

        chooser = hildon.FileChooserDialog(window, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
        chooser.set_transient_for(window)
        chooser.set_title(_('Select a folder for automatic downloads'))
        chooser.set_current_folder(constants.MYDOCS_DIR)

        chooser.set_default_response(gtk.RESPONSE_OK)

        response = chooser.run()
        folder = chooser.get_filename() + '/'
        chooser.destroy()

        self.settings.auto_download_folder = folder
        button.set_value(folder)

    def _synchronize_feeds_cb(self, button):
        enabled = button.get_active()
        self.entry_user.set_sensitive(enabled)
        self.entry_password.set_sensitive(enabled)
        self._force_sync_button.set_sensitive(enabled)

    def jump_to_google_reader_auth(self):
        self.panel.jump_to_child(self.entry_user)

    def save_settings(self, settings):
        settings.auto_load_images = self.auto_load_images.get_active()
        settings.rotation_mode = self.selector_orientation.get_active(0)
        settings.default_font_size = int(self.selector_font_size.get_current_text())
        settings.auto_download = self.automatic_download.get_active()
        settings.user = self.entry_user.get_text()
        settings.password = self.entry_password.get_text()
        settings.sync_global = self.synchronize_feeds.get_active()
        settings.delete_old = self.delete_old.get_active()
        settings.auto_update_startup = self.auto_update_startup.get_active()
        settings.show_labels_startup = self.show_labels_startup.get_active()

class FeedsWindow(hildon.StackableWindow):

    FEEDS_MODEL_PIXBUF_COLUMN, FEEDS_MODEL_TITLE_COLUMN, FEEDS_MODEL_SUBTITLE_COLUMN, \
        FEEDS_MODEL_READ_COLUMN, FEEDS_MODEL_VISITS_COLUMN, FEEDS_MODEL_SYNC_COLUMN, \
        FEEDS_MODEL_ID_COLUMN, FEEDS_MODEL_HREF_COLUMN, FEEDS_MODEL_LABEL_VISIBLE_COLUMN = range(9)

    def __init__(self, manager, settings, conn_manager):
        super(FeedsWindow, self).__init__()

        self.manager = manager
        self.manager.connect('feed-added', self._on_feed_added_update_label)
        self.settings = settings
        self._conn_manager = conn_manager
        self._conn_manager.connect('connection-changed', self._on_connection_changed)
        self._filter_label_id = constants.ALL_LABEL_ID
        self._rotation_manager = None

        # Feeds
        self.view = FeedsView(gtk.HILDON_UI_MODE_NORMAL)
        store = gtk.ListStore(gtk.gdk.Pixbuf, str, str, str, int, bool, int, str, bool)
        model_filter = store.filter_new()
        model_filter.set_visible_column(self.FEEDS_MODEL_LABEL_VISIBLE_COLUMN)
        self.view.set_model (model_filter)
        self.view.connect ("row-activated", self._on_feed_activated)
        self.view.show()

        # Edit toolbar
        self.edit_toolbar_button_handler = 0
        self.edit_toolbar = hildon.EditToolbar()
        self.edit_toolbar.connect('arrow-clicked', self._restore_normal_mode)

        self.align = gtk.Alignment(0, 0, 1, 1)
        self.align.set_padding(4, 0 , 16, 16)

        pannable = hildon.PannableArea()
        pannable.add (self.view)
        pannable.set_size_request_policy(hildon.SIZE_REQUEST_MINIMUM)
        pannable.show()

        self.align.add(pannable)
        self.add(self.align)
        self.align.show()

        self._create_menu()
        self.set_title(constants.RSS_NAME)
        self.connect('configure-event', self._on_configuration_changed)

        # Apply settings
        self._sort(self.settings.feeds_order)
        if self.settings.feeds_order == constants.DESCENDING_ORDER:
            self.descending_filter_button.set_active(True)
        elif self.settings.feeds_order == constants.VISITS_ORDER:
            self.visits_filter_button.set_active(True)

        # Evaluate menu buttons visibility
        self._on_connection_changed(self._conn_manager)
        self._check_label_menu_options_visibility()

        # Load feed summaries (could be none)
        try:
            hildon.hildon_gtk_window_set_progress_indicator(self, True)
            self._load_tag = glib.timeout_add(1000, self._show_loading_banner)
            self.manager.load_feeds_summary(self._feeds_summary_loaded)
        except Exception:
            hildon.hildon_gtk_window_set_progress_indicator(self, False)
            glib.source_remove(self._load_tag)
            self._show_initial_dialog()

    def set_rotation_manager(self, rotation_manager):
        self._rotation_manager = rotation_manager

    def set_filter_label_id(self, filter_label_id):

        if filter_label_id == constants.ALL_LABEL_ID:
            self.set_title(_('All Feeds'))
        else:
            self.set_title(self.manager.get_label_name(filter_label_id))

        if filter_label_id == self._filter_label_id:
            return

        self._filter_label_id = filter_label_id

        # Refilter
        store = self.view.get_model().get_model()
        for row in store:
            feed_id = row[FeedsWindow.FEEDS_MODEL_ID_COLUMN]
            row[FeedsWindow.FEEDS_MODEL_LABEL_VISIBLE_COLUMN] = self.manager.feed_has_label(feed_id, filter_label_id)
        # Button visibility
        self._check_label_menu_options_visibility()

    def _show_loading_banner(self):
        hildon.hildon_banner_show_information(self, '', _('Loading feed data'))
        return False

    def _check_label_menu_options_visibility(self):
        if len(self.manager.get_label_list()) == 0 or \
                self._filter_label_id == constants.ALL_LABEL_ID:
            self._add_to_label_button.hide()
            self._remove_from_label_button.hide()
            return

        self._add_to_label_button.show()
        if len(self.manager.get_feeds_for_label(self._filter_label_id)) == 0:
            self._remove_from_label_button.hide()
        else:
            self._remove_from_label_button.show()

    def _on_connection_changed(self, conn_manager):
        if self._conn_manager.is_online():
            self._new_feed_button.show()
            self._update_all_button.show()
            self._find_feeds_button.show()
            self._import_feeds_button.show()
        else:
            self._new_feed_button.hide()
            self._update_all_button.hide()
            self._find_feeds_button.hide()
            self._import_feeds_button.hide()

    def _sort(self, order):
        store = self.view.get_model().get_model()
        if (order == constants.ASCENDING_ORDER):
            store.set_sort_column_id(self.FEEDS_MODEL_TITLE_COLUMN, gtk.SORT_ASCENDING)
        elif (order == constants.DESCENDING_ORDER):
            store.set_sort_column_id(self.FEEDS_MODEL_TITLE_COLUMN, gtk.SORT_DESCENDING)
        else:
            store.set_sort_column_id(self.FEEDS_MODEL_VISITS_COLUMN, gtk.SORT_DESCENDING)

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

    def _show_entries_window(self, path):
        model_filter = self.view.get_model()
        feed_iter = model_filter.get_iter(path)
        feed_id = model_filter.get_value(feed_iter, self.FEEDS_MODEL_ID_COLUMN)
        summary = self.manager.get_feed_summary(feed_id)
        feed_data = self.manager.get_feed_data(feed_id)

        news_window = EntriesWindow(feed_data, self.manager, self.settings, self._conn_manager)
        news_window.show()

        # When the news window is closed (in Maemo5 it's really
        # hidden) reset the unread cache. Get the row reference BEFORE
        # setting the visits count. Otherwise we will get the wrong
        # one
        news_window.connect('hide', self._on_news_window_closed,
                            gtk.TreeRowReference(model_filter, path))

        # Update the visits count
        summary.visits += 1
        store_feed_iter = model_filter.convert_iter_to_child_iter(feed_iter)
        model_filter.get_model().set_value(store_feed_iter, self.FEEDS_MODEL_VISITS_COLUMN, summary.visits)

    def _on_feed_activated(self, treeview, path, column):
        feed_iter = self.view.get_model().get_iter(path)
        feed_id = self.view.get_model().get_value(feed_iter, self.FEEDS_MODEL_ID_COLUMN)

        # Check that we're not trying to open a dummy feed
        if feed_id == self.view.DUMMY_FEED_STATUS:
            hildon.hildon_banner_show_information(self, '', _('Wait until feed is refreshed'))
            return

        feed_data = self.manager.get_feed_data(feed_id)
        # Load feed data on demand
        if not feed_data:
            row_reference = gtk.TreeRowReference(self.view.get_model(), path)
            self.manager.load(feed_id, self._feed_data_loaded_cb, row_reference)
            return

        self._show_entries_window(path)

    def _feed_data_loaded_cb(self, feed_data, row_reference, error):
        if not feed_data:
            hildon.hildon_banner_show_information(self, '', _('Error loading feed data'))
            return

        self._show_entries_window(row_reference.get_path())

    def _on_news_window_closed(self, news_window, row_reference):
        store = self.view.get_model().get_model()
        store_path = self.view.get_model().convert_path_to_child_path(row_reference.get_path())
        store_feed_iter = store.get_iter(store_path)

        feed_id = store.get_value(store_feed_iter, self.FEEDS_MODEL_ID_COLUMN)
        feed_data = self.manager.get_feed_data(feed_id)

        # Reset unread cache (the value have most likely changed).
        unread_count = len([entry for entry in feed_data.entries if entry.read == False])
        store.set(store_feed_iter, self.FEEDS_MODEL_READ_COLUMN, get_visual_unread_text(unread_count))

        # Update sync status (could have changed)
        summary = self.manager.get_feed_summary(feed_id)
        store.set(store_feed_iter, self.FEEDS_MODEL_SYNC_COLUMN, summary.sync)

    def _on_configuration_changed(self, window, event):
        # Change alignment padding. We don't want padding in portrait
        # Need to save space
        if event.width > event.height:
            self.align.set_padding(4, 0 , 16, 16)
        else:
            self.align.set_padding(4, 0 , 4, 4)

    def _create_menu(self):
        menu = hildon.AppMenu()

        # Sorting filter
        self.ascending_filter_button = hildon.GtkRadioButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.ascending_filter_button.set_mode(False)
        self.ascending_filter_button.set_label(_('A-Z'))
        self.ascending_filter_button.connect('toggled', self._sort_ascending_cb)
        menu.add_filter(self.ascending_filter_button)
        self.descending_filter_button = \
            hildon.GtkRadioButton(gtk.HILDON_SIZE_FINGER_HEIGHT,
                                  group = self.ascending_filter_button)
        self.descending_filter_button.set_mode(False)
        self.descending_filter_button.set_label(_('Z-A'))
        self.descending_filter_button.connect('toggled', self._sort_descending_cb)
        menu.add_filter(self.descending_filter_button)
        self.visits_filter_button = \
            hildon.GtkRadioButton(gtk.HILDON_SIZE_FINGER_HEIGHT,
                                  group = self.ascending_filter_button)
        self.visits_filter_button.set_mode(False)
        self.visits_filter_button.set_label(_('Favorites'))
        self.visits_filter_button.connect('toggled', self._sort_visits_cb)
        menu.add_filter(self.visits_filter_button)

        self._new_feed_button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self._new_feed_button.set_label(_('New Feed'))
        self._new_feed_button.connect('clicked', self._new_feed_cb)
        menu.append(self._new_feed_button)

        button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        button.set_label(_('Remove Feed'))
        button.connect('clicked', self._remove_feed_cb)
        menu.append(button)

        self._update_all_button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self._update_all_button.set_label(_('Update all'))
        self._update_all_button.connect('clicked', self._update_all_cb)
        menu.append(self._update_all_button)

        self._import_feeds_button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self._import_feeds_button.set_label(_('Import Feeds'))
        self._import_feeds_button.connect('clicked', self._import_feed_cb)
        menu.append(self._import_feeds_button)

        button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        button.set_label(_('Export Feeds'))
        button.connect('clicked', self._export_feed_cb)
        menu.append(button)
        self.export_opml_button = button

        self._find_feeds_button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self._find_feeds_button.set_label(_('Find Feeds'))
        self._find_feeds_button.connect('clicked', self._find_feed_cb)
        menu.append(self._find_feeds_button)

        self._add_to_label_button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self._add_to_label_button.set_label(_('Add Feed to Label'))
        self._add_to_label_button.connect('clicked', self._add_feed_to_label_cb)
        menu.append(self._add_to_label_button)

        self._remove_from_label_button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self._remove_from_label_button.set_label(_('Remove Feed from Label'))
        self._remove_from_label_button.connect('clicked', self._remove_feed_from_label_cb)
        menu.append(self._remove_from_label_button)

        button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        button.set_label(_('Settings'))
        button.connect('clicked', self._preferences_cb)
        menu.append(button)

        menu.show_all()
        self.set_app_menu(menu)

    def _new_feed_cb(self, button):
        dialog = InputTextDialog(self, _('New Feed'), gtk.STOCK_ADD, _('Addresss'),
                                 gtk.HILDON_GTK_INPUT_MODE_FULL)
        dialog.connect('response', self._new_feed_response_cb)
        dialog.show_all()

    def _remove_feed_cb(self, button):

        # tree view edit mode
        hildon.hildon_gtk_tree_view_set_ui_mode(self.view, gtk.HILDON_UI_MODE_EDIT)
        self.view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.view.get_selection().unselect_all()

        self.edit_toolbar.set_label(_('Select Feeds to remove'))
        self.edit_toolbar.set_button_label(_('Remove'))
        if self.edit_toolbar.handler_is_connected (self.edit_toolbar_button_handler):
            self.edit_toolbar.disconnect(self.edit_toolbar_button_handler)
        self.edit_toolbar_button_handler = \
            self.edit_toolbar.connect('button-clicked', self._remove_button_clicked_cb)

        self.set_edit_toolbar(self.edit_toolbar)
        self.edit_toolbar.show()
        self.fullscreen()

    def _remove_button_clicked_cb(self, button):
        selection = self.view.get_selection()
        selected_rows = selection.get_selected_rows()
        model_filter, paths = selected_rows
        if not paths:
            hildon.hildon_banner_show_information(self, '', _('Please select at least one Feed'))
            return

        removed = []
        unsubscribe = []
        for path in paths:
            try:
                self.manager.remove_feed(model_filter[path][FeedsWindow.FEEDS_MODEL_ID_COLUMN])
            except IOError:
                print 'Could not remove', constants.RSS_DB_FILE
                hildon.hildon_banner_show_information(self, '', _('File error while removing Feed'))
            else:
                removed.append(gtk.TreeRowReference(model_filter, path))
                # Remove from Google Reader if needed
                if model_filter[path][FeedsWindow.FEEDS_MODEL_SYNC_COLUMN]:
                    unsubscribe.append(model_filter[path][FeedsWindow.FEEDS_MODEL_HREF_COLUMN])

        if not len(model_filter):
            self.export_opml_button.hide()

        if len(unsubscribe):
            message = gettext.ngettext('Do you want to remove the selected feed from Google Reader?',
                                       'Do you want to remove the selected feeds from Google Reader?',
                                       len(unsubscribe))
            note = hildon.hildon_note_new_confirmation(self, message)
            response = gtk.Dialog.run(note)
            note.destroy()
            if response == gtk.RESPONSE_OK:
                for feed_url in unsubscribe:
                    self.manager.subscribe_feed_google(feed_url, False)

        store = model_filter.get_model()
        for reference in removed:
            filter_iter = model_filter.get_iter(reference.get_path())
            store.remove(model_filter.convert_iter_to_child_iter(filter_iter))

        # restore normal mode
        self._restore_normal_mode(button)

    def _restore_normal_mode(self, button):

        # tree view normal mode
        hildon.hildon_gtk_tree_view_set_ui_mode(self.view, gtk.HILDON_UI_MODE_NORMAL)
        self.view.get_selection().unselect_all()

        self.edit_toolbar.hide()
        self.unfullscreen()

    def _preferences_cb(self, button):
        dialog = SettingsDialog(self, self.settings)
        dialog.connect('response', self._preferences_response_cb)
        dialog.show_all()

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
            hildon.hildon_banner_show_information(self, '', 'Updated ' + feed_data.feed.title)

        static['count'] += 1
        # If all add operations have finished then call the all-done-callback
        if static['count'] == num_operations:
            hildon.hildon_gtk_window_set_progress_indicator(self, False)
            static['count'] = 0
            if callback:
                callback(data)
        else:
            hildon.hildon_gtk_window_set_progress_indicator(self, True)

    def _update_multiple_feeds(self, callback=None, data=None):
        hildon.hildon_gtk_window_set_progress_indicator(self, True)

        model_filter = self.view.get_model()
        num_rows = len(model_filter)
        feed_iter = model_filter.get_iter_first()
        while feed_iter:
            # Create a row reference
            row_reference = gtk.TreeRowReference(model_filter, model_filter.get_path(feed_iter))
            # Update feed
            self.manager.update_feed(model_filter.get_value(feed_iter, self.FEEDS_MODEL_ID_COLUMN),\
                                         self._multiple_update_cb,\
                                         (num_rows, callback, data, row_reference))
            feed_iter = model_filter.iter_next(feed_iter)

    def _update_all_cb(self, button):
        # Quickly show feedback to user
        hildon.hildon_gtk_window_set_progress_indicator(self, True)

        # Ask manager to update feed
        self._update_multiple_feeds(self._all_feeds_updated_cb)

    def _all_feeds_updated_cb(self, data):
        hildon.hildon_gtk_window_set_progress_indicator(self, False)

        # Do not update read/unread status if all the feeds failed to sync
        synced_feeds = [row[self.FEEDS_MODEL_ID_COLUMN] for row in self.view.get_model() \
                            if row[self.FEEDS_MODEL_SYNC_COLUMN]]
        if len(synced_feeds) == 0:
            return

        # Update read/unread status
        hildon.hildon_banner_show_information(self, '', _('Synchronizing read/unread status with Google Reader'))
        hildon.hildon_gtk_window_set_progress_indicator(self, True)
        self.manager.sync_google_reader_read_status(self._sync_google_reader_read_status_cb)

    def _new_feed_response_cb(self, dialog, response):

        if response == gtk.RESPONSE_ACCEPT:

            url = dialog.entry.get_text()

            # Quickly show feedback to user
            hildon.hildon_gtk_window_set_progress_indicator(self, True)

            # Insert a dummy row while information is retrieved
            feed_iter = self._add_dummy_feed(url)
            path = self.view.get_model().get_path(feed_iter)
            row_reference = gtk.TreeRowReference(self.view.get_model(), path)

            # Add feed to manager. Do not sync with Google
            self.manager.add_feed(url, False, self._feed_added_cb, row_reference)

            dialog.destroy()

    def _feed_added_cb(self, pixbuf_and_data, row_reference=None, error=None, stop_progress=True):

        # Remove progress information
        if stop_progress:
            hildon.hildon_gtk_window_set_progress_indicator(self, False)

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
            hildon.hildon_banner_show_information(self, '', message)
            return

        pixbuf, new_feed_data = pixbuf_and_data
        self.export_opml_button.show()

        # Update model
        feed_id = get_feed_id(new_feed_data)
        summary = self.manager.get_feed_summary(feed_id)
        subtitle = get_feed_subtitle(new_feed_data)
        visible = self.manager.feed_has_label(summary.feed_id, self._filter_label_id)
        store.set(feed_iter,
                  self.FEEDS_MODEL_PIXBUF_COLUMN, pixbuf,
                  self.FEEDS_MODEL_TITLE_COLUMN, get_feed_title_markup(new_feed_data.feed.title),
                  self.FEEDS_MODEL_SUBTITLE_COLUMN, get_feed_subtitle_markup(subtitle),
                  self.FEEDS_MODEL_READ_COLUMN, get_visual_unread_text(len(new_feed_data.entries)),
                  self.FEEDS_MODEL_VISITS_COLUMN, summary.visits,
                  self.FEEDS_MODEL_SYNC_COLUMN, summary.sync,
                  self.FEEDS_MODEL_ID_COLUMN, feed_id,
                  self.FEEDS_MODEL_HREF_COLUMN, new_feed_data.href,
                  self.FEEDS_MODEL_LABEL_VISIBLE_COLUMN, visible)

    def _multiple_add_cb(self, pixbuf_and_data, user_data, error, static = {"count" : 0}):
        ''' Simulating a static variable with a default argument hack '''
        num_operations, callback, data, row_reference = user_data

        self._feed_added_cb(pixbuf_and_data, row_reference, error, stop_progress=False)
        static['count'] += 1
        # If all add operations have finished then call the all-done-callback
        if static['count'] == num_operations:
            hildon.hildon_gtk_window_set_progress_indicator(self, False)
            static['count'] = 0
            if callback:
                callback(data)
        else:
            hildon.hildon_gtk_window_set_progress_indicator(self, True)

    def _add_multiple_feeds(self, urls, sync=False, callback=None, data=None):
        # Quickly show feedback to user
        hildon.hildon_gtk_window_set_progress_indicator(self, True)
        for url in urls:
            # Insert a dummy row while information is retrieved
            feed_iter = self._add_dummy_feed(url, sync)
            path = self.view.get_model().get_path(feed_iter)
            row_reference = gtk.TreeRowReference(self.view.get_model(), path)

            # Add feed to manager
            self.manager.add_feed(url, sync, self._multiple_add_cb,
                                  (len(urls), callback, data, row_reference))

    def _sync_google_reader_read_status_cb(self, synced, user_data, error):
        hildon.hildon_gtk_window_set_progress_indicator(self, False)

        if not synced:
            hildon.hildon_banner_show_information(self, '', _('Error syncing read status with Google Reader'))
            return

        store = self.view.get_model().get_model()
        for row in store:
            if row[self.FEEDS_MODEL_SYNC_COLUMN]:
                feed_data = self.manager.get_feed_data(row[self.FEEDS_MODEL_ID_COLUMN])
                unread_count = len([entry for entry in feed_data.entries if entry.read == False])
                row[self.FEEDS_MODEL_READ_COLUMN] = get_visual_unread_text(unread_count)

    def _add_labels_confirmation_response_cb(self, note, response, label_feeds):
        if response != gtk.RESPONSE_OK:
            note.destroy()
            return

        all_labels = self.manager.get_label_list()
        for label_name in label_feeds.keys():
            summaries = [summary for summary in self.manager.get_feed_summaries()
                         if summary.href in label_feeds[label_name]]
            feed_ids = [summary.feed_id for summary in summaries]
            label_ids = [label_data[0] for label_data in all_labels if label_data[1] == label_name]
            label_id = self.manager.create_label(label_name) if len(label_ids) == 0 else label_ids[0]
            self.manager.add_feeds_to_label(feed_ids, label_id)

        note.destroy()

    def _all_synchronized_feeds_added_cb(self, label_feeds):
        ''' Called after adding all the feeds retrieved from Google Reader '''

        if len(label_feeds) > 0:
            note_text = '%s\n%s' % (_('Do you want to retrieve labels from GoogleReader?'),
                                    _('Note: no future synchronization of labels will be performed'))
            note = hildon.Note("confirmation", self, note_text)
            note.connect('response', self._add_labels_confirmation_response_cb, label_feeds)
            note.show()

        # Do not update read/unread status if all the feeds failed to sync
        synced_feeds = 0
        for row in self.view.get_model():
            if row[self.FEEDS_MODEL_ID_COLUMN]:
                synced_feeds += 1

        if not synced_feeds:
            return

        # Update read/unread status
        hildon.hildon_banner_show_information(self, '', _('Synchronizing read/unread status with Google Reader'))
        hildon.hildon_gtk_window_set_progress_indicator(self, True)
        self.manager.sync_google_reader_read_status(self._sync_google_reader_read_status_cb)

    def _feeds_synchronized(self, retval, user_data, error):

        urls, label_feeds = retval
        hildon.hildon_gtk_window_set_progress_indicator(self, False)
        if urls == None:
            hildon.hildon_banner_show_information(self, '', _('Error synchronizing feeds'))
            return
        elif urls == []:
            hildon.hildon_banner_show_information(self, '', _('No feeds in Google Reader to synchronize'))
            return

        # Update sync status of current feeds. We use the info from
        # the model in order to properly update the UI
        store = self.view.get_model().get_model()
        for row in store:
            summary = self.manager.get_feed_summary(row[self.FEEDS_MODEL_ID_COLUMN])
            if summary.href in urls:
                if not summary.sync:
                    summary.sync = True
                    row[self.FEEDS_MODEL_SYNC_COLUMN] = True
                urls.remove(summary.href)
            else:
                if summary.sync:
                    summary.sync = False
                    row[self.FEEDS_MODEL_SYNC_COLUMN] = False

        if urls:
            # Add feeds to UI asynchronously
            self._add_multiple_feeds(urls, True, self._all_synchronized_feeds_added_cb, label_feeds)

    def _preferences_response_cb(self, dialog, response):

        if response == gtk.RESPONSE_DELETE_EVENT:
            dialog.destroy()
            return

        if response == SettingsDialog.RESPONSE_SYNC_GOOGLE:
            if self.settings.user=='' or self.settings.password=='':
                hildon.hildon_banner_show_information(self, '', _('Missing user name and/or password'))
                return

        # Save settings. We do this if the users click Save or Synchronize Now
        sync_global_before = self.settings.sync_global
        dialog.save_settings(self.settings)
        dialog.destroy()

        # Update rotation
        if self._rotation_manager:
            self._rotation_manager.set_mode(self.settings.rotation_mode)

        if (self.settings.sync_global and not sync_global_before) or \
                response == SettingsDialog.RESPONSE_SYNC_GOOGLE:
            hildon.hildon_gtk_window_set_progress_indicator(self, True)
            self.manager.sync_with_google_reader(self._feeds_synchronized)

    def _feed_exported_cb(self, retval, user_data, error):
        if not error:
            message = _('Feeds exported')
        else:
            message = _('Error exporting feeds')
        hildon.hildon_banner_show_information(self, '', message)
        # Remove progress information
        hildon.hildon_gtk_window_set_progress_indicator(self, False)

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

        self._check_label_menu_options_visibility()
        dialog.destroy()

    def _add_feed_to_label_cb(self, button):
        dialog = FeedSelectionDialog(self, self.manager, gtk.STOCK_ADD, True, self._filter_label_id)
        dialog.connect('response', self._feeds_selected_cb, True)
        dialog.show()

    def _remove_feed_from_label_cb(self, button):
        dialog = FeedSelectionDialog(self, self.manager, gtk.STOCK_REMOVE, False, self._filter_label_id)
        dialog.connect('response', self._feeds_selected_cb, False)
        dialog.show()

    def _initial_dialog_new_cb(self, button, dialog):
        dialog.hide()
        self._new_feed_cb(button)
        dialog.destroy()

    def _initial_dialog_import_cb(self, button, dialog):
        dialog.hide()
        self._import_feed_cb(button)
        dialog.destroy()

    def _initial_dialog_find_cb(self, button, dialog):
        dialog.hide()
        self._find_feed_cb(button)
        dialog.destroy()

    def _initial_dialog_sync_google_cb(self, button, dialog):
        dialog.destroy()

        # Let's assume that the user wants to enable Google Reader synchronization
        self.settings.sync_global = True

        if self.settings.user=='' or self.settings.password=='':
            hildon.hildon_banner_show_information(self, '', _('Missing user name and/or password'))
            dialog = SettingsDialog(self, self.settings)
            dialog.connect('response', self._preferences_response_cb)
            dialog.show_all()
            dialog.jump_to_google_reader_auth()
        else:
            hildon.hildon_gtk_window_set_progress_indicator(self, True)
            hildon.hildon_banner_show_information(self, '', _('Connecting to Google Reader'))
            self.manager.sync_with_google_reader(self._feeds_synchronized)

    def _show_initial_dialog(self):
        dialog = gtk.Dialog()
        dialog.set_title(_('Start adding feeds'))

        # Create buttons
        add_feed_button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        add_feed_button.set_label(_('New feed'))
        add_feed_button.connect('clicked', self._initial_dialog_new_cb, dialog)

        import_feed_button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        import_feed_button.set_label(_('Import Feeds'))
        import_feed_button.connect('clicked', self._initial_dialog_import_cb, dialog)

        find_feed_button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        find_feed_button.set_label(_('Find Feeds'))
        find_feed_button.connect('clicked', self._initial_dialog_find_cb, dialog)

        sync_google_button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        sync_google_button.set_label(_('Get from Google Reader'))
        sync_google_button.connect('clicked', self._initial_dialog_sync_google_cb, dialog)

        dialog.vbox.add(add_feed_button)
        dialog.vbox.add(import_feed_button)
        dialog.vbox.add(find_feed_button)
        dialog.vbox.add(sync_google_button)

        add_feed_button.show()
        import_feed_button.show()
        find_feed_button.show()
        sync_google_button.show()
        dialog.show()

    def _feeds_summary_loaded(self, feeds_summary, user_data, error):
        glib.source_remove(self._load_tag)
        hildon.hildon_gtk_window_set_progress_indicator(self, False)

        # If there is no data then show a dialog
        if not feeds_summary:
            self._show_initial_dialog()
            return

        # Iterate over summaries and fill the model
        model_filter = self.view.get_model()
        store = model_filter.get_model()
        for summary in feeds_summary:
            feed_iter = store.append()
            visible = self.manager.feed_has_label(summary.feed_id, self._filter_label_id)
            store.set(feed_iter,
                      self.FEEDS_MODEL_TITLE_COLUMN, get_feed_title_markup(summary.title),
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

        # Auto-update feeds
        if self.settings.auto_update_startup:
            self._update_multiple_feeds(self._all_feeds_updated_cb)

    def _get_favicon_cb(self, pixbuf, row_reference, error):
        if pixbuf == None:
            return

        store = self.view.get_model().get_model()
        feed_iter = store.get_iter(row_reference.get_path())
        store.set(feed_iter, self.FEEDS_MODEL_PIXBUF_COLUMN, pixbuf)

    def _find_feed_response_cb(self, dialog, response):
        if response == gtk.RESPONSE_ACCEPT:
            keywords = dialog.entry.get_text()

            # Quickly show feedback to user
            hildon.hildon_gtk_window_set_progress_indicator(dialog, True)

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
            hildon.hildon_banner_show_information(self, '', _('Error finding feeds. Server error.'))
            dialog.destroy()
            return

        news_window = FindWindow(feeds_info, self)
        news_window.show()

        news_window.connect('urls-found', self._find_window_urls_found_cb)

        dialog.set_response_sensitive(gtk.RESPONSE_ACCEPT, True)
        hildon.hildon_gtk_window_set_progress_indicator(dialog, False)

        dialog.destroy()

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

    def _export_feed_cb(self, button):
        stack = hildon.WindowStack.get_default()
        window = stack.peek()

        chooser = hildon.FileChooserDialog(window, gtk.FILE_CHOOSER_ACTION_SAVE)
        chooser.set_transient_for(window)
        # Don't like this at all. Isn't there any define in the platform ?
        chooser.set_current_folder(constants.MYDOCS_DIR)
        chooser.set_current_name('resistance-feeds')

        #Overwrite the file if already exists
        chooser.set_do_overwrite_confirmation(True)
        chooser.set_default_response(gtk.RESPONSE_OK)

        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            hildon.hildon_gtk_window_set_progress_indicator(self, True)
            self.manager.export_opml(chooser.get_filename() + '.opml', self._feed_exported_cb)
        elif response == gtk.RESPONSE_CANCEL:
            print 'Closed, no files selected'
        chooser.destroy()

    def _import_feed_cb(self, button):
        stack = hildon.WindowStack.get_default()
        window = stack.peek()

        #Calling a file chooser
        chooser = hildon.FileChooserDialog(window ,gtk.FILE_CHOOSER_ACTION_OPEN)
        chooser.set_transient_for(window)
        # Don't like this at all. Isn't there any define in the platform ?
        chooser.set_current_folder(constants.MYDOCS_DIR)
        chooser.set_default_response(gtk.RESPONSE_OK)

        #Filter for opml files
        filter = gtk.FileFilter()
        filter.set_name("OPML")
        filter.add_pattern("*.opml")
        chooser.add_filter(filter)

        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            hildon.hildon_gtk_window_set_progress_indicator(self, True)
            self.manager.import_opml(chooser.get_filename(), self._import_opml_cb)
        elif response == gtk.RESPONSE_CANCEL:
            print 'Closed, no files selected'

        chooser.destroy()

    def _import_opml_cb(self, feed_url_list, data, error):
        hildon.hildon_gtk_window_set_progress_indicator(self, False)
        if error:
            hildon.hildon_banner_show_information(self, '', _('Error importing feeds OPML file'))
            return

        if len(feed_url_list) == 0:
            hildon.hildon_banner_show_information(self, '', _('No feeds to import in OPML file'))
            return

        hildon.hildon_gtk_window_set_progress_indicator(self, True)
        self._add_multiple_feeds(feed_url_list, callback=self._save_feeds_after_multiple_add)

    def _find_feed_cb(self, button):
        dialog = InputTextDialog(self, _('Find Feeds'), _('Find'), _('Keywords'),
                                 gtk.HILDON_GTK_INPUT_MODE_FULL | gtk.HILDON_GTK_INPUT_MODE_AUTOCAP | gtk.HILDON_GTK_INPUT_MODE_DICTIONARY)
        dialog.connect('response', self._find_feed_response_cb)
        dialog.show_all()

    def _on_feed_added_update_label(self, manager, feed_id):
        if self._filter_label_id == constants.ALL_LABEL_ID:
            return
        self.manager.add_feeds_to_label([feed_id], self._filter_label_id)

class EntriesView(hildon.GtkTreeView):

    def __init__(self, feed_title, ui_mode):
        super(EntriesView, self).__init__(ui_mode)

        self.fallback_author = feed_title

        # Add columns
        pix_renderer = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn('Icon', pix_renderer, pixbuf = 0)
        self.append_column(column);

        text_renderer = gtk.CellRendererText()
        text_renderer.set_property('ellipsize', ELLIPSIZE_END)
        column = gtk.TreeViewColumn('Name', text_renderer, markup = EntriesWindow.ENTRIES_MODEL_TEXT_COLUMN)
        column.set_expand(True)
        self.append_column(column);

        date_renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Date', date_renderer, markup = EntriesWindow.ENTRIES_MODEL_DATE_COLUMN)
        column.set_expand(False)
        self.append_column(column);

    def get_visual_entry_text(self, entry):

        # TODO: show entry.summary ?
        author = get_author_from_item(entry)
        if author == '':
            author = self.fallback_author

        if 'read' in entry and entry['read'] == True:
            color = SECONDARY_TEXT_COLOR
        else:
            color = ACTIVE_TEXT_COLOR

        return '<span foreground="' + color + '">' \
            + gobject.markup_escape_text(unescape(author)) \
            + '</span>\n<span size="small">' \
            + get_title_from_item(entry) + '</span>'

class EntriesWindow(hildon.StackableWindow):

    ENTRIES_MODEL_TEXT_COLUMN = 1
    ENTRIES_MODEL_DATA_COLUMN = 2
    ENTRIES_MODEL_DATE_COLUMN = 3
    ENTRIES_MODEL_DATE_PARSED_COLUMN = 4

    def __init__(self, feed_data, manager, settings, conn_manager):
        super(EntriesWindow, self).__init__()

        self.manager = manager
        self.settings = settings
        self.feed_data = feed_data
        self._conn_manager = conn_manager

        self.set_title(unescape(self.feed_data.feed.title))
        self.toolbar = gtk.Toolbar()

        # Edit toolbar
        self.edit_toolbar_button_handler = 0
        self.edit_toolbar = hildon.EditToolbar()
        self.edit_toolbar.connect('arrow-clicked', self._restore_normal_mode)

        # Feeds
        self.view = EntriesView(feed_data.feed.title, gtk.HILDON_UI_MODE_NORMAL)
        entries_model = gtk.ListStore(gtk.gdk.Pixbuf, str, gobject.TYPE_PYOBJECT, str, int)
        entries_model.set_sort_column_id(self.ENTRIES_MODEL_DATE_PARSED_COLUMN, gtk.SORT_DESCENDING)
        filter_model = entries_model.filter_new()
        filter_model.set_visible_func(self._row_visible_cb)
        self.view.set_model (filter_model)
        self.view.connect ("row-activated", self._on_entry_activated)
        self.view.show()

        # Draw entries
        self._add_entries()

        self.align = gtk.Alignment(0, 0, 1, 1)
        self.align.set_padding(4, 0 , 16, 16)

        pannable = hildon.PannableArea()
        pannable.add (self.view)
        pannable.set_size_request_policy(hildon.SIZE_REQUEST_CHILDREN)
        pannable.show()

        self.align.add(pannable)
        self.add(self.align)
        self.align.show()

        # Update feed button
        action_box = hildon.GtkTreeView.get_action_area_box(self.view)
        self._update_feed_button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self._update_feed_button.set_label(_('Update feed'))
        self._update_feed_button.connect('clicked', self._update_feed_cb)

        action_box.pack_start(self._update_feed_button, True, True)

        self._create_menu()

        if 'itunes' not in self.feed_data.namespaces:
            self._download_all_button.hide()

        self.connect('configure-event', self._on_configuration_changed)
        self.connect('hide', self._on_hide)

        # Force online/offline status evaluation
        self._connection_changed_id = self._conn_manager.connect('connection-changed', self._on_connection_changed)
        self._on_connection_changed(self._conn_manager)

    def _on_hide(self, window):
        # Do not listen for conn-changed events anymore. Causes
        # crashes when changing the connection after closing the
        # window
        if self._conn_manager.handler_is_connected(self._connection_changed_id):
            self._conn_manager.disconnect(self._connection_changed_id)

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
                      self.ENTRIES_MODEL_DATE_COLUMN, get_visual_entry_date(entry, True),
                      self.ENTRIES_MODEL_DATE_PARSED_COLUMN, calendar.timegm(date) if date else 0)

    def _on_connection_changed(self, conn_manager):
        if conn_manager.is_online():
            self._update_feed_button.show()
            # Check that we should not show it
            if 'itunes' in self.feed_data.namespaces:
                self._download_all_button.show()
            self._sync_feed_button.show()
            self.view.set_action_area_visible(True)
        else:
            self._update_feed_button.hide()
            self._download_all_button.hide()
            self._sync_feed_button.hide()
            self.view.set_action_area_visible(False)

    def _create_menu(self):
        menu = hildon.AppMenu()

        # Sorting filter
        self._all_filter_button = hildon.GtkRadioButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self._all_filter_button.set_mode(False)
        self._all_filter_button.set_label(_('Show All'))
        self._all_filter_button.connect('toggled', self._show_all_cb)
        menu.add_filter(self._all_filter_button)

        self._unread_filter_button = hildon.GtkRadioButton(gtk.HILDON_SIZE_FINGER_HEIGHT,
                                                           group = self._all_filter_button)
        self._unread_filter_button.set_mode(False)
        self._unread_filter_button.set_label(_('Show Unread'))
        self._unread_filter_button.connect('toggled', self._show_unread_cb)
        menu.add_filter(self._unread_filter_button)

        if self.settings.entries_filter == constants.SHOW_UNREAD_FILTER:
            self._unread_filter_button.set_active(True)

        button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        button.set_label(_('Mark Entries as Read'))
        button.connect('clicked', self._mark_read_cb, True)
        menu.append(button)

        button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        button.set_label(_('Mark Entries as Not Read'))
        button.connect('clicked', self._mark_read_cb, False)
        menu.append(button)

        self._download_all_button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self._download_all_button.set_label(_('Download all'))
        self._download_all_button.connect('clicked', self._download_all_items_cb)
        menu.append(self._download_all_button)

        self._sync_feed_button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        summary = self.manager.get_feed_summary(get_feed_id(self.feed_data))
        label = _('Remove from Google Reader') if summary.sync else _('Add to Google Reader')
        self._sync_feed_button.set_label(label)
        self._sync_feed_button.connect('clicked', self._subscribe_feed_cb)
        menu.append(self._sync_feed_button)

        menu.show_all()
        self.set_app_menu(menu)

    def _show_unread_cb(self, button):
        if not button.get_active():
            return
        self.settings.entries_filter = constants.SHOW_UNREAD_FILTER
        self.view.get_model().refilter()

    def _show_all_cb(self, button):
        if not button.get_active():
            return
        self.settings.entries_filter = constants.SHOW_ALL_FILTER
        self.view.get_model().refilter()

    def _subscribe_feed_cb(self, button):
        hildon.hildon_gtk_window_set_progress_indicator(self, True)

        # Disable buttons while subscription takes place
        self._update_feed_button.set_sensitive(False)
        self._sync_feed_button.set_sensitive(False)

        summary = self.manager.get_feed_summary(get_feed_id(self.feed_data))
        self.manager.subscribe_feed_google(summary.href, not summary.sync, self._feed_subscribed_cb)

    def _feed_subscribed_cb(self, synced, user_data, error):
        hildon.hildon_gtk_window_set_progress_indicator(self, False)
        summary = self.manager.get_feed_summary(get_feed_id(self.feed_data))

        if not synced:
            if summary.sync:
                message = _('Error removing from Google Reader')
            else:
                message = _('Error adding to Google Reader')
        else:
            summary.sync = not summary.sync
            if summary.sync:
                message = _('Added to Google Reader')
            else:
                message = _('Removed from Google Reader')

        hildon.hildon_banner_show_information(self, '', message)

        # Update the menu
        label = _('Remove from Google Reader') if summary.sync else _('Add to Google Reader')
        self._sync_feed_button.set_label(label)

        # Restore sensitiviness
        self._sync_feed_button.set_sensitive(True)
        self._update_feed_button.set_sensitive(True)

    def _sync_google_reader_read_status_cb(self, synced, user_data, error):
        hildon.hildon_gtk_window_set_progress_indicator(self, False)
        self._update_feed_button.set_sensitive(True)

        if not synced:
            hildon.hildon_banner_show_information(self, '', _('Error syncing read status with Google Reader'))
            return

    def _mark_read_cb(self, button, read):
        # tree view edit mode
        hildon.hildon_gtk_tree_view_set_ui_mode(self.view, gtk.HILDON_UI_MODE_EDIT)
        self.view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.view.get_selection().unselect_all()

        if read:
            self.edit_toolbar.set_label(_('Select Feeds to mark as Read'))
        else:
            self.edit_toolbar.set_label(_('Select Feeds to mark as Not Read'))
        self.edit_toolbar.set_button_label(_('Mark'))
        if self.edit_toolbar.handler_is_connected (self.edit_toolbar_button_handler):
            self.edit_toolbar.disconnect(self.edit_toolbar_button_handler)
        self.edit_toolbar_button_handler = \
            self.edit_toolbar.connect('button-clicked', self._mark_read_button_clicked_cb, read)

        self.set_edit_toolbar(self.edit_toolbar)
        self.edit_toolbar.show()
        self.fullscreen()

    def _mark_read_button_clicked_cb(self, button, read):
        selection = self.view.get_selection()
        selected_rows = selection.get_selected_rows()
        model, paths = selected_rows
        if not paths:
            hildon.hildon_banner_show_information(self, '', _('Please select at least one Entry'))
            return

        summary = self.manager.get_feed_summary(get_feed_id(self.feed_data))
        online = self._conn_manager.is_online()
        for path in paths:
            entry = model[path][self.ENTRIES_MODEL_DATA_COLUMN]
            entry.read = read
            child_path = model.convert_path_to_child_path(path)
            model.get_model()[child_path][self.ENTRIES_MODEL_TEXT_COLUMN] = self.view.get_visual_entry_text(entry)
            if summary.sync and online:
                self.manager.mark_as_read_synchronize(self.feed_data.href, model[path][2].link,
                                                      read, self._mark_as_read_sync_cb)

        # restore normal mode
        self._restore_normal_mode(button)

    def _mark_as_read_sync_cb(self, synced, user_data, error):
        if not synced:
            hildon.hildon_banner_show_information(self, '', _('Error syncing read status with Google Reader'))

    def _restore_normal_mode(self, button):

        # tree view normal mode
        hildon.hildon_gtk_tree_view_set_ui_mode(self.view, gtk.HILDON_UI_MODE_NORMAL)
        self.view.get_selection().unselect_all()

        self.edit_toolbar.hide()
        self.unfullscreen()

    def _on_entry_activated(self, treeview, path, column):
        item_window = ItemWindow(self.feed_data, self.manager, self.settings, self._conn_manager)

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

        # Mark item as read in Google Reader. Do it in an idle as we
        # don't want to delay the item rendering
        summary = self.manager.get_feed_summary(get_feed_id(self.feed_data))
        if summary.sync and self._conn_manager.is_online():
            glib.idle_add(self._mark_as_read_google_idle_cb, entry)

    def _mark_as_read_google_idle_cb(self, entry):
        if not self._conn_manager.is_online():
            return

        self.manager.mark_as_read_synchronize(self.feed_data.href, entry.link, True,
                                              self._mark_as_read_google_cb)
        return False

    def _mark_as_read_google_cb(self, synced, user_data, error):
        if not synced:
            hildon.hildon_banner_show_information(self, '', _('Error syncing read status with Google Reader'))

    def _update_feed_cb(self, button):
        url = self.feed_data.href

        # Quickly show feedback to user
        hildon.hildon_gtk_window_set_progress_indicator(self, True)
        button.set_sensitive(False)

        # Ask manager to update feed
        self.manager.update_feed(get_feed_id(self.feed_data), self._feed_updated_cb, None)

    def _feed_updated_cb(self, retval, data, error):

        summary = self.manager.get_feed_summary(get_feed_id(self.feed_data))
        # Update read/unread status if the feed was subscribed
        if summary.sync:
            hildon.hildon_banner_show_information(self, '', _('Synchronizing read/unread status with Google Reader'))
            self.manager.sync_google_reader_read_status(self._sync_google_reader_read_status_cb)
        else:
            hildon.hildon_gtk_window_set_progress_indicator(self, False)
            self._update_feed_button.set_sensitive(True)

        self.view.get_model().get_model().clear()
        self._add_entries()

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

        hildon.hildon_gtk_window_set_progress_indicator(self, True)

        self.manager.download_all_items(urls, paths_files, self._all_items_downloaded_cb)

    def _all_items_downloaded_cb(self, downloaded, user_data, error):
        if downloaded:
            message = _('Items downloaded')
        else:
            message = _('Error downloading items')
        hildon.hildon_banner_show_information(self, '', message)
        # Remove progress information
        hildon.hildon_gtk_window_set_progress_indicator(self, False)

    def _on_configuration_changed(self, window, event):
        # Change alignment padding. We don't want padding in portrait
        # Need to save space
        if event.width > event.height:
            self.align.set_padding(4, 0 , 16, 16)
        else:
            self.align.set_padding(4, 0 , 4, 4)

class ItemWindowLandscapeToolbar(gtk.VBox):

    def __init__(self, homogeneous, spacing):
        super(ItemWindowLandscapeToolbar, self).__init__(homogeneous, spacing)

        # Navigation buttons. Sizes are important. We set the size of the icon but
        # we let the button grow as needed
        self.button_up = gtk.Button()
        button_up_img = gtk.Image()
        button_up_img.set_from_icon_name(constants.ICON_UP_NAME,
                                              gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.button_up.set_image(button_up_img)
        self.button_down = gtk.Button()
        button_down_img = gtk.Image()
        button_down_img.set_from_icon_name(constants.ICON_DOWN_NAME,
                                                gtk.HILDON_SIZE_FINGER_HEIGHT)
        self.button_down.set_image(button_down_img)

        self.pack_start(self.button_up, True, True, 0)
        self.pack_start(self.button_down, True, True, 0)
        self.show_all()

class ItemWindow(hildon.StackableWindow):
    __gsignals__ = {
        "item-read": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT, )),
        }

    def __init__(self, feed_data, manager, settings, conn_manager):
        super(ItemWindow, self).__init__()

        self.manager = manager
        self.settings = settings
        self.feed_data = feed_data
        self._item = None
        self._conn_manager = conn_manager
        self._conn_manager.connect('connection-changed', self._on_connection_changed)

        self._osso_context = osso.Context(constants.RSS_COMPACT_NAME, constants.RSS_VERSION, False)
        self._screen_device = osso.DeviceState(self._osso_context)
        self._osso_rpc = osso.Rpc(self._osso_context)

        self._prev_item_reference = None
        self._next_item_reference = None

        # Header
        self.landscape_toolbar = ItemWindowLandscapeToolbar(True, 2)
        self.landscape_toolbar.button_up.connect("clicked", self._up_button_clicked)
        self.landscape_toolbar.button_down.connect("clicked", self._down_button_clicked)

        # HTML renderer
        self.view = WebView()
        self.view.set_full_content_zoom(True)

        # Disable navigation inside ReSiStance. Open links in browser
        self.view.connect('navigation_requested', self._navigation_requested_cb)

        # Disable text selection
        self.view.connect("motion-notify-event", lambda w, ev: True)

        # Set some settings
        wbk_settings = self.view.get_settings()
        wbk_settings.set_property('default_font_size', self.settings.default_font_size)
        wbk_settings.set_property('auto-load-images', self.settings.auto_load_images)
        wbk_settings.set_property('auto-shrink-images', True)

        # Pannable for showing content
        self.pannable = hildon.PannableArea()
        self.pannable.add(self.view)
        self.pannable.set_size_request_policy(hildon.SIZE_REQUEST_CHILDREN)
        self.pannable.set_property("mov-mode", hildon.MOVEMENT_MODE_BOTH)
        self.view.show()

        hbox = gtk.HBox(False, 4)
        hbox.pack_start(self.pannable, True, True)
        hbox.pack_start(self.landscape_toolbar, False, False)
        self.landscape_toolbar.show()
        self.pannable.show()

        self.add(hbox)
        hbox.show()

        self._create_menu()
        self._create_toolbar()

        # For portrait/landscape modes
        self.connect('configure-event', self._on_configuration_changed)

    def _on_connection_changed(self, conn_manager):
        if conn_manager.is_online() and 'enclosures' in self._item \
                and len(self._item.enclosures) > 0:
            self._download_button.show()
        else:
            self._download_button.hide()

    def _on_configuration_changed(self, window, event):

        # Show toolbar in portrait mode. Show header in landscape mode
        if event.width > event.height:
            self.pannable.set_property("mov-mode", hildon.MOVEMENT_MODE_BOTH)
            self.landscape_toolbar.show_all()
            self.toolbar.hide_all()
        else:
            self.pannable.set_property("mov-mode", hildon.MOVEMENT_MODE_VERT)
            self.landscape_toolbar.hide()
            self.toolbar.show_all()

    def _create_toolbar(self):

        self.toolbar = gtk.Toolbar()
        button_prev_img = gtk.Image()
        button_prev_img.set_from_icon_name(constants.ICON_UP_NAME,
                                           gtk.HILDON_SIZE_FINGER_HEIGHT)
        button_prev = gtk.ToolButton(button_prev_img, None)

        button_next_img = gtk.Image()
        button_next_img.set_from_icon_name(constants.ICON_DOWN_NAME,
                                           gtk.HILDON_SIZE_FINGER_HEIGHT)
        button_next = gtk.ToolButton(button_next_img, None)

        button_prev.set_expand(True)
        button_next.set_expand(True)
        button_prev.set_homogeneous(True)
        button_next.set_homogeneous(True)

        self.toolbar.insert (button_prev, -1)
        self.toolbar.insert (button_next, -1)

        button_prev.connect("clicked", self._up_button_clicked)
        button_next.connect("clicked", self._down_button_clicked)

        self.add_toolbar(self.toolbar)

    def _on_request_url(self, object, url, stream):
        if (url.lower().startswith("http")):
            request_thread = Thread(target=self._request_url_in_thread,
                                    args=(url, stream))
            request_thread.start()

    def _request_url_in_thread(self, url, stream):
        f = urllib2.urlopen(url)

        gtk.gdk.threads_enter()
        stream.write(f.read())
        stream.close()
        gtk.gdk.threads_leave()

    def _create_menu(self):
        menu = hildon.AppMenu()

        button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        button.set_label(_('Item Details'))
        button.connect('clicked', self._item_details_cb)
        button.show()
        menu.append(button)

        self._download_button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self._download_button.set_label(_('Download'))
        self._download_button.connect('clicked', self._download_item_cb)
        self._download_button.show()
        menu.append(self._download_button)

        menu.show_all()
        self.set_app_menu(menu)

    def _add_conditional_to_table (self, table, item, attr, label, is_time=False):
        if attr in item and item[attr] != '':
            value = time.strftime('%x', item[attr]) if is_time else item[attr]
            self._add_to_table (table, label, value)

    def _add_to_table (self, table, label_text, value):
        # Two cells per row. So rows = cells/2
        y_coord = len(table)/2

        label = gtk.Label('')
        label.set_markup('<span foreground="%s">%s:</span>' % \
                             (SECONDARY_TEXT_COLOR, label_text))
        label.set_alignment(1.0, 0.5)
        table.attach(label, 0, 1, y_coord, y_coord + 1, gtk.FILL, 0)

        value_label = gtk.Label('')
        value_label.set_markup(value)
        value_label.set_alignment(0.0, 0.5)
        table.attach(value_label, 1, 2, y_coord, y_coord + 1, gtk.FILL, 0)

    def _item_details_cb(self, button):
        dialog = gtk.Dialog()
        dialog.set_title(_('Item Details'))

        pannable = hildon.PannableArea()
        pannable.set_size_request_policy(hildon.SIZE_REQUEST_CHILDREN)
        pannable.set_property("mov-mode", hildon.MOVEMENT_MODE_VERT)

        item = self._item

        table = gtk.Table()
        table.set_row_spacings(6)
        table.set_col_spacings(12)
        self._add_to_table (table, _('Title'), item.title)
        self._add_conditional_to_table (table, item, 'author', _('Author'))
#        self._add_conditional_to_table (table, item, 'link', _('Home Page'))
        self._add_conditional_to_table (table, item, 'updated_parsed', _('Updated'), True)
        self._add_conditional_to_table (table, item, 'published_parsed', _('Published'), True)
        self._add_conditional_to_table (table, item, 'language', _('Language'))
        self._add_conditional_to_table (table, item, 'license', _('License'))
        self._add_conditional_to_table (table, item, 'rights', _('Rigths'))
        self._add_conditional_to_table (table, item, 'generator', _('Generated by'))

        pannable.add_with_viewport(table)

        table.show_all()
        pannable.show()
        dialog.vbox.add(pannable)

        dialog.show()

    def _up_button_clicked(self, button):
        if not self._prev_item_reference or not self._prev_item_reference.valid():
            return

        prev_path = self._prev_item_reference.get_path()
        prev_iter = self.model.get_iter(prev_path)
        if prev_iter:
            item = self.model.get_value(prev_iter, EntriesWindow.ENTRIES_MODEL_DATA_COLUMN)
            self._set_item(item, prev_path)

    def _down_button_clicked(self, button):
        if not self._next_item_reference or not self._next_item_reference.valid():
            return

        next_path = self._next_item_reference.get_path()
        next_iter = self.model.get_iter(next_path)
        if next_iter:
            item = self.model.get_value(next_iter, EntriesWindow.ENTRIES_MODEL_DATA_COLUMN)
            self._set_item(item, next_path)

    def _update_next_prev_references(self, path):
        # Work out previous item path
        # http://faq.pygtk.org/index.py?req=show&file=faq13.051.htp
        position = path[-1]
        if position:
            prev_path = list(path)[:-1]
            prev_path.append(position - 1)
            self._prev_item_reference = gtk.TreeRowReference(self.model, tuple(prev_path))
        else:
            self._prev_item_reference = None

        # Next item path
        next_iter = self.model.iter_next(self.model.get_iter(path))
        if next_iter:
            self._next_item_reference = gtk.TreeRowReference(self.model, self.model.get_path(next_iter))
        else:
            self._next_item_reference = None

    def set_item_from_model(self, model, path):
        self.model = model
        item = model.get_value(model.get_iter(path), EntriesWindow.ENTRIES_MODEL_DATA_COLUMN)
        self._set_item(item, path)

    def _set_item(self, item, path):

        self._item = item

        # Update next&prev references
        self._update_next_prev_references(path)

        author = get_author_from_item(item)
        if author == '':
            author = self.feed_data.feed.title
        self.set_title(unescape(author))

        # Get content type and body
        content_type = 'text/html'
        if 'content' in item:
            # We are only considering the first content. TODO check more?
            if 'type' in item.content[0]:
                content_type = item.content[0].type
            body = item.content[0].value
        elif 'summary' in item:
            if 'summary_detail' in item and 'type' in item.summary_detail:
                content_type = item.summary_detail.type
            body = item.summary
        elif 'title' in item:
            # Yeah I know..., but some weird feeds provide their
            # content in the title. I want to support them anyway
            body = item.title
        else:
            # Should never happen
            body = _('No text')

        # Feed header
        header = '<font size="5"><a href=%s>%s</a></font><br><a href=%s>%s</a> ' % \
            (item.link, get_title_from_item(item), self.feed_data.feed.link, self.feed_data.feed.title)
        # Date is treated separatedely for translation purpouses
        date = _('on %s') % get_visual_entry_date(item,False) if 'updated' in item else ''

        text = ''.join((header, date, '<hr>', body))

        # Write HTML
        try:
            self.view.load_string(text.encode(self.feed_data.encoding), content_type, self.feed_data.encoding, '')
        except UnicodeEncodeError:
            # In case of decoding error then try with UTF-8
            try:
                self.view.load_string(text.encode('utf-8'), content_type, 'utf-8', '')
            except UnicodeEncodeError:
                # Ok, let's fallback to ASCII then...
                try:
                    self.view.load_string(text.encode('us-ascii'), content_type, 'us-ascii', '')
                except UnicodeEncodeError:
                    # If everything else fails, then clear the view and show an error
                    self.view.load_string('', content_type, 'ascii', '')
                    hildon.hildon_banner_show_information(self, '', _('Some text could not be shown'))

        # Update button sensitiviness
        toolbar_button_list = self.toolbar.get_children()
        prev_item_missing = not self._prev_item_reference or not self._prev_item_reference.valid()
        next_item_missing = not self._next_item_reference or not self._next_item_reference.valid()

        self.landscape_toolbar.button_up.set_sensitive(not prev_item_missing)
        toolbar_button_list[0].set_sensitive(not prev_item_missing)
        self.landscape_toolbar.button_down.set_sensitive(not next_item_missing)
        toolbar_button_list[1].set_sensitive(not next_item_missing)

        # Mark item as read
        if not item.read:
            self.emit('item-read', path)

        # Force online/offline status evaluation
        self._on_connection_changed(self._conn_manager)

        # Keep the display on for 60" without user input.
        self._screen_device.display_blanking_pause()

    def _navigation_requested_cb(self, web_view, web_frame, navigation_request):
        print 'loading ' + navigation_request.get_uri()
        # Open link in a web browser
        self._osso_rpc.rpc_run_with_defaults("osso_browser", "open_new_window",
                                             (navigation_request.get_uri(),))
        # Just deny navigation. Note that there seem not to be any
        # define for data and we have to use an ugly plain 1
        return 1

    def _download_item_cb(self, button):
        url_file = self._item.enclosures[0]['href']
        file = os.path.basename(urllib.url2pathname(url_file))
        folder = self.settings.auto_download_folder

        hildon.hildon_gtk_window_set_progress_indicator(self, True)
        self.manager.download_item(url_file, folder+file, self._item_downloaded_cb)

    def _item_downloaded_cb(self, downloaded, user_data, error):
        if downloaded:
            message = _('Item downloaded')
        else:
            message = _('Error downloading item')
        hildon.hildon_banner_show_information(self, '', message)
        # Remove progress information
        hildon.hildon_gtk_window_set_progress_indicator(self, False)

class FindWindow(hildon.StackableWindow):
    __gsignals__ = {
        "urls-found": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT, )),
        }

    FIND_MODEL_SITE_COLUMN = 0
    FIND_MODEL_URL_COLUMN = 1

    def __init__(self, feedsinfo, feedsWindow):
        super(FindWindow, self).__init__()

        self.feeds_info = feedsinfo

        self.view = hildon.GtkTreeView(gtk.HILDON_UI_MODE_EDIT)
        text_renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Name', text_renderer, markup=0)
        column.set_expand(True)
        self.view.append_column(column)
        self.view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.view.get_selection().unselect_all()

        self.edit_toolbar = hildon.EditToolbar()

        self.edit_toolbar_button_handler = 0
        self.edit_toolbar.set_label(_('Select Feeds to add'))
        self.edit_toolbar.set_button_label(_('Add'))
        self.edit_toolbar.connect('arrow-clicked', self._restore_normal_mode)

        if self.edit_toolbar.handler_is_connected (self.edit_toolbar_button_handler):
            self.edit_toolbar.disconnect(self.edit_toolbar_button_handler)
        self.edit_toolbar_button_handler = \
            self.edit_toolbar.connect('button-clicked', self._add_button_clicked_cb, feedsWindow)

        self.set_edit_toolbar(self.edit_toolbar)
        self.edit_toolbar.show()
        self.fullscreen()

        self.view.set_model (gtk.ListStore(str, str))

        store = self.view.get_model()

        for feed_info in self.feeds_info:
            feed_iter = store.append()

            store.set(feed_iter,
                      self.FIND_MODEL_SITE_COLUMN, gobject.markup_escape_text(unescape(feed_info['sitename'])),
                      self.FIND_MODEL_URL_COLUMN, feed_info['dataurl'])

        self.view.show()

        self.align = gtk.Alignment(0, 0, 1, 1)
        self.align.set_padding(4, 0 , 16, 16)

        pannable = hildon.PannableArea()
        pannable.add (self.view)
        pannable.set_size_request_policy(hildon.SIZE_REQUEST_CHILDREN)
        pannable.show()

        self.align.add(pannable)
        self.add(self.align)
        self.align.show()


    def _add_button_clicked_cb(self, button, feedsWindow):
        selection = self.view.get_selection()
        selected_rows = selection.get_selected_rows()
        model, paths = selected_rows
        if not paths:
            hildon.hildon_banner_show_information(self, '', _('Please select at least one Feed'))
            return

        urls = [model[path][self.FIND_MODEL_URL_COLUMN] for path in paths]

        self.emit('urls-found', urls)

        # restore normal mode
        self._restore_normal_mode(button)

    def _restore_normal_mode(self, button):
        self.destroy()

class FeedSelectionDialog(gtk.Dialog):
    FEED_SELECT_MODEL_PIXBUF_COLUMN, FEED_SELECT_MODEL_NAME_COLUMN, FEED_SELECT_MODEL_ID_COLUMN = range(3)

    def __init__(self, parent, manager, button_label, exclude, label_id):
        super(FeedSelectionDialog, self).__init__(_('Select Feeds'), parent,
                                                  gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                                  (button_label, gtk.RESPONSE_ACCEPT))

        self._selector = hildon.TouchSelector()

        # Populate selector
        store = gtk.ListStore(gtk.gdk.Pixbuf, str, int)
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

        # We cannot pass None, so we create a temporary cell renderer and then clear it
        column = self._selector.append_column(store, gtk.CellRendererText())
        column.clear()

        # Favicon column
        pixbuf_renderer = gtk.CellRendererPixbuf()
        pixbuf_renderer.set_property('xpad', 4)
        column.pack_start(pixbuf_renderer, False)
        column.add_attribute(pixbuf_renderer, 'pixbuf', FeedSelectionDialog.FEED_SELECT_MODEL_PIXBUF_COLUMN)

        # Add the column to the TouchSelector
        text_renderer = gtk.CellRendererText()
        text_renderer.set_property('xpad', 4)
        column.pack_start(text_renderer, True)
        column.add_attribute(text_renderer, 'markup', FeedSelectionDialog.FEED_SELECT_MODEL_NAME_COLUMN)
        column.set_property('text-column', FeedSelectionDialog.FEED_SELECT_MODEL_NAME_COLUMN)

        self._selector.set_column_selection_mode(hildon.TOUCH_SELECTOR_SELECTION_MODE_MULTIPLE)

        self.vbox.add(self._selector)
        self._selector.show()

        self._selector.connect("changed", self._selection_changed)
        self._selector.unselect_all(0)

        self.set_default_size(-1, 300)

    def _get_favicon_cb(self, pixbuf, row_reference, error):
        if pixbuf == None:
            return

        store = self._selector.get_model(0)
        feed_iter = store.get_iter(row_reference.get_path())
        store.set(feed_iter, FeedSelectionDialog.FEED_SELECT_MODEL_PIXBUF_COLUMN, pixbuf)

    def _selection_changed(self, selector, user_data):
        rows = selector.get_selected_rows(0)
        self.set_response_sensitive(gtk.RESPONSE_ACCEPT, False if len(rows) == 0 else True)

    def get_selected_feed_ids(self):
        current_selection = self._selector.get_selected_rows(0)
        return [self._selector.get_model(0)[path][FeedSelectionDialog.FEED_SELECT_MODEL_ID_COLUMN] \
                    for path in current_selection]

class LabelsWindow(hildon.StackableWindow):

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

        self._view = hildon.GtkTreeView(gtk.HILDON_UI_MODE_NORMAL)

        pixbuf_renderer = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn('Icon', pixbuf_renderer, pixbuf=LabelsWindow.LABELS_MODEL_PIXBUF_COLUMN)
        column.set_expand(False)
        self._view.append_column(column)

        text_renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Name', text_renderer, markup=LabelsWindow.LABELS_MODEL_NAME_COLUMN)
        column.set_expand(True)
        self._view.append_column(column)

        self._view.connect ("row-activated", self._on_label_activated)
        self._view.show()

        # Sorting by name but with some exceptions
        #   All Feeds
        #   Feed a
        #   Feed b
        store = gtk.ListStore(gtk.gdk.Pixbuf, str, int)
        self._view.set_model(store)
        store.set_sort_column_id(LabelsWindow.LABELS_MODEL_NAME_COLUMN, gtk.SORT_ASCENDING)
        store.set_sort_func(LabelsWindow.LABELS_MODEL_NAME_COLUMN, self._label_sort_func)

        self.set_title(constants.RSS_NAME)
        self._create_menu()

        # Edit toolbar
        self.edit_toolbar_button_handler = 0
        self.edit_toolbar = hildon.EditToolbar()
        self.edit_toolbar.connect('arrow-clicked', self._restore_normal_mode)
        self.set_edit_toolbar(self.edit_toolbar)

        self.align = gtk.Alignment(0, 0, 1, 1)
        self.align.set_padding(4, 0 , 16, 16)

        pannable = hildon.PannableArea()
        pannable.add (self._view)
        pannable.set_size_request_policy(hildon.SIZE_REQUEST_CHILDREN)
        pannable.show()

        self.align.add(pannable)
        self.add(self.align)
        self.align.show()

        # Load Labels (could be none)
        self._manager.load_labels(self._load_labels_cb)

    def set_rotation_manager(self, rotation_manager):
        self._rotation_manager = rotation_manager

    def _get_folder_icon(self):
        if not self._folder_icon:
            self._folder_icon = gtk.icon_theme_get_default().load_icon('general_folder', 32, 0)
        return self._folder_icon

    def _label_sort_func(self, store, iter1, iter2):
        label_row1 = store[iter1]
        label_row2 = store[iter2]

        if label_row1[LabelsWindow.LABELS_MODEL_ID_COLUMN] == constants.ALL_LABEL_ID:
            return -1
        if label_row2[LabelsWindow.LABELS_MODEL_ID_COLUMN] == constants.ALL_LABEL_ID:
            return 1

        # Pretty sure that should be a more Python-ish way to do this
        if label_row1[LabelsWindow.LABELS_MODEL_NAME_COLUMN] > label_row2[LabelsWindow.LABELS_MODEL_NAME_COLUMN]:
            return 1
        elif label_row1[LabelsWindow.LABELS_MODEL_NAME_COLUMN] == label_row2[LabelsWindow.LABELS_MODEL_NAME_COLUMN]:
            return 0
        else:
            return -1

    def _load_labels_cb(self, retval, user_data, error):
        if error:
            hildon.hildon_banner_show_information(self, '', _('Error loading labels.'))
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
        all_feeds_icon = gtk.icon_theme_get_default().load_icon('general_web', 32, 0)
        feed_iter = store.append()
        store.set(feed_iter, LabelsWindow.LABELS_MODEL_NAME_COLUMN, _('All Feeds'),
                  LabelsWindow.LABELS_MODEL_ID_COLUMN, constants.ALL_LABEL_ID,
                  LabelsWindow.LABELS_MODEL_PIXBUF_COLUMN, all_feeds_icon)

        if len(labels) == 0:
            self._remove_button.hide()

    def _create_menu(self):
        menu = hildon.AppMenu()

        button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        button.set_label(_('New Label'))
        button.connect('clicked', self._create_label_cb)
        menu.append(button)

        self._remove_button = hildon.GtkButton(gtk.HILDON_SIZE_FINGER_HEIGHT)
        self._remove_button.set_label(_('Remove Label'))
        self._remove_button.connect('clicked', self._remove_label_cb)
        menu.append(self._remove_button)

        menu.show_all()
        self.set_app_menu(menu)

    def _create_label_cb(self, button):
        dialog = InputTextDialog(self, _('Create Label'), _('Create'), _('Name'),
                                 gtk.HILDON_GTK_INPUT_MODE_FULL | gtk.HILDON_GTK_INPUT_MODE_AUTOCAP | gtk.HILDON_GTK_INPUT_MODE_DICTIONARY)
        dialog.connect('response', self._create_label_response_cb)
        dialog.show_all()

    def _on_label_created_cb(self, manager, label_id):
        label_name = manager.get_label_name(label_id)

        # Add label to the view
        store = self._view.get_model()
        feed_iter = store.append()
        store.set(feed_iter, LabelsWindow.LABELS_MODEL_NAME_COLUMN, gobject.markup_escape_text(label_name),
                  LabelsWindow.LABELS_MODEL_ID_COLUMN, label_id,
                  LabelsWindow.LABELS_MODEL_PIXBUF_COLUMN, self._get_folder_icon())

        self._remove_button.show()

    def _create_label_response_cb(self, dialog, response):
        if response != gtk.RESPONSE_ACCEPT:
            return

        # We do not need to add it to the view. The 'label-created'
        # signal handler will do it for us.
        label_name = dialog.entry.get_text()
        label_id = self._manager.create_label(label_name)

        if not label_id:
            hildon.hildon_banner_show_information(self, '', _('Label not created. Already exists.'))
            dialog.destroy()
            return

        dialog.destroy()

    def _remove_label_cb(self, button):
        # tree view edit mode
        hildon.hildon_gtk_tree_view_set_ui_mode(self._view, gtk.HILDON_UI_MODE_EDIT)
        self._view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self._view.get_selection().unselect_all()

        self.edit_toolbar.set_label(_('Select Labels to remove'))
        self.edit_toolbar.set_button_label(_('Remove'))
        if self.edit_toolbar.handler_is_connected (self.edit_toolbar_button_handler):
            self.edit_toolbar.disconnect(self.edit_toolbar_button_handler)
        self.edit_toolbar_button_handler = \
            self.edit_toolbar.connect('button-clicked', self._remove_label_button_clicked_cb)

        self.set_edit_toolbar(self.edit_toolbar)
        self.edit_toolbar.show()
        self.fullscreen()

    def _remove_label_button_clicked_cb(self, button):
        selection = self._view.get_selection()
        selected_rows = selection.get_selected_rows()
        store, paths = selected_rows
        if not paths:
            hildon.hildon_banner_show_information(self, '', _('Please select at least one Label'))
            return

        removed = []
        for path in paths:
            self._manager.remove_label(store[path][LabelsWindow.LABELS_MODEL_ID_COLUMN])
            removed.append(gtk.TreeRowReference(store, path))

        for reference in removed:
            store.remove(store.get_iter(reference.get_path()))

        if len(self._manager.get_label_list()) == 0:
            self._remove_button.hide()

        # restore normal mode
        self._restore_normal_mode(button)

    def _restore_normal_mode(self, button):
        # tree view normal mode
        hildon.hildon_gtk_tree_view_set_ui_mode(self._view, gtk.HILDON_UI_MODE_NORMAL)
        self._view.get_selection().unselect_all()

        self.edit_toolbar.hide()
        self.unfullscreen()

    def _on_label_activated(self, treeview, path, column):
        label_iter = self._view.get_model().get_iter(path)
        label_id = self._view.get_model().get_value(label_iter, LabelsWindow.LABELS_MODEL_ID_COLUMN)

        if not self._feeds_window:
            self._feeds_window = FeedsWindow(self._manager, self._settings, self._conn_manager)
            self._feeds_window.connect('delete-event', lambda w, e: w.hide() or True)
        self._feeds_window.set_filter_label_id(label_id)
        # Do not destroy the Feeds Window keep it cached instead
        self._feeds_window.show()

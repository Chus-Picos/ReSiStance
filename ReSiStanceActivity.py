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

from sugar.activity import activity
from sugar.graphics.toolbarbox import ToolbarBox, ToolbarButton
from sugar.activity.widgets import ActivityToolbarButton, StopButton
from sugar.datastore import datastore
from sugar.graphics.objectchooser import ObjectChooser
from sugar.graphics import iconentry
from sugar.graphics.palette import Palette
from sugar.graphics.toggletoolbutton import ToggleToolButton
from sugar.graphics.combobox import ComboBox
from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.radiotoolbutton import RadioToolButton

from src.ReSiStance import constants
from src.ReSiStance.settings import Settings
from src.ReSiStance.feedmanager import FeedManager
from src.ReSiStance.connectionmanager_gnome import ConnectionManager
from src.ReSiStance.utils import *

import logging
import glib
import time
import calendar
import gobject
from pango import ELLIPSIZE_END
import gettext
import gtk
import locale
import os
import sys
import feedparser
import urllib2
import urllib
from webkit import WebView
import subprocess
from threading import Thread
from gobject import idle_add

_ = gettext.gettext

conn_manager = ConnectionManager()
settings = Settings()
manager = FeedManager(settings, conn_manager)

local_src = os.path.join (os.path.dirname(__file__), 'src')
if os.path.exists(local_src):
    sys.path = [local_src] + sys.path

# Check that user dirs exist
if os.path.exists(constants.RSS_CONF_FOLDER) == False:
    os.makedirs(constants.RSS_CONF_FOLDER, 0700)
    os.mkdir(os.path.join(constants.RSS_CONF_FOLDER, 'icons'), 0700)

if os.path.exists(constants.RSS_DB_DIR) == False:
    os.makedirs(constants.RSS_DB_DIR, 0700)    


# Init i18n stuff
languages = []
lc, encoding = locale.getdefaultlocale()
if lc:
    languages = [lc]
languages += constants.DEFAULT_LANGUAGES
gettext.bindtextdomain(constants.RSS_COMPACT_NAME,
                       constants.LOCALE_DIR)
gettext.textdomain(constants.RSS_COMPACT_NAME)
language = gettext.translation(constants.RSS_COMPACT_NAME,
                               constants.LOCALE_DIR,
                               languages = languages,
                               fallback = True)

google_reader_pixbuf = gtk.gdk.pixbuf_new_from_file(constants.GOOGLE_READER_ICON_FILE)

def on_exit(event):
    # Save the feeds status
    manager.save(None)
    settings.save()

def progress_timeout(pbobj):
    pbobj.progressbar.pulse()
    return True

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

class ReSiStanceActivity(activity.Activity):
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)

        gtk.gdk.threads_init()
    
        self.list_content = []
        self.max_participants = 1

        # Apply settings
        settings.load()
        if settings.show_labels_startup:
            win = LabelsWindow(manager, settings, conn_manager, self)
        else:
            win = FeedsWindow(manager, settings, conn_manager, self)

        self.connect('key-press-event', self._clear_status_bar)
        self.connect('button-press-event', self._clear_status_bar)

    def _clear_status_bar(self, widget, event=None):
        gobject.timeout_add(3000, self._clear_messages, widget)

    def _clear_messages(self, widget):
        actual = self.list_content[(len(self.list_content)-1)]
        if actual:
            for message in range(actual.messages_counter):
                actual.status_bar.pop(actual.context_id)

    def _back_clicked_cb(self, button, window):
        self.canvas_in = self.list_content[(len(self.list_content)-2)] 
        self.set_canvas(self.canvas_in)
        self.set_toolbar_box(self.canvas_in.toolbar_box)
        self.list_content = self.list_content[0:len(self.list_content)-1]

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
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_resizable(True)
        column.set_expand(True)
        self.append_column(column);

        # Unread entries column
        date_renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Unread', date_renderer, markup = FeedsWindow.FEEDS_MODEL_READ_COLUMN)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_resizable(True)
        column.set_fixed_width(200)
        self.append_column(column)

class FeedsWindow(gtk.VBox):

    FEEDS_MODEL_PIXBUF_COLUMN, FEEDS_MODEL_SYNC_ICON_COLUMN, FEEDS_MODEL_TITLE_COLUMN, FEEDS_MODEL_SUBTITLE_COLUMN, \
        FEEDS_MODEL_READ_COLUMN, FEEDS_MODEL_VISITS_COLUMN, FEEDS_MODEL_SYNC_COLUMN, \
        FEEDS_MODEL_ID_COLUMN, FEEDS_MODEL_HREF_COLUMN, FEEDS_MODEL_LABEL_VISIBLE_COLUMN = range(10)

    def __init__(self, manager, settings, conn_manager, activity, title=None):
        super(FeedsWindow, self).__init__()

        self.manager = manager
        self.manager.connect('feed-added', self._on_feed_added_update_label)
        self.settings = settings
        self._conn_manager = conn_manager
        self.activity = activity
        self._filter_label_id = constants.ALL_LABEL_ID

        self._create_menu()

        if title:
            self._hbox = gtk.HBox()
            self._title_label = gtk.Label()
            self._title_label.set_markup('<b><big>'+unescape(title)+'</big></b>')    
            self._title_label.set_alignment(0.5, 0.5)
            self._title_label.show()
            self._hbox.pack_start(self._title_label, True, True)
            self._hbox.show()
            self.pack_start(self._hbox, False, False)

        # Feeds
        self.view = FeedsView()
        store = gtk.ListStore(gtk.gdk.Pixbuf, gtk.gdk.Pixbuf, str, str, str, int, bool, int, str, bool)
        model_filter = store.filter_new()
        model_filter.set_visible_column(self.FEEDS_MODEL_LABEL_VISIBLE_COLUMN)
        self.view.set_model (model_filter)
        self.view.connect ("row-activated", self._on_feed_activated)
        self.view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.view.show()

        self.view.connect('key-press-event', self.activity._clear_status_bar)
        self.view.connect('button-press-event', self.activity._clear_status_bar)

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)

        self.pack_start(scroll, True, True, 0)
        scroll.add(self.view)
        scroll.show()

        self.progressbar = gtk.ProgressBar()
        
        self.progressbar.show()

        self.status_bar = gtk.Statusbar()      
        self.context_id = self.status_bar.get_context_id('Feedsswindow statusbar')
        self.status_bar.pack_start(self.progressbar, False, False)
        self.pack_start(self.status_bar, False, True, 0)
        self.status_bar.show()
        #To count the number of messages
        self.messages_counter = 0

        # Add a timer callback to update the value of the progress bar
        self.timer = gobject.timeout_add (100, progress_timeout, self)

        # Apply settings
        self._sort(self.settings.feeds_order)
        if self.settings.feeds_order == constants.DESCENDING_ORDER:
            self.descending_filter_button.set_sensitive(True)
        elif self.settings.feeds_order == constants.VISITS_ORDER:
            self.visits_filter_button.set_sensitive(True)

        self.activity.set_canvas(self)
        self.activity.list_content.append(self.activity.get_canvas())
        self.show()

        # Load Feeds (could be none)
        try:
            # Quickly show feedback to user
            self.progressbar.pulse()
            self.manager.load_feeds_summary(self._feeds_summary_loaded)
        except IOError:
            gobject.source_remove(self.timer)
            self.timer = 0
            self.progressbar.hide()

    def _set_title(self, title):        
        if self._hbox:
            self._title_label.set_markup('<b><big>'+unescape(title)+'</big></b>')    

    def _create_menu(self):
        self.toolbar_box = ToolbarBox()
        self.toolbar_box.connect('key-press-event', self.activity._clear_status_bar)
        self.toolbar_box.connect('button-press-event', self.activity._clear_status_bar)

        activity_button = ActivityToolbarButton(self.activity)

        self.toolbar_box.toolbar.insert(activity_button, 0)
        activity_button.page.keep.props.accelerator = '<Ctrl><Shift>S'
        activity_button.show()

        self.activity.set_toolbar_box(self.toolbar_box)
        self.toolbar_box.show()

        self.edit_toolbar = self._create_edit_toolbar()
        self.edit_toolbar_button = ToolbarButton(
                page=self.edit_toolbar,
                icon_name='text-x-generic')
        self.edit_toolbar.show()
        self.toolbar_box.toolbar.insert(self.edit_toolbar_button, -1)
        self.edit_toolbar_button.show()

        self.order_toolbar = self._create_order_toolbar()
        self.order_toolbar_button = ToolbarButton(
                page=self.order_toolbar,
                icon_name='view-lastedit')
        self.order_toolbar.show()
        self.toolbar_box.toolbar.insert(self.order_toolbar_button, -1)
        self.order_toolbar_button.show()

        self.find_toolbar = self._create_find_toolbar()
        self.find_toolbar_button = ToolbarButton(
                page=self.find_toolbar,
                icon_name='system-search')
        self.find_toolbar.show()
        self.toolbar_box.toolbar.insert(self.find_toolbar_button, -1)
        self.find_toolbar_button.show()

        self.google_toolbar = self._create_google_toolbar()
        self.google_toolbar_button = ToolbarButton(
                page=self.google_toolbar,
                icon_name='google-reader')
        self.google_toolbar.show()
        self.toolbar_box.toolbar.insert(self.google_toolbar_button, -1)
        self.google_toolbar_button.show()

        self._settings_palette = SettingsPalette(_('Settings'), self.manager, self.settings, self._conn_manager, self)
        self._settings_button = ToggleToolButton('preferences-system')
        self._settings_button.set_palette(self._settings_palette)
        self.toolbar_box.toolbar.insert(self._settings_button, -1)
        self._settings_button.show()

        if self.settings.show_labels_startup:
            self._add_to_label_button = ToolButton('new-label')
            self._add_to_label_button.props.accelerator = '<Ctrl><Shift>L'
            self._add_to_label_button.set_tooltip(_('Add feeds to this label'))
            self._add_to_label_button.connect('clicked', self.activity._clear_messages)
            self._add_to_label_button.connect('clicked', self._add_feed_to_label_cb)
            self.toolbar_box.toolbar.insert(self._add_to_label_button, -1)
            self._add_to_label_button.show()

            self._remove_from_label_button = ToolButton('remove-label')
            self._remove_from_label_button.props.accelerator = '<Ctrl><Shift>P'
            self._remove_from_label_button.set_tooltip(_('Remove feeds from this label'))
            self._remove_from_label_button.connect('clicked', self.activity._clear_messages)
            self._remove_from_label_button.connect('clicked', self._remove_feed_from_label_cb)
            self.toolbar_box.toolbar.insert(self._remove_from_label_button, -1)
            self._remove_from_label_button.show()



            if self._filter_label_id == constants.ALL_LABEL_ID:
                self._add_to_label_button.hide()
                self._remove_from_label_button.hide()

        separator = gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        self.toolbar_box.toolbar.insert(separator, -1)
        separator.show()

        if self.settings.show_labels_startup:        
            self.back_button = ToolButton('back')
            self.back_button.props.accelerator = '<Ctrl><Shift>B'
            self.back_button.set_tooltip(_('Return to the previous window'))
            self.back_button.connect('clicked', self.activity._back_clicked_cb, self)
            self.toolbar_box.toolbar.insert(self.back_button, -1)
            self.back_button.show()

        self.stop_button = StopButton(self.activity)
        self.stop_button.props.accelerator = '<Ctrl><Shift>Q'
        self.toolbar_box.toolbar.insert(self.stop_button, -1)
        self.stop_button.connect('clicked', on_exit)
        self.stop_button.show()

    def _create_edit_toolbar(self):
        edit_toolbar = gtk.Toolbar()

        add_label = gtk.Label(_('New') + ': ')
        add_label.show()
        add_item_label = gtk.ToolItem()
        add_item_label.add(add_label)
        add_item_label.show()
        edit_toolbar.insert(add_item_label, 0)
        self.entry_add = gtk.Entry()
        self.entry_add.show()
        entry_item = gtk.ToolItem()
        entry_item.set_expand(True)
        entry_item.add(self.entry_add)
        entry_item.show()
        edit_toolbar.insert(entry_item, -1)
        edit_toolbar._entry = self.entry_add     

        self.add_button = ToolButton('list-add')
        self.add_button.set_tooltip(_('Add a new feed'))
        self.add_button.props.accelerator = '<Ctrl><Shift>N'
        self.add_button.connect('clicked', self.activity._clear_messages)
        self.add_button.connect('clicked', self._new_feed_response_cb, edit_toolbar)
        self.add_button.set_sensitive(False)
        edit_toolbar.insert(self.add_button, -1)
        self.add_button.show()

        self.entry_add.connect('changed', self._entry_changed_cb, edit_toolbar, self.add_button)

        remove_button = ToolButton('list-remove')
        remove_button.set_tooltip(_('Remove one or more feeds'))
        remove_button.props.accelerator = '<Ctrl><Shift>D'
        remove_button.connect('clicked', self.activity._clear_messages)
        remove_button.connect('clicked', self._remove_button_clicked_cb)
        edit_toolbar.insert(remove_button, -1)
        remove_button.show()

        self._update_all_button = ToolButton('view-refresh')
        self._update_all_button.set_tooltip(_('Update the entries of the feeds'))
        self._update_all_button.props.accelerator = '<Ctrl><Shift>R'
        self._update_all_button.connect('clicked', self.activity._clear_messages)
        self._update_all_button.connect('clicked', self._update_all_cb)
        edit_toolbar.insert(self._update_all_button, -1)
        self._update_all_button.show()

        self.export_opml_button = ToolButton('transfer-to')
        self.export_opml_button.set_tooltip(_('Export the list of feeds in an opml file'))
        self.export_opml_button.props.accelerator = '<Ctrl><Shift>E'
        self.export_opml_button.connect('clicked', self.activity._clear_messages)
        self.export_opml_button.connect('clicked', self._export_feed_cb)
        edit_toolbar.insert(self.export_opml_button, -1)
        self.export_opml_button.show()

        import_button = ToolButton('transfer-from')
        import_button.set_tooltip(_('Import a list of feeds from an opml file'))
        import_button.props.accelerator = '<Ctrl><Shift>I'
        import_button.connect('clicked', self.activity._clear_messages)
        import_button.connect('clicked', self._import_feed_cb)
        edit_toolbar.insert(import_button, -1)
        import_button.show()

        return edit_toolbar

    def _create_order_toolbar(self):
        order_toolbar = gtk.Toolbar()

        self.ascending_filter_button = ToolButton('sort-ascent')
        self.ascending_filter_button.set_tooltip(_('Sort the feeds in ascending order'))
        self.ascending_filter_button.props.accelerator = '<Ctrl><Shift>T'
        self.ascending_filter_button.set_sensitive(True)
        self.ascending_filter_button.connect('clicked', self.activity._clear_messages)
        self.ascending_filter_button.connect('clicked', self._sort_ascending_cb)
        order_toolbar.insert(self.ascending_filter_button, 0)
        self.ascending_filter_button.show()

        self.descending_filter_button = ToolButton('sort-descent')
        self.descending_filter_button.set_tooltip(_('Sort the feeds in descending order'))
        self.descending_filter_button.props.accelerator = '<Ctrl><Shift>B'
        self.descending_filter_button.set_sensitive(True)
        self.descending_filter_button.connect('clicked', self.activity._clear_messages)
        self.descending_filter_button.connect('clicked', self._sort_descending_cb)
        order_toolbar.insert(self.descending_filter_button, -1)
        self.descending_filter_button.show()

        self.visits_filter_button = ToolButton('emblem-favorite')
        self.visits_filter_button.set_tooltip(_('Sort the feeds according to the most read'))
        self.visits_filter_button.props.accelerator = '<Ctrl><Shift>F'
        self.visits_filter_button.set_sensitive(True)
        self.visits_filter_button.connect('clicked', self.activity._clear_messages)
        self.visits_filter_button.connect('clicked', self._sort_visits_cb)
        order_toolbar.insert(self.visits_filter_button, -1)
        self.visits_filter_button.show()

        return order_toolbar

    def _create_find_toolbar(self):
        find_toolbar = gtk.Toolbar()

        search_label = gtk.Label(_("Search") + ": ")
        search_label.show()
        search_item_page_label = gtk.ToolItem()
        search_item_page_label.add(search_label)
        find_toolbar.insert(search_item_page_label, -1)
        search_item_page_label.show()

        # setup the search options
        find_toolbar._entry = iconentry.IconEntry()
        find_toolbar._entry.set_icon_from_name(iconentry.ICON_ENTRY_PRIMARY,
                                              'system-search')
        find_toolbar._entry.add_clear_button()
        entry_item = gtk.ToolItem()
        entry_item.set_expand(True)
        entry_item.add(find_toolbar._entry)
        find_toolbar._entry.show()
        find_toolbar.insert(entry_item, -1)
        entry_item.show()
        
        self.search_button = ToolButton('go-next')
        self.search_button.set_tooltip(_('Find feeds by keywords'))
        self.search_button.props.accelerator = '<Ctrl><Shift>S'
        self.search_button.connect('clicked', self.activity._clear_messages)
        self.search_button.connect('clicked', self._find_feed_cb, find_toolbar)
        self.search_button.set_sensitive(False)
        find_toolbar.insert(self.search_button, -1)
        self.search_button.show()

        find_toolbar._entry.connect('changed', self._entry_changed_cb, find_toolbar, self.search_button)

        return find_toolbar

    def _create_google_toolbar(self):
        google_toolbar = gtk.Toolbar()

        self._sync_feed_button = ToolButton('list-add')
        message = '%s\n%s' % (_('Add feeds to Google Reader.'), _('Use Settings to add your user and password'))
        self._sync_feed_button.set_tooltip(message)
        self._sync_feed_button.props.accelerator = '<Ctrl><Shift>G'
        self._sync_feed_button.connect('clicked', self.activity._clear_messages)
        self._sync_feed_button.connect('clicked', self._subscribe_feed_cb, True)
        google_toolbar.insert(self._sync_feed_button, -1)
        self._sync_feed_button.show()

        self._sync_feed_remove_button = ToolButton('list-remove')
        message = '%s\n%s' % (_('Remove feeds from Google Reader.'), _('Use Settings to add your user and password'))
        self._sync_feed_remove_button.set_tooltip(message)
        self._sync_feed_remove_button.props.accelerator = '<Ctrl><Shift>U'
        self._sync_feed_remove_button.connect('clicked', self.activity._clear_messages)
        self._sync_feed_remove_button.connect('clicked', self._subscribe_feed_cb, False)
        google_toolbar.insert(self._sync_feed_remove_button, -1)
        self._sync_feed_remove_button.show()

        return google_toolbar

    def _entry_changed_cb(self, entry, toolbar, button):
        if toolbar._entry.props.text:
            toolbar._entry.activate()
            # set the button contexts
            button.set_sensitive(True)
            return
        else:
            button.set_sensitive(False)

    def _add_feed_to_label_cb(self, button):
        news_window = FeedsLabelsWindow(self.manager, self.settings, self._conn_manager, True, self, self._filter_label_id, self.activity)
        news_window.show()

    def _remove_feed_from_label_cb(self, button):
        news_window = FeedsLabelsWindow(self.manager, self.settings, self._conn_manager, False, self, self._filter_label_id, self.activity)
        news_window.show()

    def _on_feed_added_update_label(self, manager, feed_id):
        if self._filter_label_id == constants.ALL_LABEL_ID:
            return
        self.manager.add_feeds_to_label([feed_id], self._filter_label_id)

    def _new_feed_response_cb(self, button, toolbar):
        url = toolbar._entry.props.text

        # Quickly show feedback to user
        self.progressbar.pulse()
        self.timer = gobject.timeout_add (100, progress_timeout, self)
        self.progressbar.show()

        # Insert a dummy row while information is retrieved
        feed_iter = self._add_dummy_feed(url)
        path = self.view.get_model().get_path(feed_iter)
        row_reference = gtk.TreeRowReference(self.view.get_model(), path)

        # Add feed to manager
        self.manager.add_feed(url, False, self._feed_added_cb, row_reference)

    def _remove_button_clicked_cb(self, button):
        selection = self.activity.get_canvas().view.get_selection()
        selected_rows = selection.get_selected_rows()
        model, paths = selected_rows

        dialog = gtk.MessageDialog(None,
                               gtk.DIALOG_MODAL,
                               type=gtk.MESSAGE_QUESTION,
                               buttons=gtk.BUTTONS_YES_NO)
        dialog.set_markup("<b>%s</b>" % _('Do you want to delete these feeds?'))
        dialog.connect('response', self._remove_cb, model, paths)
        response = dialog.run()
        dialog.destroy()

    def _remove_cb(self, dialog, response, model_filter, paths):
        if response == gtk.RESPONSE_YES:
            # Quickly show feedback to user
            self.progressbar.pulse()
            self.timer = gobject.timeout_add (100, progress_timeout, self)
            self.progressbar.show()
            
            removed = []
            unsubscribe = []
            if len(paths) == len(self.manager.get_feed_summaries()):
                self.export_opml_button.set_sensitive(False)
            for path in paths:
                try:
                    self.manager.remove_feed(model_filter[path][FeedsWindow.FEEDS_MODEL_ID_COLUMN])
                except IOError:
                    # Quickly show feedback to user
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

            gobject.source_remove(self.timer)
            self.timer = 0
            self.progressbar.hide()
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
            self.activity.get_canvas().manager.save()

    def _remove_from_google_cb(self, dialog, response, feed, unsubscribe):
        if response == gtk.RESPONSE_YES:
            for feed in unsubscribe:
                self.manager.subscribe_feed_google(feed, feed.href, False)

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
        self.progressbar.pulse()
        self.timer = gobject.timeout_add (100, progress_timeout, self)
        self.progressbar.show()

        # Ask manager to update feed
        self._update_multiple_feeds(self._all_feeds_updated_cb)

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

    def _export_feed_cb(self, button):
        # Quickly show feedback to user
        self.progressbar.pulse()
        self.timer = gobject.timeout_add (100, progress_timeout, self)
        self.progressbar.show()

        file_name = 'resistance-feeds.opml'
        # create a datastore object
        dsobject = datastore.create()
        # metadata for the datastore object
        dsobject.metadata['title'] = file_name
        # the picke module serializes objects in simple txt (?!)
        dsobject.metadata['mime_type'] = 'text/x-opml'

        file_path = os.path.join(activity.get_activity_root(), 'instance', file_name)
        self.manager.export_opml(file_path, self._feed_exported_cb, [dsobject, file_path])

    def _import_feed_cb(self, button):

        try:
            chooser = ObjectChooser(self.activity, None)
        except TypeError:
            chooser = ObjectChooser(_('Select file to import'), self.activity,
                gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)
        if chooser is not None:
            try:
                result = chooser.run()
                if result == gtk.RESPONSE_ACCEPT:
                    dsobject = chooser.get_selected_object()

                    # Quickly show feedback to user
                    self.progressbar.pulse()
                    self.timer = gobject.timeout_add (100, progress_timeout, self)
                    self.progressbar.show()
                
                    try:
                        self.manager.import_opml(dsobject.metadata['file_path'], self._import_opml_cb)
                    except:
                        self.manager.import_opml(dsobject.get_file_path(), self._import_opml_cb)

                    dsobject.destroy()
            finally:
                chooser.destroy()
                del chooser

    def _find_feed_cb(self, button, find_toolbar):
        keywords = find_toolbar._entry.props.text
        self._find_feed_response_cb(button, keywords)

    def _sort_ascending_cb(self, button):
        button.set_sensitive(False)
        self.descending_filter_button.set_sensitive(True)
        self.visits_filter_button.set_sensitive(True)
        self.settings.feeds_order = constants.ASCENDING_ORDER
        self._sort(constants.ASCENDING_ORDER)

    def _sort_descending_cb(self, button):
        button.set_sensitive(False)
        self.ascending_filter_button.set_sensitive(True)
        self.visits_filter_button.set_sensitive(True)
        self.settings.feeds_order = constants.DESCENDING_ORDER
        self._sort(constants.DESCENDING_ORDER)

    def _sort_visits_cb(self, button):
        button.set_sensitive(False)
        self.ascending_filter_button.set_sensitive(True)
        self.descending_filter_button.set_sensitive(True)
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

    def _feeds_summary_loaded(self, feeds_summary, user_data, error):
        if user_data:
            # Quickly show feedback to user
            self.status_bar.push(self.context_id, _('Loaded'))
            self.messages_counter += 1

        # Iterate over summaries and fill the model
        gobject.source_remove(self.timer)
        self.timer = 0
        self.progressbar.hide()
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

    def _feed_data_loaded_cb(self, feed_data, row_reference, error):
        if not feed_data:
            # Quickly show feedback to user
            self.status_bar.push(self.context_id, _('Error loading feed data'))
            self.messages_counter += 1
            return

        self._show_entries_window(row_reference.get_path())

    def _get_favicon_cb(self, pixbuf, row_reference, error):
        if pixbuf == None:
            return

        store = self.view.get_model().get_model()
        feed_iter = store.get_iter(row_reference.get_path())
        store.set(feed_iter, self.FEEDS_MODEL_PIXBUF_COLUMN, pixbuf)

    def _on_feed_activated(self, treeview, path, column):
        feed_iter = self.view.get_model().get_iter(path)
        feed_id = self.view.get_model().get_value(feed_iter, self.FEEDS_MODEL_ID_COLUMN)

        # Check that we're not trying to open a dummy feed
        if feed_id == self.view.DUMMY_FEED_STATUS:
            # Quickly show feedback to user
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

        news_window = EntriesWindow(feed_data, self.manager, self.settings, self._conn_manager, self, path, self.activity)
        news_window.show()

        # Update the visits count
        summary.visits += 1
        store_feed_iter = model_filter.convert_iter_to_child_iter(feed_iter)
        model_filter.get_model().set_value(store_feed_iter, self.FEEDS_MODEL_VISITS_COLUMN, summary.visits)

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


    def _update_labels_menu(self):
        if self._filter_label_id != constants.ALL_LABEL_ID:
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


    def _feed_added_cb(self, pixbuf_and_data, row_reference=None, error=None, stop_progress=True):

        # Remove progress information
        if stop_progress:
            gobject.source_remove(self.timer)
            self.timer = 0
            self.progressbar.hide() 

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
            # Quickly show feedback to user
            self.status_bar.push(self.context_id, message)
            self.messages_counter += 1
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

    def _all_feeds_updated_cb(self,  data):
        # Remove progress information
        gobject.source_remove(self.timer)
        self.timer = 0
        self.progressbar.hide() 

        # Do not update read/unread status if all the feeds failed to sync
        synced_feeds = [row[self.FEEDS_MODEL_ID_COLUMN] for row in self.view.get_model() \
                            if row[self.FEEDS_MODEL_SYNC_COLUMN]]
        if len(synced_feeds) == 0:
            return

        # Update read/unread status
        # Quickly show feedback to user
        self.progressbar.pulse()
        self.timer = gobject.timeout_add (100, progress_timeout, self)
        self.progressbar.show()
        self.manager.sync_google_reader_read_status(self._sync_google_reader_read_status_cb)

    def _feed_exported_cb(self, retval, user_data, error):
        if not error:
            dsobject = user_data[0]
            file_path = user_data[1]
            dsobject.set_file_path(file_path)
            dsobject.metadata['file_path'] = file_path

            datastore.write(dsobject)
            dsobject.destroy()
            message = _('Feeds exported')
        else:
            message = _('Error exporting feeds')

        # Remove progress information
        gobject.source_remove(self.timer)
        self.timer = 0
        self.progressbar.hide() 
        # Quickly show feedback to user
        self.status_bar.push(self.context_id, message)
        self.messages_counter += 1

    def _import_opml_cb(self, feed_url_list, data, error):
        # Remove progress information
        gobject.source_remove(self.timer)
        self.timer = 0
        self.progressbar.hide() 
        if error:
            # Quickly show feedback to user
            self.status_bar.push(self.context_id, _('Error importing feeds OPML file'))
            self.messages_counter += 1
            return

        if len(feed_url_list) == 0:
            # Quickly show feedback to user
            self.status_bar.push(self.context_id, _('No feeds to import in OPML file'))
            self.messages_counter += 1
            return

        self._add_multiple_feeds(feed_url_list, callback=self._save_feeds_after_multiple_add)

    def _multiple_add_cb(self, pixbuf_and_data, user_data, error, static = {"count" : 0}):
        ''' Simulating a static variable with a default argument hack '''
        num_operations, callback, data, row_reference = user_data

        self._feed_added_cb(pixbuf_and_data, row_reference, error, stop_progress=False)
        static['count'] += 1
        # If all add operations have finished then call the all-done-callback
        if static['count'] == num_operations:
            # Remove progress information
            gobject.source_remove(self.timer)
            self.timer = 0
            self.progressbar.hide() 

            static['count'] = 0
            if callback:
                callback(data)
        else:
            pass

    def _add_multiple_feeds(self, urls, sync=False, callback=None, data=None):
        for url in urls:
            # Insert a dummy row while information is retrieved
            feed_iter = self._add_dummy_feed(url, sync)
            path = self.view.get_model().get_path(feed_iter)
            row_reference = gtk.TreeRowReference(self.view.get_model(), path)

            # Add feed to manager
            self.manager.add_feed(url, sync, self._multiple_add_cb,
                                  (len(urls), callback, data, row_reference))

    def _save_feeds_after_multiple_add(self, data=None):
        self.manager.save()

    def _find_feed_response_cb(self, button, keywords):
        # Quickly show feedback to user
        self.progressbar.pulse()
        self.timer = gobject.timeout_add (100, progress_timeout, self)
        self.progressbar.show()

        self.manager.find_feed(keywords, self._found_cb, None)
        button.set_sensitive(False)

    def _find_window_urls_found_cb(self, find_window, urls):
        # Quickly show feedback to user
        self.progressbar.pulse()
        self.timer = gobject.timeout_add (100, progress_timeout, self)
        self.progressbar.show()
        if len(urls):
            self._add_multiple_feeds(urls, callback=self._save_feeds_after_multiple_add)

    def _found_cb(self, feeds_info, dialog, error):
        self.search_button.set_sensitive(True)
        # Remove progress information
        gobject.source_remove(self.timer)
        self.timer = 0
        self.progressbar.hide() 
        if feeds_info == None:
            # Something went wrong
            self.status_bar.push(self.context_id, _('Error finding feeds. Server error.'))
            self.messages_counter += 1
            return

        #Hide the page of the toolbarbutton
        self.find_toolbar_button.set_expanded(False)
        news_window = FindWindow(self.manager, self.settings, self._conn_manager, feeds_info, self.activity)
        news_window.show()

        news_window.connect('urls-found', self._find_window_urls_found_cb)

    def _subscribe_feed_cb(self, button, subscribe):
        selection = self.view.get_selection()
        selected_rows = selection.get_selected_rows()
        model_filter, paths = selected_rows
        if not paths:
            # Quickly show feedback to user
            self.status_bar.push(self.context_id, _('Please select at least one Feed'))
            self.messages_counter += 1
            return

        self.update_cont = 1
        total = len(paths)

        # Quickly show feedback to user
        self.progressbar.pulse()
        self.timer = gobject.timeout_add (100, progress_timeout, self)
        self.progressbar.show()

        for path in paths:
            try:
                # Disable buttons while subscription takes place
                self._update_all_button.set_sensitive(False)
                self._sync_feed_button.set_sensitive(False)
                self._sync_feed_remove_button.set_sensitive(False)

                summary = self.manager.get_feed_summary(model_filter[path][FeedsWindow.FEEDS_MODEL_ID_COLUMN])
                self.manager.subscribe_feed_google(summary.href, subscribe, self._feed_subscribed_cb, [summary, subscribe, total, path])
            except IOError:
                # Quickly show feedback to user
                self.status_bar.push(self.context_id, _('File error while subscribing Feed'))
                self.messages_counter += 1

    def _feed_subscribed_cb(self, synced, user_data, error):
        feed_data = user_data[0]
        subscribe = user_data[1]
        total = user_data[2]
        path = user_data[3]
        if self.update_cont == total:
            # Remove progress information
            gobject.source_remove(self.timer)
            self.timer = 0
            self.progressbar.hide()  

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

        # Restore sensitiviness
        self._sync_feed_button.set_sensitive(True)
        self._update_all_button.set_sensitive(True)
        self._sync_feed_remove_button.set_sensitive(True)

    def _sync_google_reader_read_status_cb(self, synced, user_data, error):
        # Remove progress information
        gobject.source_remove(self.timer)
        self.timer = 0
        self.progressbar.hide() 
        if not synced:
            # Quickly show feedback to user
            self.status_bar.push(self.context_id, _('Error syncing read status with Google Reader'))
            self.messages_counter += 1
            return

        # TODO: Update counters
        store = self.view.get_model().get_model()
        for row in store:
            if row[self.FEEDS_MODEL_SYNC_COLUMN]:
                feed_data = self.manager.get_feed_data(row[self.FEEDS_MODEL_ID_COLUMN])
                unread_count = len([entry for entry in feed_data.entries if entry.read == False])
                row[self.FEEDS_MODEL_READ_COLUMN] = get_visual_unread_text(unread_count)

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
        # Remove progress information
        gobject.source_remove(self.timer)
        self.timer = 0
        self.progressbar.hide() 
        if retval == None:
            # Quickly show feedback to user
            self.status_bar.push(self.context_id, _('Authentication error'))
            self.messages_counter += 1
            return

        urls, label_feeds = retval

        if urls == None:
            # Quickly show feedback to user
            self.status_bar.push(self.context_id, _('Error synchronizing feeds'))
            self.messages_counter += 1
            return
        elif urls == []:
            # Quickly show feedback to user
            self.status_bar.push(self.context_id, _('No feeds in Google Reader to synchronize'))
            self.messages_counter += 1
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

class SettingsPalette(Palette):
    def __init__(self, label, manager, settings, conn_manager, feeds_window):
        Palette.__init__(self, label)

        self.manager = manager
        self.settings = settings
        self._conn_manager = conn_manager
        self.feeds_window = feeds_window

        self.mainBox = gtk.VBox()

        self.font_size_box = gtk.HBox()
        self.font_size_label = gtk.Label(_('Default font size'))
        self.font_size_combobox = ComboBox()
        for i in constants.font_size_range:
            self.font_size_combobox.append_item(i, str(i))
        self.font_size_combobox.set_active(0)
        self.font_size_combobox.connect('changed', self.handle_font_size_box)
        self.font_size_box.pack_start(self.font_size_label, False, False, padding = 5)
        self.font_size_box.pack_end(self.font_size_combobox, False, False, padding = 55)
        self.mainBox.pack_start(self.font_size_box, padding = 3)

        self.auto_load_images_box = gtk.HBox()
        self.auto_load_images = gtk.CheckButton(_('Auto load images'))
        self.auto_load_images.set_active(self.settings.auto_load_images)
        self.auto_load_images.connect('toggled', self.handle_auto_load_images)
        self.auto_load_images_box.pack_start(self.auto_load_images, False, False, padding = 5)
        self.mainBox.pack_start(self.auto_load_images_box, padding = 3)

        self.show_labels_startup_box = gtk.HBox()
        self.show_labels_startup = gtk.CheckButton(_('Show labels at start-up'))
        self.show_labels_startup.set_active(self.settings.show_labels_startup)
        self.show_labels_startup.connect('toggled', self.handle_show_labels_startup)
        self.show_labels_startup_box.pack_start(self.show_labels_startup, False, False, padding = 5)
        self.mainBox.pack_start(self.show_labels_startup_box, padding = 3)

        page_separator = gtk.HSeparator()
        page_separator.set_size_request(20, -1)
        self.mainBox.pack_start(page_separator, padding = 10)

        self.automatic_download_box = gtk.HBox()
        self.automatic_download = gtk.CheckButton(_('Automatically download Podcasts'))
        self.automatic_download.set_active(self.settings.auto_download)
        self.automatic_download.connect('toggled', self.handle_automatic_download)
        self.automatic_download_box.pack_start(self.automatic_download, False, False, padding = 5)
        self.mainBox.pack_start(self.automatic_download_box, padding = 3)

        page_separator = gtk.HSeparator()
        page_separator.set_size_request(20, -1)
        self.mainBox.pack_start(page_separator, padding = 10)

        self.synchronize_feeds_box = gtk.HBox()
        self.synchronize_feeds = gtk.CheckButton(_('Synchronize with Google Reader'))
        self.synchronize_feeds.set_active(self.settings.sync_global)
        self.synchronize_feeds.connect('toggled', self.handle_synchronize_feeds)
        self.synchronize_feeds_box.pack_start(self.synchronize_feeds, False, False, padding = 5)
        self.mainBox.pack_start(self.synchronize_feeds_box, padding = 3)

        self.user_box = gtk.HBox()
        user_label = gtk.Label(_('User') + ': ')
        user_label.show()
        self.user_box.pack_start(user_label, False, False, padding = 5)
        self.entry_user = gtk.Entry()
        self.entry_user.set_sensitive(self.settings.sync_global)
        self.entry_user.set_text(self.settings.user)
        self.user_box.pack_end(self.entry_user, False, False, padding = 55)
        self.mainBox.pack_start(self.user_box, padding = 3)

        self.password_box = gtk.HBox()
        password_label = gtk.Label(_('Password') + ': ')
        password_label.show()
        self.password_box.pack_start(password_label, False, False, padding = 5)
        self.entry_password = gtk.Entry()
        self.entry_password.set_visibility(False)
        self.entry_password.set_sensitive(self.settings.sync_global)
        self.entry_password.set_text(self.settings.password)
        self.password_box.pack_end(self.entry_password, False, False, padding = 55)
        self.mainBox.pack_start(self.password_box, padding = 3)

        self.save_user_password_box = gtk.HBox()
        save_user_password_label = gtk.Label(_('Save user and password for Google:'))
        save_user_password_label.show()
        self.save_user_password_button = ToolButton('document-save')
        self.save_user_password_button.connect('clicked', self.handle_save_user_password)
        self.save_user_password_button.show()
        self.save_user_password_button.set_sensitive(self.settings.sync_global)
        self.save_user_password_box.pack_start(save_user_password_label, False, False, padding = 5)
        self.save_user_password_box.pack_start(self.save_user_password_button, False, False, padding = 5)
        self.mainBox.pack_start(self.save_user_password_box, padding = 3)

        self.force_sync_box = gtk.HBox()
        force_sync_label = gtk.Label(_('Synchronize now'))
        force_sync_label.show()
        self.force_sync_button = ToolButton('view-refresh')
        self.force_sync_button.connect('clicked', self._settings_sync_google_reader_cb)
        self.force_sync_button.show()
        self.force_sync_button.set_sensitive(self.settings.sync_global)
        self.force_sync_box.pack_start(force_sync_label, False, False, padding = 5)
        self.force_sync_box.pack_start(self.force_sync_button, False, False, padding = 5)
        self.mainBox.pack_start(self.force_sync_box, padding = 3)

        self.mainBox.show_all()

        self.set_content(self.mainBox)

    def handle_font_size_box(self, widget):
        self.settings.default_font_size = int(widget.props.value)

    def handle_auto_load_images(self, widget):
        self.settings.auto_load_images = self.auto_load_images.get_active()

    def handle_show_labels_startup(self, widget):
        self.settings.show_labels_startup = self.show_labels_startup.get_active()

    def handle_automatic_download(self, widget):
        self.settings.auto_download = self.automatic_download.get_active()

    def handle_synchronize_feeds(self, widget):
        self.entry_user.set_sensitive(self.synchronize_feeds.get_active())
        self.entry_password.set_sensitive(self.synchronize_feeds.get_active())
        self.save_user_password_button.set_sensitive(self.synchronize_feeds.get_active())
        self.force_sync_button.set_sensitive(self.synchronize_feeds.get_active())
        self.settings.sync_global = self.synchronize_feeds.get_active()

    def handle_save_user_password(self, widget):
        self.settings.user = self.entry_user.get_text()
        self.settings.password = self.entry_password.get_text()

    def _settings_sync_google_reader_cb(self, button):
        # Quickly show feedback to user
        self.feeds_window.progressbar.pulse()
        self.feeds_window.timer = gobject.timeout_add (100, progress_timeout, self.feeds_window)
        self.feeds_window.progressbar.show()
        self.handle_save_user_password(None)
        self.manager.sync_with_google_reader(self.feeds_window._feeds_synchronized)

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

class FindWindow(gtk.VBox):
    __gsignals__ = {
        "urls-found": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT, )),
        }

    FIND_MODEL_SITE_COLUMN = 0
    FIND_MODEL_URL_COLUMN = 1

    def __init__(self, manager, settings, conn_manager, feedsinfo, activity):
        super(FindWindow, self).__init__()

        self.manager = manager
        self.settings = settings
        self._conn_manager = conn_manager
        self.activity = activity
        
        self._create_menu()

        self.feeds_info = feedsinfo

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

        self.view.connect('key-press-event', self.activity._clear_status_bar)
        self.view.connect('button-press-event', self.activity._clear_status_bar)

        self.progressbar = gtk.ProgressBar()

        self.status_bar = gtk.Statusbar()      
        self.context_id = self.status_bar.get_context_id('Findwindow statusbar')
        self.status_bar.pack_start(self.progressbar, False, False)
        self.pack_start(self.status_bar, False, True, 0)
        self.status_bar.show()
        #To count the number of messages
        self.messages_counter = 0

        self.activity.set_canvas(self)
        self.activity.list_content.append(self.activity.get_canvas())
        self.show()

    def _create_menu(self):
        self.toolbar_box = ToolbarBox()
        self.toolbar_box.connect('key-press-event', self.activity._clear_status_bar)
        self.toolbar_box.connect('button-press-event', self.activity._clear_status_bar)

        activity_button = ActivityToolbarButton(self.activity)

        self.toolbar_box.toolbar.insert(activity_button, 0)
        activity_button.page.keep.props.accelerator = '<Ctrl><Shift>S'
        activity_button.show()

        self.activity.set_toolbar_box(self.toolbar_box)
        self.toolbar_box.show()

        self.add_button = ToolButton('list-add')
        self.add_button.props.accelerator = '<Ctrl><Shift>A'
        self.add_button.set_tooltip(_('Add the selected feeds'))
        self.add_button.connect('clicked', self.activity._clear_messages)
        self.add_button.connect('clicked', self._add_button_clicked_cb)
        self.toolbar_box.toolbar.insert(self.add_button, -1)
        self.add_button.show()

        separator = gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        self.toolbar_box.toolbar.insert(separator, -1)
        separator.show()

        self.back_button = ToolButton('back')
        self.back_button.props.accelerator = '<Ctrl><Shift>B'
        self.back_button.set_tooltip(_('Return to the previous window'))
        self.back_button.connect('clicked', self.activity._back_clicked_cb, self)
        self.toolbar_box.toolbar.insert(self.back_button, -1)
        self.back_button.show()

        self.stop_button = StopButton(self.activity)
        self.stop_button.props.accelerator = '<Ctrl><Shift>Q'
        self.toolbar_box.toolbar.insert(self.stop_button, -1)
        self.stop_button.connect('clicked', on_exit)   
        self.stop_button.show()   

    def _add_button_clicked_cb(self, button):
        selection = self.view.get_selection()
        selected_rows = selection.get_selected_rows()
        model, paths = selected_rows
        if not paths:
            # Quickly show feedback to user
            self.status_bar.push(self.context_id, _('Please select at least one Feed'))
            self.messages_counter += 1
            return

        self.activity._back_clicked_cb(button, self)
        urls = [model[path][self.FIND_MODEL_URL_COLUMN] for path in paths]

        self.emit('urls-found', urls)

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
            + gobject.markup_escape_text(author) \
            + '</span>\n<span size="medium" ' + color + '>' \
            + gobject.markup_escape_text(title) + '</span>'

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

class EntriesWindow(gtk.VBox):

    ENTRIES_MODEL_TEXT_COLUMN = 1
    ENTRIES_MODEL_DATA_COLUMN = 2
    ENTRIES_MODEL_DATE_COLUMN = 3
    ENTRIES_MODEL_DATE_PARSED_COLUMN = 4

    def __init__(self, feed_data, manager, settings, conn_manager, feeds_window, path, activity):
        super(EntriesWindow, self).__init__()

        self.manager = manager
        self.settings = settings
        self.feed_data = feed_data
        self._conn_manager = conn_manager
        self.path = path
        self.activity = activity

        itunes = 'itunes' in self.feed_data.namespaces
        self.itunes = itunes   

        self._create_menu()

        self.feed_data = feed_data
        self.feeds_window = feeds_window
        self.hbox = gtk.HBox()
        
        self.title_label = gtk.Label()
        self.title_label.set_markup('<big>'+unescape(self.feed_data.feed.title)+'</big>')
        self.title_label.set_alignment(0.5, 0.5)
        self.title_label.show()
        self.hbox.pack_start(self.title_label, True, True)          
        self.hbox.show()
        self.pack_start(self.hbox, False, False)     

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

        self.view.connect('key-press-event', self.activity._clear_status_bar)
        self.view.connect('button-press-event', self.activity._clear_status_bar)

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

        self.progressbar = gtk.ProgressBar()

        self.status_bar = gtk.Statusbar()      
        self.context_id = self.status_bar.get_context_id('Entriesswindow statusbar')
        self.status_bar.pack_start(self.progressbar, False, False)
        self.pack_start(self.status_bar, False, True, 0)
        self.status_bar.show()
        #To count the number of messages
        self.messages_counter = 0

        self.activity.set_canvas(self)
        self.activity.list_content.append(self.activity.get_canvas())
        self.show()

    def _create_menu(self):
        self.toolbar_box = ToolbarBox()
        self.toolbar_box.connect('key-press-event', self.activity._clear_status_bar)
        self.toolbar_box.connect('button-press-event', self.activity._clear_status_bar)

        activity_button = ActivityToolbarButton(self.activity)

        self.toolbar_box.toolbar.insert(activity_button, 0)
        activity_button.page.keep.props.accelerator = '<Ctrl><Shift>S'
        activity_button.show()

        self.activity.set_toolbar_box(self.toolbar_box)
        self.toolbar_box.show()

        self._update_feed_button = ToolButton('view-refresh')
        self._update_feed_button.props.accelerator = '<Ctrl><Shift>R'
        self._update_feed_button.set_tooltip(_('Update this feed'))
        self._update_feed_button.connect('clicked', self.activity._clear_messages)
        self._update_feed_button.connect('clicked', self._update_feed_cb)
        self.toolbar_box.toolbar.insert(self._update_feed_button, -1)
        self._update_feed_button.show()

        self._all_filter_button = ToolButton('show-all')
        self._all_filter_button.set_sensitive(self.settings.entries_filter != constants.SHOW_ALL_FILTER)
        self._all_filter_button.props.accelerator = '<Ctrl><Shift>A'
        self._all_filter_button.set_tooltip(_('Show all entries'))
        self._all_filter_button.connect('clicked', self.activity._clear_messages)
        self._all_filter_button.connect('clicked', self._show_all_cb)
        self.toolbar_box.toolbar.insert(self._all_filter_button, -1)
        self._all_filter_button.show()

        self._unread_filter_button = ToolButton('show-unread')
        self._unread_filter_button.set_sensitive(self.settings.entries_filter != constants.SHOW_UNREAD_FILTER)
        self._unread_filter_button.props.accelerator = '<Ctrl><Shift>U'
        self._unread_filter_button.set_tooltip(_('Show only unread entries'))
        self._unread_filter_button.connect('clicked', self.activity._clear_messages)
        self._unread_filter_button.connect('clicked', self._show_unread_cb)
        self.toolbar_box.toolbar.insert(self._unread_filter_button, -1)
        self._unread_filter_button.show()

        self._mark_read_button = ToolButton('dialog-ok')
        self._mark_read_button.props.accelerator = '<Ctrl><Shift>M'
        self._mark_read_button.set_tooltip(_('Mark read'))
        self._mark_read_button.connect('clicked', self.activity._clear_messages)
        self._mark_read_button.connect('clicked', self._mark_read_button_clicked_cb, True)
        self.toolbar_box.toolbar.insert(self._mark_read_button, -1)
        self._mark_read_button.show()

        self._mark_unread_button = ToolButton('dialog-cancel')
        self._mark_unread_button.props.accelerator = '<Ctrl><Shift>N'
        self._mark_unread_button.set_tooltip(_('Mark unread'))
        self._mark_unread_button.connect('clicked', self.activity._clear_messages)
        self._mark_unread_button.connect('clicked', self._mark_read_button_clicked_cb, False)
        self.toolbar_box.toolbar.insert(self._mark_unread_button, -1)
        self._mark_unread_button.show()

        if self.itunes:
            self._download_all_button = ToolButton('transfer-from-text-uri-list')
            self._download_all_button.props.accelerator = '<Ctrl><Shift>D'
            self._download_all_button.set_tooltip(_('Download all'))
            self._download_all_button.connect('clicked', self.activity._clear_messages)
            self._download_all_button.connect('clicked', self._download_all_items_cb)
            self.toolbar_box.toolbar.insert(self._download_all_button, -1)
            self._download_all_button.show()

        separator = gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        self.toolbar_box.toolbar.insert(separator, -1)
        separator.show()

        self.back_button = ToolButton('back')
        self.back_button.props.accelerator = '<Ctrl><Shift>B'
        self.back_button.set_tooltip(_('Return to the previous window'))
        self.back_button.connect('clicked', self.activity._back_clicked_cb, self)
        self.toolbar_box.toolbar.insert(self.back_button, -1)
        self.back_button.show()

        self.stop_button = StopButton(self.activity)
        self.stop_button.props.accelerator = '<Ctrl><Shift>Q'
        self.toolbar_box.toolbar.insert(self.stop_button, -1)
        self.stop_button.connect('clicked', on_exit)
        self.stop_button.show()

    def _on_entry_activated(self, treeview, path, column, itunes):
        item_window = ItemWindow(self.feed_data, self.manager, self.settings, self._conn_manager, treeview.get_model(), path, itunes, self.activity)

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
            # Quickly show feedback to user
            self.status_bar.push(self.context_id, _('Error syncing read status with Google Reader'))
            self.messages_counter += 1

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

    def _update_feed_cb(self, button):
        # Quickly show feedback to user
        self.progressbar.pulse()
        self.timer = gobject.timeout_add (100, progress_timeout, self)
        self.progressbar.show()
        button.set_sensitive(False)

        # Ask manager to update feed
        self.manager.update_feed(get_feed_id(self.feed_data), self._feed_updated_cb, None)

    def _feed_updated_cb(self, retval, data, error):
        # Update read/unread status if the feed was subscribed
        summary = self.manager.get_feed_summary(get_feed_id(self.feed_data))
        if summary.sync:
            self.manager.sync_google_reader_read_status(self._sync_google_reader_read_status_cb)
        else:
            # Remove progress information
            gobject.source_remove(self.timer)
            self.timer = 0
            self.progressbar.hide() 
            self._update_feed_button.set_sensitive(True)

        self._update_feed_button.set_sensitive(True)

        self.view.get_model().get_model().clear()
        self._add_entries()

    def _sync_google_reader_read_status_cb(self, synced, user_data, error):
        # Remove progress information
        gobject.source_remove(self.timer)
        self.timer = 0
        self.progressbar.hide() 
        self._update_feed_button.set_sensitive(True)

        if not synced:
            # Quickly show feedback to user
            self.status_bar.push(self.context_id, _('Error syncing read status with Google Reader'))
            self.messages_counter += 1
            return

        #Update UI
        model_filter = self.view.get_model()
        store = model_filter.get_model()
        for row in store:
            entry = row[self.ENTRIES_MODEL_DATA_COLUMN]
            row[self.ENTRIES_MODEL_TEXT_COLUMN] = self.view.get_visual_entry_text(entry)

    def _show_all_cb(self, button, button_type='radiobutton'):
        self.settings.entries_filter = constants.SHOW_ALL_FILTER
        self.view.get_model().refilter()
        self.scroll.set_placement(gtk.CORNER_TOP_LEFT)
        self._all_filter_button.set_sensitive(False)
        self._unread_filter_button.set_sensitive(True)

    def _show_unread_cb(self, button, button_type='radiobutton'):  
        self.settings.entries_filter = constants.SHOW_UNREAD_FILTER
        self.view.get_model().refilter()
        self._all_filter_button.set_sensitive(True)
        self._unread_filter_button.set_sensitive(False)

    def _mark_read_button_clicked_cb(self, button, read):
        selection = self.view.get_selection()
        selected_rows = selection.get_selected_rows()
        model, paths = selected_rows
        if not paths:
            # Quickly show feedback to user
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
            # Quickly show feedback to user
            self.status_bar.push(self.context_id, _('Error syncing read status with Google Reader'))
            self.messages_counter += 1

    def _download_all_items_cb(self, button):
        folder = os.path.join(activity.get_activity_root(), 'instance')

        urls = []
        paths_files = []
        dsobjects = []
        for entry in self.feed_data.entries:
            try:
                url = entry['enclosures'][0]['href']
                urls.append(url)
                paths_files.append(folder + os.path.basename(urllib.url2pathname(url)))
                dsobject = datastore.create()
                dsobject.metadata['title'] = os.path.basename(urllib.url2pathname(url))
                dsobject.metadata['mime_type'] = 'audio/mpeg'
                dsobjects.append(dsobject)
            except:
                pass

        # Quickly show feedback to user
        self.progressbar.pulse()
        self.timer = gobject.timeout_add (100, progress_timeout, self)
        self.progressbar.show()

        self.manager.download_all_items(urls, paths_files, self._all_items_downloaded_cb, [dsobjects, paths_files])

    def _all_items_downloaded_cb(self, downloaded, user_data, error):
        if downloaded:
            dsobjects = user_data[0]
            paths_files = user_data[1]
            for n in range(len(dsobjects)):
                dsobject = dsobjects[n]
                file_path = paths_files[n]
                dsobject.set_file_path(file_path)
                dsobject.metadata['file_path'] = file_path
                datastore.write(dsobject)
                dsobject.destroy()
            message = _('Items downloaded')
        else:
            message = _('Error downloading items')
        # Quickly show feedback to user
        self.status_bar.push(self.context_id, message)
        self.messages_counter += 1
        gobject.source_remove(self.timer)
        self.timer = 0
        self.progressbar.hide()

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

        self.pack_start(header_vbox, True, True)

    def _link_button_clicked(self, link_button):
        print 'Open ' + link_button.get_uri()

    def set_item(self, item):

        self.item = item

        self.title.set_markup('<span size="large">  ' + unescape(item.title) + '</span>')

class ItemWindow(gtk.VBox):
    __gsignals__ = {
        "item-read": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT, )),
        }

    def __init__(self, feed_data, manager, settings, conn_manager, model, path, itunes, activity):
        super(ItemWindow, self).__init__()

        self.feed_data = feed_data
        self.manager = manager
        self.settings = settings
        self._conn_manager = conn_manager
        self.activity = activity
        self.itunes = itunes

        self._create_menu()

        # Header
        self.item_window_header = ItemWindowHeader(False, 16, itunes)

        self.pack_start(self.item_window_header, False, False)

        # HTML renderer
        self.view = WebView()
        self.view.set_full_content_zoom(True)

        # Disable text selection
        self.view.connect("motion-notify-event", lambda w, ev: True)

        self.view.connect('key-press-event', self.activity._clear_status_bar)
        self.view.connect('button-press-event', self.activity._clear_status_bar)

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

        self.progressbar = gtk.ProgressBar()

        self.status_bar = gtk.Statusbar()      
        self.context_id = self.status_bar.get_context_id('Itemsswindow statusbar')
        self.status_bar.pack_start(self.progressbar, False, False)
        self.pack_start(self.status_bar, False, True, 0)
        self.status_bar.show()
        #To count the number of messages
        self.messages_counter = 0

        self.activity.set_canvas(self)
        self.activity.list_content.append(self.activity.get_canvas())
        self.show()

    def _create_menu(self):
        self.toolbar_box = ToolbarBox()
        self.toolbar_box.connect('key-press-event', self.activity._clear_status_bar)
        self.toolbar_box.connect('button-press-event', self.activity._clear_status_bar)

        activity_button = ActivityToolbarButton(self.activity)

        self.toolbar_box.toolbar.insert(activity_button, 0)
        activity_button.page.keep.props.accelerator = '<Ctrl><Shift>S'
        activity_button.show()

        self.activity.set_toolbar_box(self.toolbar_box)
        self.toolbar_box.show()

        self.button_up = ToolButton('go-up')
        self.button_up.props.accelerator = '<Ctrl><Shift>W'
        self.button_up.set_tooltip(_('Read the previous item'))
        self.button_up.connect('clicked', self.activity._clear_messages)
        self.button_up.connect('clicked', self._up_button_clicked)
        self.toolbar_box.toolbar.insert(self.button_up, -1)
        self.button_up.show()

        self.button_down = ToolButton('go-down')
        self.button_down.props.accelerator = '<Ctrl><Shift>S'
        self.button_down.set_tooltip(_('Read the next item'))
        self.button_down.connect('clicked', self.activity._clear_messages)
        self.button_down.connect('clicked', self._down_button_clicked)
        self.toolbar_box.toolbar.insert(self.button_down, -1)
        self.button_down.show()

        if self.itunes:
            self._download_button = ToolButton('transfer-from-text-uri-list')
            self._download_button.props.accelerator = '<Ctrl><Shift>D'
            self._download_button.set_tooltip(_('Download the item'))
            self._download_button.connect('clicked', self.activity._clear_messages)
            self._download_button.connect('clicked', self._download_item_cb)
            self.toolbar_box.toolbar.insert(self._download_button, -1)
            self._download_button.show()

        separator = gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        self.toolbar_box.toolbar.insert(separator, -1)
        separator.show()

        self.back_button = ToolButton('back')
        self.back_button.props.accelerator = '<Ctrl><Shift>B'
        self.back_button.set_tooltip(_('Return to the previous window'))
        self.back_button.connect('clicked', self.activity._back_clicked_cb, self)
        self.toolbar_box.toolbar.insert(self.back_button, -1)
        self.back_button.show()

        self.stop_button = StopButton(self.activity)
        self.stop_button.props.accelerator = '<Ctrl><Shift>Q'
        self.toolbar_box.toolbar.insert(self.stop_button, -1)
        self.stop_button.connect('clicked', on_exit)
        self.stop_button.show()

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

        self.item = item

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
            self.button_up.set_sensitive(False)
        elif position == len(self.model) - 1:
            self.button_down.set_sensitive(False)
            toolbar_button_list[1].set_sensitive(False)
        else:
            self.button_up.set_sensitive(True)
            self.button_down.set_sensitive(True)

        # Mark item as read
        item['read'] = True

        # Emit item read
        self.emit('item-read', self.model.get_path(self.model_iter))

    def on_click_uri(self, view, frame, request, action, policy):
        uri = request.get_uri()
        self._open_url(uri)

    def _download_item_cb(self, button):
        item = self.item
        url_file = item.enclosures[0]['href']
        file = os.path.basename(urllib.url2pathname(url_file))

        file_name = file
        # create a datastore object
        dsobject = datastore.create()
        # metadata for the datastore object
        dsobject.metadata['title'] = file_name
        # the picke module serializes objects in simple txt (?!)
        dsobject.metadata['mime_type'] = 'audio/mpeg'

        file_path = os.path.join(activity.get_activity_root(), 'instance', file_name)

        # Quickly show feedback to user
        self.progressbar.pulse()
        self.timer = gobject.timeout_add (100, progress_timeout, self)
        self.progressbar.show()

        self.manager.download_item(url_file, file_path, self._item_downloaded_cb, [dsobject, file_path])

    def _item_downloaded_cb(self, downloaded, user_data, error):
        if downloaded:
            dsobject = user_data[0]
            file_path = user_data[1]
            dsobject.set_file_path(file_path)
            dsobject.metadata['file_path'] = file_path
            datastore.write(dsobject)
            dsobject.destroy()
            message = _('Item downloaded')
        else:
            message = _('Error downloading item')

        # Quickly show feedback to user
        self.status_bar.push(self.context_id, message)
        self.messages_counter += 1
        gobject.source_remove(self.timer)
        self.timer = 0
        self.progressbar.hide()

class LabelsWindow(gtk.VBox):

    LABELS_MODEL_PIXBUF_COLUMN, LABELS_MODEL_NAME_COLUMN, LABELS_MODEL_ID_COLUMN = range(3)

    def __init__(self, manager, settings, conn_manager, activity):
        super(LabelsWindow, self).__init__()

        self._manager = manager
        self._settings = settings
        self._conn_manager = conn_manager
        self.activity = activity
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

        self._view.connect('key-press-event', self.activity._clear_status_bar)
        self._view.connect('button-press-event', self.activity._clear_status_bar)

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

        self.activity.set_canvas(self)
        self.activity.list_content.append(self.activity.get_canvas())
        self.show()

        self.progressbar = gtk.ProgressBar()

        self.status_bar = gtk.Statusbar()      
        self.context_id = self.status_bar.get_context_id('Labelsswindow statusbar')
        self.status_bar.pack_start(self.progressbar, False, False)
        self.pack_start(self.status_bar, False, True, 0)
        self.status_bar.show()
        #To count the number of messages
        self.messages_counter = 0

        # Load Labels (could be none)
        self._manager.load_labels(self._load_labels_cb)

    def _get_folder_icon(self):
        if not self._folder_icon:
            self._folder_icon = gtk.icon_theme_get_default().load_icon('label', 32, 0)
        return self._folder_icon

    def _create_menu(self):
        self.toolbar_box = ToolbarBox()
        self.toolbar_box.connect('key-press-event', self.activity._clear_status_bar)
        self.toolbar_box.connect('button-press-event', self.activity._clear_status_bar)

        activity_button = ActivityToolbarButton(self.activity)

        self.toolbar_box.toolbar.insert(activity_button, 0)
        activity_button.page.keep.props.accelerator = '<Ctrl><Shift>S'
        activity_button.show()

        self.activity.set_toolbar_box(self.toolbar_box)
        self.toolbar_box.show()

        self.add_label_toolbar = self._create_add_label_toolbar()
        self.add_label_toolbar_button = ToolbarButton(
                page=self.add_label_toolbar,
                icon_name='label')
        self.add_label_toolbar.show()
        self.toolbar_box.toolbar.insert(self.add_label_toolbar_button, -1)
        self.add_label_toolbar_button.show()

        self.remove_label_button = ToolButton('delete-label')
        self.remove_label_button.props.accelerator = '<Ctrl><Shift>R'
        self.remove_label_button.set_tooltip(_('Remove one or more labels'))
        self.remove_label_button.connect('clicked', self.activity._clear_messages)
        self.remove_label_button.connect('clicked', self._remove_label_cb)
        self.toolbar_box.toolbar.insert(self.remove_label_button, -1)
        self.remove_label_button.show()

        separator = gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        self.toolbar_box.toolbar.insert(separator, -1)
        separator.show()

        self.stop_button = StopButton(self.activity)
        self.stop_button.props.accelerator = '<Ctrl><Shift>Q'
        self.toolbar_box.toolbar.insert(self.stop_button, -1)
        self.stop_button.connect('clicked', on_exit)
        self.stop_button.show()

    def _create_add_label_toolbar(self):
        add_label_toolbar = gtk.Toolbar()

        add_label_label = gtk.Label(_('New label') + ': ')
        add_label_label.show()
        add_label_item_label = gtk.ToolItem()
        add_label_item_label.add(add_label_label)
        add_label_item_label.show()
        add_label_toolbar.insert(add_label_item_label, 0)
        self.entry_add_label = gtk.Entry()
        self.entry_add_label.show()
        entry_add_label_item = gtk.ToolItem()
        entry_add_label_item.set_expand(True)
        entry_add_label_item.add(self.entry_add_label)
        entry_add_label_item.show()
        add_label_toolbar.insert(entry_add_label_item, -1)
        add_label_toolbar._entry = self.entry_add_label     

        self.add_button = ToolButton('list-add')
        self.add_button.set_tooltip(_('Add a new label'))
        self.add_button.props.accelerator = '<Ctrl><Shift>N'
        self.add_button.connect('clicked', self.activity._clear_messages)
        self.add_button.connect('clicked', self._create_label_response_cb, add_label_toolbar)
        self.add_button.set_sensitive(False)
        add_label_toolbar.insert(self.add_button, -1)
        self.add_button.show()

        self.entry_add_label.connect('changed', self._entry_changed_cb, add_label_toolbar, self.add_button)

        return add_label_toolbar

    def _entry_changed_cb(self, entry, toolbar, button):
        if toolbar._entry.props.text:
            toolbar._entry.activate()
            # set the button contexts
            button.set_sensitive(True)
            return
        else:
            button.set_sensitive(False)

    def _load_labels_cb(self, retval, user_data, error):
        if error:
            # Quickly show feedback to user
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
        all_feeds_icon = gtk.icon_theme_get_default().load_icon('go-home', 32, 0)
        feed_iter = store.append()
        store.set(feed_iter, LabelsWindow.LABELS_MODEL_NAME_COLUMN, _('All Feeds'),
                  LabelsWindow.LABELS_MODEL_ID_COLUMN, constants.ALL_LABEL_ID,
                  LabelsWindow.LABELS_MODEL_PIXBUF_COLUMN, all_feeds_icon)

        if len(labels) == 0:
            self.remove_label_button.set_sensitive(False)


    def _create_label_response_cb(self, button, toolbar):
        # We do not need to add it to the view. The 'label-created'
        # signal handler will do it for us.
        label_name = toolbar._entry.props.text
        toolbar._entry.props.text = ''
        label_id = self._manager.create_label(label_name)

        if not label_id:
            # Quickly show feedback to user
            self.status_bar.push(self.context_id, _('Label not created. Already exists.'))
            self.messages_counter += 1
            return

    def _on_label_created_cb(self, manager, label_id):
        label_name = manager.get_label_name(label_id)

        # Add label to the view
        store = self._view.get_model()
        feed_iter = store.append()
        store.set(feed_iter, LabelsWindow.LABELS_MODEL_NAME_COLUMN, gobject.markup_escape_text(label_name),
                  LabelsWindow.LABELS_MODEL_ID_COLUMN, label_id,
                  LabelsWindow.LABELS_MODEL_PIXBUF_COLUMN, self._get_folder_icon())

        self.remove_label_button.set_sensitive(True)

    def _on_label_activated(self, treeview, path, column):
        label_iter = self._view.get_model().get_iter(path)
        label_id = self._view.get_model().get_value(label_iter, LabelsWindow.LABELS_MODEL_ID_COLUMN)

        if label_id == constants.ALL_LABEL_ID:
            name = _('All Feeds')
        else:
            name = self._manager.get_label_name(label_id)  
        
        if not self._feeds_window:
            self._feeds_window = FeedsWindow(self._manager, self._settings, self._conn_manager, self.activity, name)
        else:
            self._feeds_window._set_title(name)
            # Do not destroy the Feeds Window keep it cached instead
            self.activity.set_canvas(self._feeds_window)
            self.activity.list_content.append(self.activity.get_canvas())
        self._feeds_window.set_filter_label_id(label_id)
        if self._feeds_window:
            self._feeds_window._create_menu()

    def _remove_label_cb(self, button):
        selection = self._view.get_selection()
        selected_rows = selection.get_selected_rows()
        store, paths = selected_rows
        if not paths:
            # Quickly show feedback to user
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

class FeedsLabelsView(gtk.TreeView):
    def __init__(self):
        super(FeedsLabelsView, self).__init__()

        text_renderer = gtk.CellRendererText()
        text_renderer.set_property('ellipsize', ELLIPSIZE_END)

        pix_renderer = gtk.CellRendererPixbuf()

        # Add columns
        # Feed icon column
        column = gtk.TreeViewColumn(_('Icon'), pix_renderer, pixbuf = FeedsLabelsWindow.FEED_SELECT_MODEL_PIXBUF_COLUMN)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_resizable(True)
        column.set_fixed_width(100)
        self.append_column(column);       

        #Title/subtitle column
        column = gtk.TreeViewColumn(_('Name'), text_renderer, markup = FeedsLabelsWindow.FEED_SELECT_MODEL_NAME_COLUMN)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_resizable(True)
        column.set_expand(True)
        self.append_column(column);

class FeedsLabelsWindow(gtk.VBox):

    FEED_SELECT_MODEL_PIXBUF_COLUMN, FEED_SELECT_MODEL_NAME_COLUMN, FEED_SELECT_MODEL_ID_COLUMN = range(3)

    def __init__(self, manager, settings, conn_manager, add_to_label, feeds_window, label_id, activity):
        super(FeedsLabelsWindow, self).__init__()

        self._manager = manager
        self._settings = settings
        self._conn_manager = conn_manager
        self.feeds_window = feeds_window
        self.label_id = label_id
        self.activity = activity
        self.add_to_label = add_to_label

        self._view = FeedsLabelsView()

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        self.pack_start(scroll, True, True, 0)
        scroll.add(self._view)
        scroll.show()

        store = gtk.ListStore(gtk.gdk.Pixbuf, str, int)

        model_filter = store.filter_new()
        self._view.set_model (model_filter)
        self._view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self._view.show()

        self._create_menu()

        self.activity.set_canvas(self)
        self.activity.list_content.append(self.activity.get_canvas())
        self.show()

        feed_summaries = self._manager.get_feed_summaries()
        for summary in feed_summaries:
            has_label = self._manager.feed_has_label(summary.feed_id, self.label_id)
            if self.label_id == constants.ALL_LABEL_ID or \
                    has_label if not self.add_to_label else not has_label:
                feed_iter = store.append()
                store.set(feed_iter, FeedsLabelsWindow.FEED_SELECT_MODEL_ID_COLUMN, summary.feed_id,
                          FeedsLabelsWindow.FEED_SELECT_MODEL_NAME_COLUMN, get_feed_title_markup(summary.title))
                # Favicon
                path = store.get_path(feed_iter)
                row_reference = gtk.TreeRowReference(store, path)
                self._manager.get_favicon(summary.favicon, self._get_favicon_cb, row_reference)

    def _get_favicon_cb(self, pixbuf, row_reference, error):
        if pixbuf == None:
            return

        store = self._view.get_model().get_model()
        feed_iter = store.get_iter(row_reference.get_path())
        store.set(feed_iter, FeedsLabelsWindow.FEED_SELECT_MODEL_PIXBUF_COLUMN, pixbuf)

    def _selection_changed(self, selector, user_data):
        rows = selector.get_selected_rows(0)
        self.set_response_sensitive(gtk.RESPONSE_ACCEPT, False if len(rows) == 0 else True)

    def get_selected_feed_ids(self):
        selection = self._view.get_selection()
        selected_rows = selection.get_selected_rows()
        model, paths = selected_rows
        
        feed_ids = []
        for path in paths:
            item_iter = self._view.get_model().get_iter(path)
            feed_ids.append(self._view.get_model().get_value(item_iter, self.FEED_SELECT_MODEL_ID_COLUMN))
        return feed_ids

    def _create_menu(self):
        self.toolbar_box = ToolbarBox()
        self.toolbar_box.connect('key-press-event', self.activity._clear_status_bar)
        self.toolbar_box.connect('button-press-event', self.activity._clear_status_bar)

        activity_button = ActivityToolbarButton(self.activity)

        self.toolbar_box.toolbar.insert(activity_button, 0)
        activity_button.page.keep.props.accelerator = '<Ctrl><Shift>S'
        activity_button.show()

        self.activity.set_toolbar_box(self.toolbar_box)
        self.toolbar_box.show()

        
        self._add_feed_label_button = ToolButton('list-add')
        self._add_feed_label_button.props.accelerator = '<Ctrl><Shift>A'
        self._add_feed_label_button.set_tooltip(_('Add these feeds to the label'))
        self._add_feed_label_button.connect('clicked', self._feeds_selected_cb, self.add_to_label)
        self.toolbar_box.toolbar.insert(self._add_feed_label_button, -1)
        self._add_feed_label_button.show()

        self._remove_feed_label_button = ToolButton('list-remove')
        self._remove_feed_label_button.props.accelerator = '<Ctrl><Shift>A'
        self._remove_feed_label_button.set_tooltip(_('Remove these feeds from the label'))
        self._remove_feed_label_button.connect('clicked', self._feeds_selected_cb, self.add_to_label)
        self.toolbar_box.toolbar.insert(self._remove_feed_label_button, -1)
        self._remove_feed_label_button.show()

        self._remove_feed_label_button.hide() if self.add_to_label else self._add_feed_label_button.hide()

        separator = gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        self.toolbar_box.toolbar.insert(separator, -1)
        separator.show()

        self.back_button = ToolButton('back')
        self.back_button.props.accelerator = '<Ctrl><Shift>B'
        self.back_button.set_tooltip(_('Return to the previous window'))
        self.back_button.connect('clicked', self.activity._back_clicked_cb, self)
        self.toolbar_box.toolbar.insert(self.back_button, -1)
        self.back_button.show()

        self.stop_button = StopButton(self.activity)
        self.stop_button.props.accelerator = '<Ctrl><Shift>Q'
        self.toolbar_box.toolbar.insert(self.stop_button, -1)
        self.stop_button.connect('clicked', on_exit)
        self.stop_button.show()

    def _feeds_selected_cb(self, button, add_to_label):
        selected_feeds = self.get_selected_feed_ids()        
        if add_to_label:
            self._manager.add_feeds_to_label(selected_feeds, self.feeds_window._filter_label_id)
        else:
            self._manager.remove_feeds_from_label(selected_feeds, self.feeds_window._filter_label_id)

        # Update view
        store = self.feeds_window.view.get_model().get_model()
        for row in store:
            if row[FeedsWindow.FEEDS_MODEL_ID_COLUMN] in selected_feeds:
                row[FeedsWindow.FEEDS_MODEL_LABEL_VISIBLE_COLUMN] = add_to_label
        
        if self.feeds_window.settings.show_labels_startup:
            self.feeds_window._update_labels_menu()

        self.activity._back_clicked_cb(None, self)

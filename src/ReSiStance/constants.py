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

import os
import sys

RSS_NAME = 'ReSiStance'
RSS_COMPACT_NAME = 'resistance'
RSS_VERSION = '0.9.1'
RSS_DESCRIPTION = 'ReSiStance is a RSS feeds reader'
RSS_URL = 'http://www.igalia.com'

try: 
    from sugar.activity import bundlebuilder
    from sugar.activity import activity
    HOME_PATH = os.path.join(activity.get_activity_root(), 'data')
except ImportError:
    HOME_PATH = os.path.expanduser('~')

RSS_CONF_FOLDER = os.path.join(HOME_PATH, RSS_COMPACT_NAME)
RSS_CONF_FILE = os.path.join(RSS_CONF_FOLDER, '%s.conf' % RSS_COMPACT_NAME)
RSS_DB_DIR = os.path.join(RSS_CONF_FOLDER, 'feeds')
OLD_RSS_DB_FILE = os.path.join(RSS_CONF_FOLDER, '%s' % 'feeds.db')
RSS_DB_SUMMARY_FILE = os.path.join(RSS_CONF_FOLDER, '%s' % 'feed-summaries.db')

DEFAULT_SYSTEM_APP_DIR = os.path.join(sys.prefix,
                                      'share',
                                      RSS_COMPACT_NAME)
APP_DIR = DEFAULT_SYSTEM_APP_DIR

if not os.path.exists(APP_DIR):
    APP_DIR = os.path.curdir
    APP_DIR = os.path.join(APP_DIR, 'data')

RSS_SPEC_FILE = os.path.join(APP_DIR, '%s_spec.ini' % RSS_COMPACT_NAME)

LOCALE_DIR = os.path.join(sys.prefix,
                         'share',
                         'locale')

DEFAULT_LANGUAGES = os.environ.get('LANGUAGE', '').split(':')
DEFAULT_LANGUAGES += ['en_US']

# Default RSS icon for feeds without favicon
DEFAULT_FAVICON = os.path.join(APP_DIR, 'feed-presence.png')

ICON_UP_NAME = "rss_reader_move_up"
ICON_DOWN_NAME = "rss_reader_move_down"

ASCENDING_ORDER, DESCENDING_ORDER, VISITS_ORDER = range(3)
font_size_range = range(12,28,4)
SHOW_ALL_FILTER, SHOW_UNREAD_FILTER = range(2)

MYDOCS_DIR = '/home/user/MyDocs/.documents'

#Google Reader
URL_LOGIN = "https://www.google.com/accounts/ClientLogin"
GOOGLE_READER_ATOM_URL = 'http://www.google.com/reader/atom/'
GOOGLE_READER_API_URL = 'http://www.google.com/reader/api/0/'
URL_TOKEN = GOOGLE_READER_API_URL + 'token'
URL_SUBSCRIPTION_LIST = GOOGLE_READER_API_URL + 'subscription/list?output=xml&client=-'
URL_FEED = GOOGLE_READER_ATOM_URL + 'feed/'
URL_USER = GOOGLE_READER_ATOM_URL + 'user/-/'
LABEL_SUFFIX = "label/"
STATE_SUFFIX = "state/com.google/"
URL_EDIT = GOOGLE_READER_API_URL + 'edit-tag?client=-'
URL_SUBSCRIPTION_EDIT = GOOGLE_READER_API_URL + 'subscription/edit'
GOOGLE_READER_ICON_FILE = os.path.join(APP_DIR, 'prism-google-reader.png')
GOOGLE_READER_REMOVE_ICON_FILE = os.path.join(APP_DIR, 'prism-google-reader_remove.png')

# Labels
ALL_LABEL_ID = 0
RSS_LABEL_DB_FILE = os.path.join(RSS_CONF_FOLDER, '%s' % 'labels.db')

#Icons
EXPORT_ICON_FILE = os.path.join(APP_DIR, 'export.png')
IMPORT_ICON_FILE = os.path.join(APP_DIR, 'import.png')
ADD_TO_LABEL_ICON_FILE = os.path.join(APP_DIR, 'add-to-label.png')
REMOVE_FROM_LABEL_ICON_FILE = os.path.join(APP_DIR, 'remove-from-label.png')


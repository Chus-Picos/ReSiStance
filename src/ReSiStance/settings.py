#!/usr/bin/env python
# -*- coding: utf-8 -*-

#########################################################################
#    Copyright (C) 2010 Sergio Villar Senin <svillar@igalia.com>
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
import constants
from portrait import FremantleRotation
from configobj import ConfigObj
from validate import Validator

def stringToBoolean(str):
    return str=='True'

class Settings(object):

    def __init__(self):
        self.reset_to_defaults()
        self.config = None
        self.validator = Validator()
        self.spec = ConfigObj(constants.RSS_SPEC_FILE, encoding='UTF8',
                              list_values=False)

    def reset_to_defaults(self):
        self.feeds_order = constants.ASCENDING_ORDER
        self.default_font_size = 16
        self.auto_load_images = True
        self.rotation_mode = FremantleRotation.AUTOMATIC
        self.auto_download = False
        self.auto_download_folder = '/home/user/MyDocs'
        self.user  = ''
        self.password = ''
        self.sync_global = False
        self.entries_filter = constants.SHOW_ALL_FILTER
        self.delete_old = False
        self.auto_update_startup = False
        self.show_labels_startup = False

    def load(self):
        if not (os.path.exists(constants.RSS_CONF_FILE) and
                os.path.isfile(constants.RSS_CONF_FILE)):
            return

        if self.config == None:
            self.config = ConfigObj(constants.RSS_CONF_FILE, configspec=self.spec)
            if self.config.validate(self.validator) == False:
                self.reset_to_defaults()
                return

        self.feeds_order = self.config['feeds_order']
        self.default_font_size = int(self.config['default_font_size'])
        self.auto_load_images = stringToBoolean(self.config['auto_load_images'])
        self.rotation_mode = int(self.config['rotation_mode'])
        self.auto_download = stringToBoolean(self.config['auto_download']) if 'auto_download' in self.config else False
        self.auto_download_folder = self.config['auto_download_folder'] if 'auto_download_folder' in self.config else '/home/user/MyDocs'
        self.user = self.config['user'] if 'user' in self.config else ''
        self.password = self.config['password'] if 'password' in self.config else ''
        self.sync_global = stringToBoolean(self.config['sync_global']) if 'sync_global' in self.config else False
        self.entries_filter = int(self.config['entries_filter']) if 'entries_filter' in self.config else constants.SHOW_ALL_FILTER
        self.delete_old = stringToBoolean(self.config['delete_old']) if 'delete_old' in self.config else False
        self.auto_update_startup = stringToBoolean(self.config['auto_update_startup']) if 'auto_update_startup' in self.config else False
        self.show_labels_startup = stringToBoolean(self.config['show_labels_startup']) if 'show_labels_startup' in self.config else False

    def save(self):
        if self.config == None:
            self.config = ConfigObj(constants.RSS_CONF_FILE, configspec=self.spec)
            self.config.validate(self.validator)

        self.config['feeds_order'] = self.feeds_order
        self.config['default_font_size'] = self.default_font_size
        self.config['auto_load_images'] = self.auto_load_images
        self.config['rotation_mode'] = self.rotation_mode
        self.config['auto_download'] = self.auto_download
        self.config['auto_download_folder'] = self.auto_download_folder
        self.config['user'] = self.user
        self.config['password'] = self.password
        self.config['sync_global'] = self.sync_global
        self.config['entries_filter'] = self.entries_filter
        self.config['delete_old'] = self.delete_old
        self.config['auto_update_startup'] = self.auto_update_startup
        self.config['show_labels_startup'] = self.show_labels_startup

        self.config.write()

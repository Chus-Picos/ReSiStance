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

import glib
import gtk
import htmlentitydefs
import re
from gobject import markup_escape_text
from time import localtime, strftime
from os import getenv
from xml.dom.minidom import parseString

# SYSTEM COLORS
#color_style = gtk.rc_get_style_by_paths(gtk.settings_get_default() , 'GtkButton', 'osso-logical-colors', gtk.Button)
#ACTIVE_TEXT_COLOR = color_style.lookup_color('ActiveTextColor').to_string()
#DEFAULT_TEXT_COLOR = color_style.lookup_color('DefaultTextColor').to_string()
#SECONDARY_TEXT_COLOR = color_style.lookup_color('SecondaryTextColor').to_string()
#del color_style

# From http://effbot.org/zone/re-sub.htm#unescape-html
def unescape(text):
    def fixup(m):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text # leave as is
    return re.sub("&#?\w+;", fixup, text)

def get_author_from_item(item):
    from_title = False

    # I found some feeds with author_detail but without name,
    # email..., just with a 'value' key
    if 'author_detail' in item and 'name' in item.author_detail:
        author = item.author_detail.name
    elif 'author' in item:
        author = item.author
    elif 'publisher_detail' in item and 'name' in item.publisher_detail:
        author = item.publisher_detail.name
    else:
        from_title = True
        words = item.title.rsplit(":")
        if len(words) > 1:
            author = words[0].lstrip()
        else:
            author = ''

    if not from_title:
        try:
            doc = parseString(author)
            author = doc.documentElement.firstChild.data
        except:
            pass

    return author

def get_title_from_item(item):
    words = item.title.rsplit(":")
    author = get_author_from_item(item)
    if len(words) > 1 and author == words[0].lstrip():
        title = words[1].lstrip()
    else:
        title = item.title

    return markup_escape_text(unescape(title))

def get_feed_title_markup(title):
    return '<span foreground="%s">%s</span>' % \
        (DEFAULT_TEXT_COLOR, glib.markup_escape_text(unescape(title)))

def get_feed_subtitle(feed_data):
    if 'subtitle' in feed_data.feed:
        subtitle = feed_data.feed.subtitle
    else:
        if 'link' in  feed_data.feed:
            subtitle = feed_data.feed.link
        else:
            subtitle = feed_data.href
    return subtitle

def get_feed_subtitle_markup(subtitle):

    return '<span foreground="%s">%s</span>' % \
        (SECONDARY_TEXT_COLOR, glib.markup_escape_text(unescape(subtitle)))

def get_feed_icon_uri(feed_data):
    if 'icon' in feed_data.feed:
        return feed_data.feed.icon
    elif 'link' in feed_data.feed:
        return feed_data.feed.link
    else:
        return feed_data.href

def get_visual_unread_text(unread_count):
    if unread_count:
        return '<span size="small"> %d </span>' % unread_count
    else:
        return ''

def get_feed_id(feed_data):
    return hash(feed_data.href)

def get_visual_entry_date(entry, small):
    tag_format = '<span size="xx-small">%s</span>' if small else \
        '<span size="small">%s</span>';

    if entry.has_key('updated_parsed') == False:
        if entry.has_key('updated'):
            return tag_format % entry.updated
        else:
            return ''

    now = localtime()

    if now.tm_year == entry.updated_parsed.tm_year:
        # Today
        if now.tm_yday == entry.updated_parsed.tm_yday:
            return tag_format % strftime('%H:%M', entry.updated_parsed)
        # This week
        elif now.tm_yday - entry.updated_parsed.tm_yday < 7 and \
                entry.updated_parsed.tm_wday < now.tm_wday:
            str_format = '%a' if small else '%A'
            return tag_format % strftime(str_format, entry.updated_parsed)
        # This year
        else:
            str_format = '%d %b' if small else '%D'
            return tag_format % strftime(str_format, entry.updated_parsed)
    # Anything else
    else:
        str_format = '%x' if small else '%X'
        return tag_format % strftime('%x', entry.updated_parsed)

def inside_sbox():
    # if that environment variable is set then we're running inside
    # the sbox
    if getenv("SBOX_REDIRECT_BINARIES"):
        return True
    return False

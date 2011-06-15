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

from sys import maxint as MAXINT
import cairo
import constants
import gobject
import gtk

# As defined here: http://docs.python.org/library/sys.html
MININT = -MAXINT-1

# SYSTEM FONTS
font_style = gtk.rc_get_style_by_paths(gtk.settings_get_default(), 'SystemFont', None, None)
SYSTEM_FONT_DESC = font_style.font_desc
del font_style

font_style = gtk.rc_get_style_by_paths(gtk.settings_get_default(), 'SmallSystemFont', None, None)
SMALL_FONT_DESC = font_style.font_desc
del font_style

color_style = gtk.rc_get_style_by_paths(gtk.settings_get_default() , 'GtkButton', 'osso-logical-colors', gtk.Button)
SELECTION_COLOR = color_style.lookup_color('SelectionColor')
del color_style

class FeedCellRenderer(gtk.GenericCellRenderer):
    __gproperties__ = {
        'id': (int, 'The feed ID', 'The feed ID', MININT, MAXINT, 0, gobject.PARAM_READWRITE),
        'title': (str, 'The pixbuf to render', 'The pixbuf to render', None, gobject.PARAM_READWRITE),
        'subtitle': (str, 'The pixbuf to render', 'The pixbuf to render', None, gobject.PARAM_READWRITE),
        'sync': (gobject.TYPE_BOOLEAN, 'The pixbuf to render', None, False, gobject.PARAM_READWRITE),
    }

    def __init__(self, pixbuf):
        self.__gobject_init__()
        self.id = 0
        self.pixbuf = pixbuf
        self.title = None
        self.subtitle = None
        self.sync = False
        self._layout_cache = {}
        self._pix_rect = None

    def on_get_size(self, widget, cell_area):

        title_layout, subtitle_layout, title_size, subtitle_size = self._get_layouts(widget)

        calc_width = self.get_property('xpad') * 2 + max(title_size[0], subtitle_size[0]) + self.pixbuf.get_width()
        calc_height = self.get_property('ypad') * 2 + title_size[1] + subtitle_size[1]

        if cell_area:
            x_offset = self.get_property('xalign') * (cell_area.width - calc_width - self.get_property('xpad'))
            x_offset = max(x_offset, 0)
            y_offset = self.get_property('yalign') * (cell_area.height - calc_height - self.get_property('ypad'))
            y_offset = max(y_offset, 0)
        else:
            x_offset = 0
            y_offset = 0

        return x_offset, y_offset, calc_width, calc_height

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_set_property(self, pspec, value):
        if not hasattr(self, pspec.name):
            raise AttributeError, 'unknown property %s' % pspec.name
        setattr(self, pspec.name, value)


    TITLE, SUBTITLE = range(2)

    def _get_layouts(self, widget):
        try:
            title_layout, subtitle_layout, title_size, subtitle_size = self._layout_cache[self.id]
        except KeyError:
            # Create layouts
            title_layout = widget.create_pango_layout('')
            title_layout.set_markup(self.title)
            subtitle_layout = widget.create_pango_layout('')
            subtitle_layout.set_markup(self.subtitle)
            # Apply font descriptions
            title_layout.set_font_description(SYSTEM_FONT_DESC)
            subtitle_layout.set_font_description(SMALL_FONT_DESC)
            # Compute sizes
            title_size = title_layout.get_pixel_size()
            subtitle_size = subtitle_layout.get_pixel_size()
            # Id -1 means no caching
            if self.id != -1:
                self._layout_cache[self.id] = (title_layout, subtitle_layout, title_size, subtitle_size)
        return title_layout, subtitle_layout, title_size, subtitle_size

    def on_render(self, window, widget, background_area, cell_area, expose_area, flags):
        if not self.pixbuf:
            return

        if not self._pix_rect:
            self._pix_rect = gtk.gdk.Rectangle()

        self._pix_rect.x, self._pix_rect.y, self._pix_rect.width, self._pix_rect.height = \
            self.on_get_size(widget, cell_area)

        self._pix_rect.x += cell_area.x + self.get_property('xpad')
        self._pix_rect.y += cell_area.y + self.get_property('ypad')
        self._pix_rect.width -= self.get_property('xpad') * 2
        self._pix_rect.height -= self.get_property('ypad') * 2

        draw_rect = cell_area.intersect(self._pix_rect)
        draw_rect = expose_area.intersect(draw_rect)

        context = window.cairo_create()

        # Draw text
        title_layout, subtitle_layout, title_size, subtitle_size = self._get_layouts(widget)
        widget.style.paint_layout(window, widget.state, False,
                                  None, widget, None, draw_rect.x, draw_rect.y, title_layout)
        widget.style.paint_layout(window, widget.state, False,
                                  None, widget, None, draw_rect.x, draw_rect.y + title_layout.get_pixel_size()[1], subtitle_layout)

        # Google Reader like icon
        if self.sync:
            context.set_source_pixbuf(self.pixbuf, draw_rect.x + title_layout.get_pixel_size()[0], draw_rect.y)
            context.paint()

gobject.type_register(FeedCellRenderer)

class CellRendererRoundedRectangleText(gtk.GenericCellRenderer):
    __gproperties__ = {
        'id': (int, 'id', 'the id', MININT, MAXINT, 0, gobject.PARAM_READWRITE),
        'text': (str, 'unread', 'the unread count', None, gobject.PARAM_READWRITE),
    }

    def __init__(self):
        self.__gobject_init__()
        self.id = -1
        self.text = None
        self._layout_cache = {}
        self._size_cache = None
        self._radius = 0.9
        self._pix_rect = gtk.gdk.Rectangle()
        self._color = (float(SELECTION_COLOR.red)/65535,
                       float(SELECTION_COLOR.green)/65535,
                       float(SELECTION_COLOR.blue)/65535)

    def on_get_size(self, widget, cell_area):

        if not self._size_cache:
            sample_layout = widget.create_pango_layout('')
            self._size_cache = sample_layout.get_pixel_size()

        layout, size = self._get_layout(widget)
        if size[0] > self._size_cache[0]:
            self._size_cache = size

        calc_width = self.props.xpad * 2 + self._size_cache[0]
        calc_height = self.props.ypad * 2 + self._size_cache[1]

        if cell_area and self._size_cache[0] > 0 and self._size_cache[1] > 0:
            x_offset = self.props.xalign * (cell_area.width - calc_width - self.props.xpad)
            y_offset = self.props.yalign * (cell_area.height - calc_height - self.props.ypad)
        else:
            x_offset = 0
            y_offset = 0

        return x_offset, y_offset, calc_width, calc_height

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_set_property(self, pspec, value):
        if not hasattr(self, pspec.name):
            raise AttributeError, 'unknown property %s' % pspec.name
        setattr(self, pspec.name, value)

    def _get_layout(self, widget):
        try:
            title_layout, title_size = self._layout_cache[self.id]
        except KeyError:
            # Create layouts
            title_layout = widget.create_pango_layout('')
            title_layout.set_markup(self.text)
            # Apply font descriptions
            title_layout.set_font_description(SYSTEM_FONT_DESC)
            # Compute sizes
            title_size = title_layout.get_pixel_size()
            # Id -1 means no caching
            if self.id != -1:
                self._layout_cache[self.id] = (title_layout, title_size)
        return title_layout, title_size

    def on_render(self, window, widget, background_area, cell_area, expose_area, flags):

        self._pix_rect.x, self._pix_rect.y, self._pix_rect.width, self._pix_rect.height = \
            self.on_get_size(widget, cell_area)

        self._pix_rect.x += cell_area.x + self.props.xpad
        self._pix_rect.y += cell_area.y + self.props.ypad
        self._pix_rect.width -= 2 * self.props.xpad
        self._pix_rect.height -= 2 * self.props.ypad

        # We add some extra width in order to give some room for the text inside the rectange
        self._pix_rect.width += 8

        draw_rect = cell_area.intersect(self._pix_rect)
        draw_rect = expose_area.intersect(draw_rect)

        context = window.cairo_create()
        r = self._radius * min((draw_rect.width, draw_rect.height))

        # Get text layout. Always reset text as this could easily change
        layout, size = self._get_layout(widget)
        layout.set_markup(self.text)

        # If there are not unread feeds do not draw anything
        if not size[0]:
            return

        # Rectangle color
        context.set_source_rgb(self._color[0], self._color[1], self._color[2])

        # Draw rectangle
        self.draw_round_rect(context, draw_rect.x, draw_rect.y, \
            draw_rect.width, draw_rect.height, r)
        context.fill()

        # Draw text
        x = (draw_rect.width - size[0])/2
        y = (draw_rect.height - size[1])/2
        widget.style.paint_layout(window, widget.state, False,
                                  None, widget, None, draw_rect.x + x, draw_rect.y + y, layout)

    def draw_round_rect(self, context, x, y, w, h, r):
        context.move_to(x+r,y)
        context.line_to(x+w-r,y)
        context.curve_to(x+w,y,x+w,y,x+w,y+r)
        context.line_to(x+w,y+h-r)
        context.curve_to(x+w,y+h,x+w,y+h,x+w-r,y+h)
        context.line_to(x+r,y+h)
        context.curve_to(x,y+h,x,y+h,x,y+h-r)
        context.line_to(x,y+r)
        context.curve_to(x,y,x,y,x+r,y)
        context.close_path()

gobject.type_register(CellRendererRoundedRectangleText)

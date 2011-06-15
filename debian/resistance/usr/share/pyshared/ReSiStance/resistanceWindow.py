#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gtk
import gettext

_ = gettext.gettext

class ResistanceWindow():
    """ A python singleton """

    class __impl():
        """ Implementation of the singleton interface """

        def window_content(self, vbox, hbox=None):
            #Is a window with content
            if self.content:
                self.list_content.append(self.vbox_in)
                self.vbox.remove(self.vbox_in)

                self.vbox_in = vbox

                if hbox:                
                    self.button_back = gtk.Button(stock=gtk.STOCK_GO_BACK) 
                    self.button_back.set_label(_('Back'))
                    self.button_back_connect_id = self.button_back.connect('clicked', self.return_cb)
                    self.button_back.set_tooltip_text( _('Return to the previous window [Ctrl+B]'))
                    key, mod = gtk.accelerator_parse("<Control>B")
                    self.button_back.add_accelerator('clicked', self.agr, key, mod, gtk.ACCEL_VISIBLE)
                    self.button_back.show_all()

                    hbox.pack_start(self.button_back, False, False, 5)

                    self.vbox_in.pack_start(hbox, False, False, 0)
                                  
            #Is the first window
            else:
                self.vbox_in = vbox
            
            self.vbox.pack_start(self.vbox_in, True, True)  

            self.content = True
            self.window.show_all()

        def return_cb(self, button=None):
            self.vbox.remove(self.vbox_in)
            self.vbox_in = self.list_content[(len(self.list_content)-1)]
            self.vbox.pack_start(self.vbox_in, True, True)
            self.list_content = self.list_content[0:len(self.list_content)-1]
  
        def resistance_window_agr(self):
            return self.agr

        def get_window(self):
            return self.window

        def get_back_button(self):
            return self.button_back

        def get_button_back_connect_id(self):
            return self.button_back_connect_id

    def destroy(self, widget, data=None):
        # Close application
        gtk.main_quit()
        

    # storage for the instance reference
    __instance = None

    def __init__(self):
        """ Create singleton instance """
        # Check whether we already have an instance
        if ResistanceWindow.__instance is None:
            # Create and remember instance
            ResistanceWindow.__instance = ResistanceWindow.__impl()
            self.list_content = []
            self.content = False
            self.vbox = gtk.VBox(False, 0)
            self.window = gtk.Window()
            screen = self.window.get_screen()
            self.window.maximize()
            self.window.add(self.vbox)
            self.agr = gtk.AccelGroup()
            self.window.add_accel_group(self.agr)
            
        # Store instance reference as the only member in the handle
        self.__dict__['_Singleton__instance'] = ResistanceWindow.__instance

    def __getattr__(self, attr):
        """ Delegate access to implementation """
        return getattr(self.__instance, attr)

    def __setattr__(self, attr, value):
        """ Delegate access to implementation """
        return setattr(self.__instance, attr, value)

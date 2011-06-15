#!/usr/bin/python

#You must execute ReSiStance in English to test

from dogtail.tree import *
from dogtail.utils import *
from dogtail.rawinput import *
from dogtail.procedural import *

def new_label_test():
    click('New Label')
    typeText('label_test_1')
    pressKey('Return')

def remove_label_test():
    keyCombo('<Ctrl>n')
    typeText('label_test_2')
    pressKey('Return')

    pressKey('Tab')
    pressKey('Tab')
    pressKey('Tab')
    pressKey('Down')
    pressKey('Down')
    keyCombo('<Ctrl>d')
    pressKey('Tab')    
    pressKey('Return')

def open_all_feeds():
    pressKey('Tab')
    pressKey('Down')
    pressKey('Return')

def subscribe():
    keyCombo('<Ctrl>n')
    typeText('http://www.fic.udc.es/HarvestExternalData.do?operation=rss&idConfig=1')
    pressKey('Return')

def open_entry():
    pressKey('Tab')
    pressKey('Tab')
    pressKey('Tab')
    pressKey('Tab')
    pressKey('Down')   
    pressKey('Return')

def mark_entry_read():
    pressKey('Tab')
    pressKey('Tab')
    pressKey('Tab')
    pressKey('Down') 
    pressKey('Down') 
    keyCombo('<Ctrl>m')

def open_item():
    pressKey('Tab')
    pressKey('Tab')
    pressKey('Tab')
    pressKey('Down') 
    pressKey('Down') 
    pressKey('Down') 
    pressKey('Down') 
    pressKey('Return')

def show_only_unread():
    click('Show Unread')

def show_all():
    click('Show All')

def back():
    keyCombo('<Ctrl>b')

def export_feeds():
    keyCombo('<Ctrl>e')
    typeText('resistance-feeds-test')
    pressKey('Return')

def import_feeds():
    keyCombo('<Ctrl>i')
    typeText('resistance-feeds-test')
    pressKey('Return')

def remove_feed():
    keyCombo('<Ctrl>d')
    pressKey('Tab')
    pressKey('Return')

def open_settings():
    keyCombo('<Ctrl>s')

def find_feeds():
    keyCombo('<Ctrl>f')
    typeText('Cambridge')
    pressKey('Return')

def open_label():
    pressKey('Down')
    pressKey('Down')
    doDelay(1)
    pressKey('Return')

def add_to_label():
    keyCombo('<Ctrl>l')
    pressKey('Down')
    pressKey('Tab')
    pressKey('Return')

def remove_from_label():
    keyCombo('<Ctrl><Shift>l')
    pressKey('Down')
    pressKey('Tab')
    pressKey('Return')

def main():
    run('./resistance')
    focus.application('resistance')

    new_label_test()
    doDelay(2)
    remove_label_test()
    doDelay(2)
    open_all_feeds()
    doDelay(2)
    subscribe()
    doDelay(15)
    open_entry()
    doDelay(2)
    mark_entry_read()
    doDelay(2)
    show_only_unread()
    doDelay(5)
    show_all()
    doDelay(2)
    open_item()
    doDelay(3)
    back()
    doDelay(2)
    back()
    export_feeds()
    doDelay(2)
    remove_feed()
    doDelay(3)
    import_feeds()
    doDelay(6)
    open_settings()
    doDelay(3)
    back()
    pressKey('Tab')
    doDelay(2)
    pressKey('Return')
    find_feeds()
    doDelay(10)
    back()
    back()
    open_label()
    doDelay(2)
    add_to_label()
    doDelay(3)
    remove_from_label()
    back()

if __name__ == "__main__":
    main()

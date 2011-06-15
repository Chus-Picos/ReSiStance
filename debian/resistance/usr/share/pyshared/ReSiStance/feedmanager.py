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

from asyncworker import AsyncWorker, AsyncItem, PriorityQueue
from time import time
from utils import get_feed_id, get_feed_icon_uri, get_feed_subtitle
from Queue import Queue
import constants
import cPickle
import feedparser
import gobject
import gtk
import os
import urllib
import urllib2
import urlparse
import xmlrpclib

from settings import Settings
from sgmllib import SGMLParser
from threading import Thread
from xml.dom import minidom
from xml.dom.minidom import Document

# http://diveintomark.org/archives/2002/05/31/rss_autodiscovery_in_python
def getRSSLink(url):
    BUFFERSIZE = 1024

    try:
        usock = urllib.urlopen(url)
        parser = LinkParser()
        while 1:
            buffer = usock.read(BUFFERSIZE)
            parser.feed(buffer)
            if parser.nomoretags: break
            if len(buffer) < BUFFERSIZE: break
        usock.close()
        return urlparse.urljoin(url, parser.href)
    except IOError:
        print 'Could not establish a connection to ' + url
        return ''


class LinkParser(SGMLParser):
    def reset(self):
        SGMLParser.reset(self)
        self.href = ''

    def do_link(self, attrs):
        if not ('rel', 'alternate') in attrs:
            return
        if (not ('type', 'application/rss+xml') in attrs) and \
                (not ('type', 'application/atom+xml') in attrs):
            return
        hreflist = [e[1] for e in attrs if e[0]=='href']
        if hreflist:
            self.href = hreflist[0]
        self.setnomoretags()

    def end_head(self, attrs):
        self.setnomoretags()
    start_body = end_head

class ReSiStanceFeedDict(feedparser.FeedParserDict):

    def __init__(self, feed_data):
        super(ReSiStanceFeedDict, self).__init__()

        self.update(feed_data)

        # Initialize data
        for entry in self.entries:
            if not 'read' in entry:
                entry['read'] = False

        # Remove data from old versions
        if 'visits' in self:
            del self['visits']

        if 'id' in self:
            del self['id']

        if 'sync' in self:
            del self['sync']

class ReSiStanceFeedSummary(dict):

    def __init__(self, feed_id, href, title, subtitle, favicon, visits, unread, sync):
        super(dict, self).__init__()

        self.feed_id = feed_id
        self.href = href
        self.title = title
        self.subtitle = subtitle
        self.favicon = favicon
        self.visits = visits
        self.unread = unread
        self.sync = sync

    def update_from_feed_data(self, feed_data):
        self.unread = len([entry for entry in feed_data.entries if entry.read == False])

class FeedManager(gobject.GObject):
    __gsignals__ = {
        "feed-added": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (int, )),
        "label-created": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (int, )),
        }

    LOW_PRIORITY = 10
    DEFAULT_PRIORITY = 0
    HIGH_PRIORITY = -10

    def __init__(self, settings, conn_manager):
        super(FeedManager, self).__init__()

        self._settings = settings
        self._feed_data_dict = {}
        self._feeds_summary = {}
        self._feeds_summary_loaded = False
        self._conn_manager = conn_manager
        self._conn_manager.connect('connection-changed', self._on_connection_changed)
        self._google_reader_auth = None
        self._google_reader_auth_token = None
        self._google_reader_expires = None
        self._async_worker = None
        self._label_dict = {}
        self._label_dict_loaded = False

    def stop(self):
        # Cancel all pending operations
        if self._async_worker:
            self._async_worker.stop()

    def halt(self):
        # Wait till all the workers are done with their tasks
        if self._async_worker:
            self._async_worker.halt()

    def requireWorker(f):
        '''Function decorator to ensure that a valid async worker
        exists and is properly initialized in order to run the called
        method'''
        def wrapper(self, *args):
            # Check if we need to create the AsyncWorker. Use 2 worker threads
            if not self._async_worker:
                self._async_worker = AsyncWorker(2)

            # Call the async function
            f(self, *args)

        return wrapper

    def _on_connection_changed(self, conn_manager):
        pass

    @requireWorker
    def add_feed(self, url, sync, callback, data=None):
        # Create a new worker to update from network
        add_item = AsyncItem(self._add_feed_in_thread, (url,sync),
                             callback, (data,))
        self._async_worker.add_task((self.DEFAULT_PRIORITY, add_item))

    def _add_feed_in_thread(self, url, sync):

        parsed_url = urlparse.urlsplit(url)
        if parsed_url.scheme == '':
            url = 'http://' + url

        if not url.endswith('xml') and not url.endswith('opml'):
            url = getRSSLink(url)

        # Return if we cannot get the feed URL
        if url == '':
            raise IOError('Invalid URL')

        new_feed_data = ReSiStanceFeedDict(feedparser.parse(url))

        # 200 == OK, and 3xx are redirections.
        # On the other hand bozo==1 if there was some problem parsing the feed
        if 'status' not in new_feed_data or \
                (new_feed_data.status!=200 and new_feed_data.status/100 != 3) or \
                new_feed_data.bozo:
            del new_feed_data
            raise IOError('Resource is not a feed')

        # Add data to hashtable
        new_feed_id = get_feed_id(new_feed_data)
        self._feed_data_dict[new_feed_id] = new_feed_data
        self._feeds_summary[new_feed_id] = self._generate_summary(new_feed_data, sync)

        if 'link' in new_feed_data.feed:
            pixbuf = self._get_favicon_sync(new_feed_data.feed.link)
        else:
            pixbuf = self._get_favicon_sync(new_feed_data.href)

        self.emit('feed-added', new_feed_id)

        return pixbuf, new_feed_data

    @requireWorker
    def update_feed(self, feed_id, callback, data=None):
        # Create a new worker to update from network
        update_item = AsyncItem(self._update_feed_in_thread, (feed_id,),
                                callback, (data,))
        self._async_worker.add_task((self.DEFAULT_PRIORITY, update_item))

    def _update_feed_in_thread(self, feed_id):

        feed_data = self.get_feed_data(feed_id)
        if not feed_data:
            feed_data = self._load_in_thread(feed_id)
            if not feed_data:
                print 'ERROR: cannot load feed with ID: ' + string(feed_id)
                return

        try:
            updated_feed_data = ReSiStanceFeedDict(feedparser.parse(feed_data.href))
        except e:
            return

        # In case of network failure
        if updated_feed_data == None or updated_feed_data.entries == None or \
                len(updated_feed_data.entries) == 0:
            return

        updated_feed_date = updated_feed_data.feed.get('updated_parsed') or \
            updated_feed_data.entries[0].get('updated_parsed')
        feed_date = feed_data.feed.get('updated_parsed') or \
            feed_data.entries[0].get('updated_parsed')

        # Early return, nothing to do
        if updated_feed_date <= feed_date:
            return

        # Use the entry link for those entries with no id attribute
        old_entry_ids = [entry.id if 'id' in entry else entry.link \
                             for entry in feed_data.entries]
        updated_entry_ids = [entry.id if 'id' in entry else entry.link \
                                 for entry in updated_feed_data.entries]
        new_entries = [entry for entry in updated_feed_data.entries \
                           if (entry.id if 'id' in entry else entry.link) not in old_entry_ids]
        del old_entry_ids, updated_entry_ids

        # Autodownload enclosures
        if self._settings.auto_download:
            to_download_urls = [entry.enclosures[0].href for entry in new_entries if 'enclosures' in entry]
            to_download_paths = [self._settings.auto_download_folder+os.path.basename(urllib.url2pathname(url)) for url in to_download_urls]
            self._download_items_in_thread(to_download_urls, to_download_paths)

        if self._settings.delete_old:
            feed_data.update(updated_feed_data)
            feed_data.entries = new_entries
        else:
            # In order to keep read/unread status, just add
            # new_entries to the old ones while updating the rest
            # of the information
            old_entries = feed_data.entries
            feed_data.update(updated_feed_data)
            feed_data.entries = old_entries + new_entries

    @requireWorker
    def remove_feed(self, feed_id, callback=None, data=None):
        # Create a new worker to save the  file
        remove_item = AsyncItem(self._remove_feed_in_thread, (feed_id,),
                                callback, (data,))
        self._async_worker.add_task((self.LOW_PRIORITY, remove_item))

    def _remove_feed_in_thread(self, feed_id):

        try:
            os.remove(os.path.join(constants.RSS_DB_DIR, str(feed_id)))
        except:
            pass

        del self._feeds_summary[feed_id]
        if feed_id in self._feed_data_dict:
            del self._feed_data_dict[feed_id]

        return True

    @requireWorker
    def export_opml(self, file_path, callback, data=None):
        # Create a new worker to save the  file
        export_item = AsyncItem(self._export_opml_in_thread, (file_path,),
                                callback, (data,))
        self._async_worker.add_task((self.LOW_PRIORITY, export_item))

    def _export_opml_in_thread(self, file_path):
        # Create the minidom document
        opml_doc = Document()

        # Add tags and create the body of the document
        root = opml_doc.createElement('opml')
        root.setAttribute('version','1.0')
        root.appendChild(opml_doc.createElement('head'))
        body = opml_doc.createElement('body')

        for summary in self._feeds_summary.values():
            outline = opml_doc.createElement('outline')
            outline.setAttribute('title',summary.title)
            outline.setAttribute('text',summary.subtitle)
            outline.setAttribute('xmlUrl',summary.href)
            body.appendChild(outline)

        root.appendChild(body)
        opml_doc.appendChild(root)

        file_opml = open(file_path,"w")
        opml_doc.writexml(file_opml, "    ", "", "\n", "UTF-8")

    @requireWorker
    def import_opml(self, file_path, callback, data=None):
        # Create a new worker to read the file
        import_item = AsyncItem(self._import_opml_in_thread, (file_path,),
                                callback, (data,))
        self._async_worker.add_task((self.DEFAULT_PRIORITY, import_item))

    def _import_opml_in_thread(self, file_path):

        feed_url_list = [];

        if (not (os.path.exists(file_path) and os.path.isfile(file_path)) or
            (os.path.splitext(file_path)[1] != '.opml')):
            return feed_url_list

        doc=open(file_path,'r')
        opml_doc = minidom.parse(doc)
        opml_doc.getElementsByTagName('outline')

        feed_url_list = [node.attributes['xmlUrl'].value \
                             for node in opml_doc.getElementsByTagName('outline') \
                             if node.getAttribute('xmlUrl') != '']
        doc.close()

        return feed_url_list

    @requireWorker
    def find_feed(self, keywords, callback, data):
        # Create a new worker to search
        find_item = AsyncItem(self._find_feed_in_thread, (keywords,),
                              callback, (data,))
        self._async_worker.add_task((self.DEFAULT_PRIORITY, find_item))

    def _find_feed_in_thread(self, keywords):
        try:
            server = xmlrpclib.Server('http://www.syndic8.com/xmlrpc.php')
            feedids = server.syndic8.FindFeeds(keywords,'last_pubdate',25,0)
            infolist = server.syndic8.GetFeedInfo(feedids, ['imageurl','sitename','dataurl'])
        except:
            infolist = None
            print 'Error while accessing syndic8.com'

        return infolist

    def _authenticate_google_reader(self):
        ''' Returns a pair of authentication headers and the authentication token '''
        authenticated = True
        if self._google_reader_auth == None:
            try:
                params = urllib.urlencode({"service": "reader",
                                           "Email": self._settings.user,
                                           "Passwd": self._settings.password})
                url = constants.URL_LOGIN
                content = urllib2.urlopen(url,params).read()
            except:
                self._google_reader_auth = None
                self._google_reader_auth_token = None
                return None, None

            pos_begin = content.find('Auth=')
            pos_end = content.find('\n', pos_begin)
            self._google_reader_auth = content[pos_begin+len('Auth='):pos_end]

        auth_headers = { 'Authorization' : 'GoogleLogin auth=' + self._google_reader_auth }
        if self._google_reader_auth_token == None:
            try:
                # Get auth token
                token_request = urllib2.Request(constants.URL_TOKEN, headers = auth_headers)
                token_response = urllib2.urlopen(token_request)
                self._google_reader_auth_token = token_response.read()
            except:
                self._google_reader_auth = None
                self._google_reader_auth_token = None

        return auth_headers, self._google_reader_auth_token

    @requireWorker
    def mark_as_read_synchronize(self, feed_data_base, item_ref, read_item=True, callback=None, data=None):
        # Create a new thread to synchronize
        mark_read_item = AsyncItem(self._mark_as_read_synchronize_in_thread, (feed_data_base, item_ref, read_item),
                                   callback, (data,))
        self._async_worker.add_task((self.LOW_PRIORITY, mark_read_item))

    def _mark_as_read_synchronize_in_thread(self, feed_data_base, item_ref, read_item):
        synced = False
        read_mark = "a" if read_item else "r"

        auth_headers, auth_token = self._authenticate_google_reader()
        if not auth_token:
            return False

        try:
            # Get feed
            feed_request = constants.URL_FEED+feed_data_base
            req = urllib2.Request(feed_request, headers = auth_headers)
            feed_response = urllib2.urlopen(req)
        except:
            return False

        response_data=feed_response.read()

        while not synced:
            try:
                doc = minidom.parseString(response_data)
            except:
                return False
            #retrieve following 20 items
            nodes = doc.getElementsByTagName('gr:continuation')
            nodesEntries = doc.getElementsByTagName('entry')
            if nodes==[]:
                break
            try:
                for node in nodesEntries:
                    if node.getElementsByTagName('link')[0].attributes['href'].value == item_ref:
                        # Do the actual request for sync'ing the read status
                        itemId = node.getElementsByTagName('id')[0].firstChild.data
                        postparams = urllib.urlencode({read_mark: "user/-/state/com.google/read", "async" : "true", "ac" : "edit", "s" : "feed/"+feed_data_base, "i" : itemId, "T" : auth_token})
                        req = urllib2.Request(constants.URL_EDIT, postparams, auth_headers)
                        response = urllib2.urlopen(req)
                        synced = True
                        break
                if not synced:
                    # Get the next 20 items
                    continuation = nodes[0].firstChild.data
                    req = urllib2.Request(feed_request+'?c='+continuation, headers = auth_headers)
                    feed_response = urllib2.urlopen(req)
                    response_data = feed_response.read()
            except:
                return False

        # Call user callback
        return synced

    @requireWorker
    def download_item(self, url, file_path, callback, data=None):
        # Create a new worker to download from network
        download_item = AsyncItem(self._download_items_in_thread, ([url], [file_path]),
                                 callback, (data,))
        self._async_worker.add_task((self.LOW_PRIORITY, download_item))

    @requireWorker
    def download_all_items(self, urls, file_paths, callback, data=None):
        # Create a new worker to download from network
        download_item = AsyncItem(self._download_items_in_thread, (urls, file_paths),
                                 callback, (data,))
        self._async_worker.add_task((self.LOW_PRIORITY, download_item))

    def _download_items_in_thread(self, urls, file_paths):
        path_file = iter(file_paths)
        retvalues = []
        for url in urls:
            try:
                opener = urllib.FancyURLopener
                urlretrieve = opener().retrieve
                path = path_file.next()
                f = urlretrieve(url, path)
            except IOError :
                retvalues.append(False)
                break

        return False not in retvalues

    @requireWorker
    def sync_with_google_reader(self, callback, data=None):
        # Create a new worker to sync
        sync_item = AsyncItem(self._sync_with_google_reader_in_thread, (),
                              callback, (data,))
        self._async_worker.add_task((self.LOW_PRIORITY, sync_item))

    def _sync_with_google_reader_in_thread(self):

        auth_headers, auth_token = self._authenticate_google_reader()
        if not auth_token:
            return None

        urls = []
        label_feeds = {}
        try:
            # Get subscriptions
            subs_request = urllib2.Request(constants.URL_SUBSCRIPTION_LIST, headers = auth_headers)
            subs_response = urllib2.urlopen(subs_request)

            doc = minidom.parse(subs_response)
            # The xml looks like this
            # <object>
            #    <list name="subscriptions">
            #       <object><string name="id">feed/http://somefeed.com</string>....</object>
            #       <object><string name="id">feed/http://someotherfeed.com</string>....</object>
            #    </list>
            # <object>
            nodes = doc.documentElement.childNodes[0].childNodes
            for node in nodes:
                feed_url = node.firstChild.firstChild.data
                # Google allows also some other kind of
                # subscriptions. Skip them for the moment. I saw for
                # example feeds like
                # <string name="id">webfeed/someidreturnedbygoogle</string>
                # <string name="id">user/someuserid/label/SomeLabel</string>
                if feed_url.startswith('feed/'):
                    urls.append(feed_url[5:])

                for element in node.getElementsByTagName('list'):
                    if element.getAttribute('name') == 'categories':
                        for category in element.childNodes:
                            label_name = category.childNodes[1].firstChild.data
                            if label_name not in label_feeds:
                                label_feeds[label_name] = []
                            label_feeds[label_name].append(feed_url[5:])
        except:
            pass

        return urls, label_feeds

    @requireWorker
    def save(self, callback=None, data=None):
        # Create a new worker to store in disk
        save_item = AsyncItem(self.save_sync, (),
                              callback, (data,))
        self._async_worker.add_task((self.LOW_PRIORITY, save_item))

    def save_sync(self):

        # Save labels, summaries and feed data
        if self._label_dict_loaded:
            try:
                self._save_labels()
            except:
                print 'Unable to save label info'

        # Summaries may not have been loaded
        if self._feeds_summary_loaded:
            try:
                self._save_feeds_summary()
            except:
                print 'Unable to save feeds summary'

        for feed in self._feed_data_dict.values():
            file_name = os.path.join(constants.RSS_DB_DIR, str(get_feed_id(feed)))

            # TODO: migrate to "with" statement when available
            try:
                db_file = open(file_name, 'w')
                cPickle.dump(feed, db_file)
                db_file.close()
            except:
                print 'Could not save feed ' + feed.href
                pass

    @requireWorker
    def load(self, feed_id, callback, data=None):
        load_item = AsyncItem(self._load_in_thread, (feed_id,),
                              callback, (data,))
        self._async_worker.add_task((self.DEFAULT_PRIORITY, load_item))

    def _load_in_thread(self, feed_id):
        try:
            db_file = open(os.path.join(constants.RSS_DB_DIR, str(feed_id)), 'r')
            feed_data = cPickle.load(db_file)
            db_file.close()
        except IOError, e:
            print e
            # If the data does not exist reload it
            summary = self._feeds_summary[feed_id]
            feed_data = ReSiStanceFeedDict(feedparser.parse(summary.href))
        except Exception:
            return None

        self._feed_data_dict[feed_id] = feed_data
        return feed_data

    @requireWorker
    def get_favicon(self, url, callback, data=None):
        get_favicon_item = AsyncItem(self._get_favicon_sync,(url,),
                                     callback, (data,))
        self._async_worker.add_task((self.LOW_PRIORITY, get_favicon_item))

    def _get_favicon_sync(self, url):
        # Check that user dir exists
        user_path = os.path.join (constants.RSS_CONF_FOLDER, 'icons')

        if os.path.exists(user_path) == False:
            os.makedirs(user_path, 0700)

        file_name = os.path.join (user_path, str(hash(url)) + '.ico')
        if os.path.exists(file_name) == False:
            parsed_url = urlparse.urlsplit(url)
            try:
                localfile, headers = urllib.urlretrieve(parsed_url.scheme + '://' +
                                                        parsed_url.netloc + '/favicon.ico',
                                                        file_name)
            except:
                return gtk.gdk.pixbuf_new_from_file(constants.DEFAULT_FAVICON)

            # Try with a more general address. If we got a text/html then we most
            # likely requested an invalid address. It's better this than to check
            # for something like "image/" because I noticed that some servers return
            # icons with funny content types like text/plain. No comment
            if headers['Content-type'].startswith('text/html') == True:
                domains = parsed_url.netloc.rsplit('.',2)
                # Do not retry if domains == 2 because it will be
                # the same address we tried before
                if len(domains) > 2:
                    try:
                        localfile, headers = urllib.urlretrieve(parsed_url.scheme + '://' +
                                                                domains[-2] + '.' + domains[-1] +
                                                                '/favicon.ico', file_name)
                    except:
                        return gtk.gdk.pixbuf_new_from_file(constants.DEFAULT_FAVICON)

                if headers['Content-type'].startswith('image/') == False:
                    os.remove(localfile)
        try:
            pixbuf = gtk.gdk.pixbuf_new_from_file(file_name)
        except:
            return gtk.gdk.pixbuf_new_from_file(constants.DEFAULT_FAVICON)

        # Scale pixbuf. TODO: do not use hard-coded values
        if (pixbuf.get_width() != 32):
            pixbuf = pixbuf.scale_simple(32,32,gtk.gdk.INTERP_BILINEAR)
            pixbuf.save(file_name, 'png')

        return pixbuf

    @requireWorker
    def subscribe_feed_google(self, feed_url, is_add_subcription, callback=None, user_data=None):
        # Create a new thread to synchronize(subscribe and unsubscribe)
        subscribe_item = AsyncItem(self._subscribe_feed_google_in_thread, (feed_url,is_add_subcription),
                                   callback, (user_data,))
        self._async_worker.add_task((self.LOW_PRIORITY, subscribe_item))

    def _subscribe_feed_google_in_thread(self, feed_url, is_add_subcription):
        synced = False

        auth_headers, auth_token = self._authenticate_google_reader()
        if not auth_token:
            return synced

        action = 'subscribe' if is_add_subcription else 'unsubscribe'
        try:
            # Edit subscriptions
            postparams = urllib.urlencode({"s":"feed/"+feed_url, "ac": action, "T": auth_token})
            edit_request = urllib2.Request(constants.URL_SUBSCRIPTION_EDIT, postparams, auth_headers)
            urllib2.urlopen(edit_request)
        except:
            pass
        else:
            synced = True

        return synced

    @requireWorker
    def sync_google_reader_read_status(self, callback=None, user_data=None):
        ''' Synchronize the read/unread status of all (mandatory by
        Google Reader API) subscribed feeds with Google Reader '''
        sync_read_item = AsyncItem(self._sync_google_reader_read_status_in_thread, (),
                                   callback, (user_data,))
        self._async_worker.add_task((self.LOW_PRIORITY, sync_read_item))

    def _sync_google_reader_read_status_in_thread(self):
        auth_headers, auth_token = self._authenticate_google_reader()
        if not auth_token:
            return False

        # Do not update if we have updated just a while ago
        if time() < self._google_reader_expires:
            return True

        try:
            # Get items from feed excluding those with read status. It
            # indeed really sucks that we can only ask for the unread
            # items from *ALL* of our subscriptions
            unread_url = constants.URL_USER + constants.STATE_SUFFIX + 'reading-list' + '?' + 'xt=user/-/' + constants.STATE_SUFFIX + 'read' + '&n=1000'
            unread_request = urllib2.Request(unread_url, None, auth_headers)
            unread_response = urllib2.urlopen(unread_request)
            # Set 10 minutes expiration time. Google returns some
            # expiration time in unread_response.info()['expires'] but
            # it's just some seconds.
            self._google_reader_expires = time() + 10 * 60
            unread_data = unread_response.read()
        except:
            return False

        unread_dict = {}
        while True:
            doc = minidom.parseString(unread_data)
            nodesEntries = doc.getElementsByTagName('entry')

            for node in nodesEntries:
                entry_link = node.getElementsByTagName('link')[0].attributes['href'].value
                if not node.getElementsByTagName('source')[0].getAttribute('gr:stream-id').startswith('feed/'):
                    continue

                feed_source = node.getElementsByTagName('source')[0].getElementsByTagName('link')[0].attributes['href'].value
                if not feed_source in unread_dict:
                    unread_dict[feed_source] = [ entry_link ]
                else:
                    unread_dict[feed_source].append(entry_link)

            try:
                nodes = doc.getElementsByTagName('gr:continuation')
                if nodes==[]:
                    break
                unread_request = urllib2.Request(unread_url+'&c='+nodes[0].firstChild.data, None, auth_headers)
                unread_response = urllib2.urlopen(unread_request)
                unread_data = unread_response.read()
            except:
                return False

        # Load all data. FIXME: there should be a better way
        for summary in self._feeds_summary.values():
            if summary.feed_id not in self._feed_data_dict:
                feed_data = self._load_in_thread(summary.feed_id)

        for key in unread_dict.keys():
            # This could happen if there are unread items in feeds
            # that are not synchronized to ReSiStance. If that's the
            # case just ignore them
            feed_data_list = [feed_data for feed_data in self._feed_data_dict.values() \
                                  if feed_data.feed.link == key]
            if not feed_data_list:
                continue

            feed_data = feed_data_list[0]

            # Sync read/unread status. Ideally this should prioritize
            # the last action. Meanwhile prioritize the read status
            for entry in feed_data.entries:
                # Sometimes entry links include queries, discard them for the comparison
                if entry.link in unread_dict[key] or entry.link[:entry.link.find('?')] in unread_dict[key]:
                    # If read in ReSiStance update Google Reader (most likely read while offline)
                    if entry.read:
                        self._mark_as_read_synchronize_in_thread(feed_data.feed.link, entry.link, True)
                else:
                    # If read in Google Reader update ReSiStance (most likely read in Web)
                    if not entry.read:
                        entry.read = True

        # Mark all entries as read for feeds synced with Google Reader
        # with no unread items
        sync_feeds = []
        for summary in self._feeds_summary.values():
            if summary.sync:
                feed_data = self._feed_data_dict[summary.feed_id]
                if feed_data.feed.link not in unread_dict:
                    sync_feeds.append(feed_data)

        for feed_data in sync_feeds:
            for entry in feed_data.entries:
                if not entry.read:
                    entry.read = True

        return True

    def get_feed_summary(self, feed_id):
        return self._feeds_summary[feed_id]

    def get_feed_summaries(self):
        return self._feeds_summary.values()

    def get_feed_data(self, feed_id):
        try:
            return self._feed_data_dict[feed_id]
        except KeyError:
            return None

    @requireWorker
    def load_feeds_summary(self, callback, data=None):
        load_item = AsyncItem(self._load_feeds_summary_in_thread, (),
                              callback, (data,))
        self._async_worker.add_task((self.HIGH_PRIORITY, load_item))

    def _generate_summary(self, feed_data, sync, visits=0):
        feed_id = get_feed_id(feed_data)
        unread_count = len([entry for entry in feed_data.entries if entry.read == False])
        return ReSiStanceFeedSummary(feed_id, feed_data.href, feed_data.feed.title,
                                     get_feed_subtitle(feed_data), get_feed_icon_uri(feed_data),
                                     visits, unread_count, sync)

    def _create_summary_from_old_storage(self):
        db_file = open(constants.OLD_RSS_DB_FILE, 'r')
        feed_data_list = cPickle.load(db_file)
        db_file.close()

        for feed_data in feed_data_list:
            feed_id = get_feed_id(feed_data)
            self._feeds_summary[feed_id] = self._generate_summary(feed_data, feed_data.sync, feed_data.visits)
            self._feed_data_dict[feed_id] = ReSiStanceFeedDict(feed_data)

        if self._feeds_summary:
            self._feeds_summary_loaded = True

    def _load_feeds_summary_in_thread(self):
        try:
            db_file = open(constants.RSS_DB_SUMMARY_FILE, 'r')
            self._feeds_summary = cPickle.load(db_file)
            self._feeds_summary_loaded = True
            db_file.close()
        except IOError, e:
            # IOError 2 means "file not found", so we're moving from
            # an old version of ReSiStance that does not use summaries.
            if e.errno != 2:
                print e
                return None

            # There is no summary nor old storage, this means that
            # this is the first execution. self._feeds_summary_loaded
            # must be True to allow new feeds to be stored
            self._feeds_summary_loaded = True
            if not os.path.isfile(constants.OLD_RSS_DB_FILE):
                return None

            self._create_summary_from_old_storage()

            # No need to keep the old storage. Try to save summaries
            # and feed data in their new storages and if everything
            # goes fine then remove the old db file
            self.save_sync()
            os.unlink(constants.OLD_RSS_DB_FILE)

        except Exception, e:
            print e
            return None

        return self._feeds_summary.values()

    def _save_feeds_summary(self):
        # Update summaries, some data might have changed
        for feed_data in self._feed_data_dict.values():
            summary_list = [summary for summary in self._feeds_summary.values() if summary.feed_id == get_feed_id(feed_data)]
            if summary_list:
                summary_list[0].update_from_feed_data(feed_data)

        db_file = open(constants.RSS_DB_SUMMARY_FILE, 'w')
        cPickle.dump(self._feeds_summary, db_file)
        db_file.close()

    # LABELS
    def get_label_list(self):
        return zip(self._label_dict.keys(), [label_data[0] for label_data in self._label_dict.values()])

    def get_label_name(self, label_id):
        return self._label_dict[label_id][0]

    def get_feeds_for_label(self, label_id):
        return self._label_dict[label_id][1]

    def feed_has_label(self, feed_id, label_id):
        if label_id == constants.ALL_LABEL_ID:
            return True
        return feed_id in self._label_dict[label_id][1]

    def remove_label(self, label_id):
        del self._label_dict[label_id]

    def create_label(self, label_name):
        label_id = hash(label_name)
        if label_id in self._label_dict:
            return 0

        self._label_dict[label_id] = [label_name, []]
        self.emit('label-created', label_id)
        return label_id

    def add_feeds_to_label(self, feed_ids, label_id):
        self._label_dict[label_id][1] += feed_ids

    def remove_feeds_from_label(self, feed_ids, label_id):
        for feed_id in feed_ids:
            self._label_dict[label_id][1].remove(feed_id)

    @requireWorker
    def load_labels(self, callback, data=None):
        load_item = AsyncItem(self._load_labels_in_thread, (),
                              callback, (data,))
        self._async_worker.add_task((self.HIGH_PRIORITY, load_item))

    def _load_labels_in_thread(self):
        try:
            db_file = open(constants.RSS_LABEL_DB_FILE, 'r')
            self._label_dict = cPickle.load(db_file)
            db_file.close()
            loaded = True
        except IOError:
            print 'No labels file or unable to read it'
            loaded = False
        finally:
            self._label_dict_loaded = True

        return loaded

    def _save_labels(self):
        db_file = open(constants.RSS_LABEL_DB_FILE, 'w')
        cPickle.dump(self._label_dict, db_file)
        db_file.close()

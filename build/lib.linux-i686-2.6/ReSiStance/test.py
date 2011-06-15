#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from feedmanager import FeedManager
import constants
from settings import Settings
from connectionmanager_gnome import ConnectionManager
import os
import urllib
import urllib2

conn_manager = ConnectionManager()
settings = Settings()
manager = FeedManager(settings, conn_manager)

class ExportTest(unittest.TestCase):
    def setUp(self): 
        url = 'http://www.lavozdegalicia.es/coruna/index.xml'
        sync = False
        pixbuf, new_feed_data = manager._add_feed_in_thread(url, sync)
        self.file_path = os.path.join(constants.HOME_PATH, 'export_import_test.opml')
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

    def test(self):
        manager._export_opml_in_thread(self.file_path)
        self.assertTrue(os.path.exists(self.file_path))

class ExportEmptyTest(unittest.TestCase):
    def setUp(self): 
        self.feeds_summary = manager._feeds_summary
        manager._feeds_summary = {}
        self.file_path = os.path.join(constants.HOME_PATH, 'export_import_empty_test.opml')
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

    def test(self):
        manager._export_opml_in_thread(self.file_path)
        self.assertTrue(os.path.exists(self.file_path))

    def tearDown(self):
        manager._feeds_summary = self.feeds_summary
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

class ExportBadFileTest(unittest.TestCase):
    def setUp(self): 
        self.file_path = os.path.join(constants.HOME_PATH, 'not_exist_text')
        self.file_path = os.path.join(self.file_path, 'export_import_not_exist_test.opml')
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

    def test(self):
        self.assertRaises(IOError, manager._export_opml_in_thread, self.file_path)

class ImportTest(unittest.TestCase):
    def setUp(self): 
        self.file_path = os.path.join(constants.HOME_PATH, 'export_import_test.opml')
        if os.path.exists(self.file_path):
            os.remove(self.file_path)
        manager._export_opml_in_thread(self.file_path)

    def test(self):
        url_added = 'http://www.lavozdegalicia.es/coruna/index.xml'
        feed_url_list = manager._import_opml_in_thread(self.file_path)
        self.assertTrue(url_added in feed_url_list)

    def tearDown(self):
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

class ImportEmptyFileTest(unittest.TestCase):
    def setUp(self): 
        self.file_path = os.path.join(constants.HOME_PATH, 'export_import_empty_test.opml')
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

    def test(self):
        feed_url_list = manager._import_opml_in_thread(self.file_path)
        self.assertTrue(feed_url_list == [])

    def tearDown(self):
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

class ImportBadFileTest(unittest.TestCase):
    def setUp(self): 
        self.file_path = os.path.join(constants.HOME_PATH, 'not_exist_test')
        self.file_path = os.path.join(self.file_path, 'export_import_not_exist_test.opml')
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

    def test(self):
        feed_url_list = manager._import_opml_in_thread(self.file_path)
        self.assertTrue(feed_url_list == [])

class DownloadPodcastTest(unittest.TestCase):
    def setUp(self): 
        url = 'http://www.cadenaser.com/rssaudio/hablar-por-hablar.html'
        sync = False
        pixbuf, new_feed_data = manager._add_feed_in_thread(url, sync)

        folder = os.path.join(constants.HOME_PATH, 'test_download')
        if os.path.exists(folder):
            os.remove(folder)

        self.urls = []
        self.paths_files = []
        for entry in new_feed_data.entries:
            try:
                url = entry['enclosures'][0]['href']
                self.urls.append(url)
                self.paths_files.append(folder + os.path.basename(urllib.url2pathname(url)))
            except:
                pass
            break 

    def test(self):
        self.assertTrue(manager._download_items_in_thread(self.urls, self.paths_files))

class DownloadPodcastNotContentTest(unittest.TestCase):
    def setUp(self): 
        url = 'http://www.lavozdegalicia.es/coruna/index.xml'
        sync = False
        pixbuf, new_feed_data = manager._add_feed_in_thread(url, sync)

        folder = os.path.join(constants.HOME_PATH, 'test_download')
        if os.path.exists(folder):
            os.remove(folder)

        self.urls = []
        self.paths_files = []
        for entry in new_feed_data.entries:
            try:
                url = entry['enclosures'][0]['href']
                self.urls.append(url)
                self.paths_files.append(folder + os.path.basename(urllib.url2pathname(url)))
            except:
                pass
            break 

    def test(self):
        self.assertTrue(manager._download_items_in_thread(self.urls, self.paths_files))

class FindFeedsTest(unittest.TestCase):
    def test(self):
        """ With keywords """
        keywords = 'blue'
        self.assertTrue(manager._find_feed_in_thread(keywords) != None)

class FindFeedsEmptyKeywordsTest(unittest.TestCase):
    def test(self):
        """ Without keywords """
        keywords = ''
        self.assertTrue(manager._find_feed_in_thread(keywords) != None)

class CreateLabelTest(unittest.TestCase):
    def test(self):
        label_name = 'label_1'
        self.label_id = hash(label_name)
        self.assertTrue(manager.create_label(label_name) == self.label_id)

    def tearDown(self):
        manager.remove_label(self.label_id)

class CreateNoNameLabelTest(unittest.TestCase):
    def test(self):
        label_name = ''
        self.label_id = hash(label_name)
        self.assertTrue(manager.create_label(label_name) == self.label_id)

    def tearDown(self):
        manager.remove_label(self.label_id)

class CreateLabelRepeatTest(unittest.TestCase):
    def setUp(self): 
        label_name = 'label_2'
        self.label_id = manager.create_label(label_name)

    def test(self):
        label_name = 'label_2'
        self.assertTrue(manager.create_label(label_name) == 0)

    def tearDown(self):
        manager.remove_label(self.label_id)

class RemoveLabelTest(unittest.TestCase):
    def setUp(self): 
        label_name = 'label_3'
        self.label_id = manager.create_label(label_name)

    def test(self):
        manager.remove_label(self.label_id)
        self.assertTrue(self.label_id not in manager._label_dict)

class RemoveLabelNotExistTest(unittest.TestCase):
    def setUp(self): 
        label_name = 'label_3'
        self.label_id = manager.create_label(label_name)
        manager.remove_label(self.label_id)

    def test(self):
        self.assertRaises(KeyError, manager.remove_label, self.label_id)

class AddFeedToLabelTest(unittest.TestCase):
    def setUp(self):
        url = 'http://www.lavozdegalicia.es/coruna/index.xml'
        sync = False
        pixbuf, feed_data = manager._add_feed_in_thread(url, sync)
        self.feed_id = hash(feed_data.href)
        self.feed_ids = [self.feed_id]
        label_name = 'label_4'
        self.label_id = manager.create_label(label_name)

    def test(self):
        manager.add_feeds_to_label(self.feed_ids, self.label_id)
        self.assertTrue(self.feed_id in manager._label_dict[self.label_id][1])

    def tearDown(self):
        manager._remove_feed_in_thread(self.feed_id)
        manager.remove_label(self.label_id)

class AddFeedToLabelBadIdTest(unittest.TestCase):
    def setUp(self):
        url = 'http://www.lavozdegalicia.es/coruna/index.xml'
        sync = False
        pixbuf, feed_data = manager._add_feed_in_thread(url, sync)
        self.feed_id = hash(feed_data.href)
        self.feed_ids = [self.feed_id]
        label_name = 'label_4'
        self.label_id = manager.create_label(label_name)
        manager.remove_label(self.label_id)

    def test(self):
        self.assertRaises(KeyError, manager.add_feeds_to_label, self.feed_ids, self.label_id)

    def tearDown(self):
        manager._remove_feed_in_thread(self.feed_id)

class RemoveFeedFromLabelTest(unittest.TestCase):
    def setUp(self):
        url = 'http://www.lavozdegalicia.es/coruna/index.xml'
        sync = False
        pixbuf, feed_data = manager._add_feed_in_thread(url, sync)
        self.feed_id = hash(feed_data.href)
        self.feed_ids = [self.feed_id]
        label_name = 'label_5'
        self.label_id = manager.create_label(label_name)
        manager.add_feeds_to_label(self.feed_ids, self.label_id)    

    def test(self):
        manager.remove_feeds_from_label(self.feed_ids, self.label_id)  
        self.assertTrue(self.feed_id not in manager._label_dict[self.label_id][1])

class RemoveFeedFromLabelBadFeedTest(unittest.TestCase):
    def setUp(self):
        url = 'http://www.lavozdegalicia.es/coruna/index.xml'
        sync = False
        pixbuf, feed_data = manager._add_feed_in_thread(url, sync)
        self.feed_id = hash(feed_data.href)
        self.feed_ids = [self.feed_id]
        label_name = 'label_6'
        self.label_id = manager.create_label(label_name)

    def test(self):
        self.assertRaises(ValueError, manager.remove_feeds_from_label, self.feed_ids, self.label_id)

if __name__ == "__main__":
    unittest.main()

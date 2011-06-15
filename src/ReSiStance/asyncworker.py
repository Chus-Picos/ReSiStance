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

from Queue import Queue
from bisect import bisect_left
from threading import Thread, Lock
import gobject
import logging
import time
logging.basicConfig(level=logging.DEBUG)

# AsyncItem object was borrowed from Joaquim Rocha's
# <jrocha@igalia.com> SeriesFinale. You can get SeriesFinale from
# http://gitorious.org/seriesfinale. The AsyncItem code is almost
# identical except one minor change in the order in which arguments
# are returned

# Both AsyncWorker and PriorityQueue are different in implementation
# and behaviour.
class TaskCanceled(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class AsyncItem(object):

    def __init__(self, target_method, target_method_args, finish_callback = None, finish_callback_args = ()):
        self.target_method = target_method
        self.target_method_args = target_method_args
        self.finish_callback = finish_callback
        self.finish_callback_args = finish_callback_args
        self.canceled = False

    def run(self):
        results = error = None

        # Contrary to SeriesFinale we do invoke callback even if the
        # request was canceled
        if not self.canceled:
            try:
                results = self.target_method(*self.target_method_args)
            except Exception, exception:
                logging.debug(str(exception))
                error = exception
        else:
            error = TaskCanceled('Canceled task:' + str(self.target_method))

        if not self.finish_callback:
            return

        # In SeriesFinale this is a += but we prefer the
        # finish_callback_args at the end
        self.finish_callback_args = (results,) + self.finish_callback_args
        self.finish_callback_args += (error,)
        gobject.idle_add(self.finish_callback, *self.finish_callback_args)

    def cancel(self):
        self.canceled = True

class AsyncWorker(object):

    def __init__(self, num_workers):
        self._num_workers = num_workers
        self._queue = PriorityQueue()
        self._stopped = False

        # Create the pool of workers
        self._workers_pool = []
        for i in range(self._num_workers):
            worker = Thread(target=self._process_queue, args=(i,))
            worker.setDaemon(True)
            worker.start()
            self._workers_pool.append(worker)

    def _process_queue(self, worker_id):
        """This is the worker thread function.
        It processes items in the queue one after
        another.  These daemon threads go into an
        infinite loop, and only exit when
        the main thread ends.
        """
        while True:
            print '%s: Waiting for the next item' % worker_id
            async_item = self._queue.get()
            if self._stopped:
                async_item.canceled = True
            state = 'Cancelling' if async_item.canceled else 'Running'
            print '\t%s: %s %s' % (worker_id, state, str(async_item.target_method).split()[2])
            try:
                async_item.run()
            except Exception, exception:
                logging.debug(str(exception))

            # tell queue about task done
            self._queue.task_done()

            # Allow other threads to enter CPU. This does not really
            # work really good due to the Globar Interpreter Lock, but
            # what else can we do?
            time.sleep(0)

    def add_task(self, task):
        self._queue.put(task)

    def stop(self):
        self._stopped = True
        self._queue.stop()

    def halt(self):
        # Wait until all threads are done
        self._queue.join()

# PriorityQueue was added to python in 2.6. We need to implement it as
# Maemo5 ships 2.5. Got this nice implementation from
# http://code.activestate.com/recipes/87369-priority-queue/
class PriorityQueue(Queue):

    def _init(self, maxsize):
        self.maxsize = maxsize
        # Python 2.5 uses collections.deque, but we can't because
        # we need insert(pos, item) for our priority stuff
        self.queue = []
        self._cancel_lock = None

    def put(self, item, block=True, timeout=None):
        """Puts an item onto the queue with a numeric priority (default is zero).

        Note that we are "shadowing" the original Queue.Queue put() method here.
        """
        Queue.put(self, item, block, timeout)

    def _put(self, item):
        """Override of the Queue._put to support prioritisation."""
        priority, data = item

        # Using a tuple (priority+1,) finds us the correct insertion
        # position to maintain the existing ordering.
        self.queue.insert(bisect_left(self.queue, (priority+1,)), item)

    def _get(self):
        if self._cancel_lock:
            self._cancel_lock.acquire()

        """Override of Queue._get().  Strips the priority."""
        item = self.queue.pop(0)[1]

        if self._cancel_lock:
            self._cancel_lock.release()

        return item

    def stop(self):
        if not self._cancel_lock:
            self._cancel_lock = Lock()

        # Acquire cancel lock in order to properly block access to queue items
        self._cancel_lock.acquire()
        for (priority, item) in self.queue:
            item.cancel()
        self._cancel_lock.release()

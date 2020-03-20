'''
Listener for MusicCast events over the network.

.. reviewed 13 Oct 2018
   TODO: document
'''

import socket
import select
import json
import threading
import Queue
import time
import logging

import musiccast2mqtt as mcc

LOG = logging.getLogger(__name__)

class musiccastListener(object):
    ''' docstring'''

    def __init__(self, port=mcc.DEFAULT_LISTEN_PORT):
        if port is None or port < 0 or port > 65535:
            self._port = mcc.DEFAULT_LISTEN_PORT
        else:
            self._port = port
        self._event_queue = Queue.Queue(maxsize=mcc.MAX_QUEUE_SIZE)
        self._loop_stop_event = threading.Event()
        self._socket = None
        self._create_socket()
        return

    def get_musiccast_events_queue(self):
        ''' Returns the event queue.'''
        return self._event_queue

    def loop_start(self):
        ''' Starts the loop in a separate thread.'''
        loop_thread = threading.Thread(target=self._loop, name='Event Listener')
        self._loop_stop_event.clear()
        loop_thread.start()
        LOG.debug('Listener loop started.')
        return

    def loop_stop(self):
        ''' Stops the loop via the appropriate events.'''
        self._loop_stop_event.set()
        return

    def _loop(self):
        ''' The actual loop.
        It does a full search then waits either for a 'refresh' event or for the full
        cycle, then tests the 'loop_stop' event if to exit or loop again.'''
        while True:
            if self._socket is None:
                self._create_socket()
            event = self._listen()
            if event is not None:
                self._event_queue.put(event)
            if self._loop_stop_event.is_set(): break
        LOG.debug('Listener loop ended.')
        return

    def _create_socket(self):
        ''' Creates the socket.'''
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #, socket.IPPROTO_UDP)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Re-use socket.
        self._socket.setblocking(0)
        self._socket.bind(('', self._port))
        return

    def _release_socket(self):
        ''' Releases the socket in case of error. '''
        self._socket.close()
        self._socket = None
        return

    def _listen(self):
        ''' Listens for new events.

        The 'body' of the event (see below) is in the form:
            '{"main":{"power":"on"},"device_id":"00A0DED57E83"}'
        or:
            '{"main":{"volume":88},"zone2":{"volume":0}, "device_id":"00A0DED3FD57"}'

        The 'address' is a pair (host, port) as in ('192.168.1.44', 38507).
        '''
        if self._socket is None: # wait a bit? TODO: decide what can be done better here.
            time.sleep(mcc.SOCKET_ERROR_SLEEP)
            return None
        try:
            trigger = select.select([self._socket], [], [], mcc.LISTEN_TIMEOUT)
        except select.error as err: # log only for now. TODO: restart socket?
            LOG.debug(''.join(('Socket error: <', err[1], '>. Ignore.')))
            return None
        if trigger[0]: # there is an event waiting in the socket
            body, address = self._socket.recvfrom(mcc.SOCKET_BUFFER_SIZE)
            LOG.debug(''.join(('Event received: <', str(body), '> from <', str(address), '>.')))
            try: event = json.loads(body)
            except ValueError as err: # log only for now
                LOG.debug(''.join(('Error while reading JSON: ', str(err))))
                return None
            return event
        else:
            return None

if __name__ == '__main__':
    LISTENER = musiccastListener()
    QUEUE = LISTENER.get_musiccast_events_queue()
    LISTENER.loop_start()
    BLOCK = threading.Event()
    BLOCK.wait()

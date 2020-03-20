''' Discovery module for MusicCast devices.

Based on the UPnP protocol v2.0:
    http://www.upnp.org/specs/arch/UPnP-arch-DeviceArchitecture-v2.0.pdf

This module searches for MusicCast devices in the network by using the UPnP protocol.
A complete search process is made of 2 steps, each launched in a separate thread:

  1) a discovery step where a broadcast is sent over the network and simple responses are expected
     from discovered devices; those responses are put in a queue to be picked up by the
     description thread;

  2) a description step where each discovered device retrieved from the queue is polled to get more
     information about it; each discovered new MusicCast device is written to a dictionary to be
     retrieved by any other thread that might be interested.

The methods ``loop_start`` and ``loop_stop`` are used to start or stop the search process.
The method ``retrieve_new_devices`` can be called at any time to retrieve a dictionary with all the
devices that have been discovered since the last call.
Use the method ``get_new_device_event`` to get an event which will be set each time a new device is
discovered.  Use it or not.
The method ``update_online_devices`` allows to tell this module what are the devices already online
and avoids going through the description process for these devices. It is a nice to have but it
does not need to be used.  If unused, the new devices retrieved with the ``retrieve_new_devices``
call might not be new, but then the calling thread must know that it needs to check that before
doing anything else with those *not really new* devices.

New devices do not go in any queue but in a dictionary, so even if the ``retrieve_new_devices``
method is not called for a while, it does not matter.

.. Reviewed 9 November 2018
'''

import socket
import httplib
from urlparse import urlparse
import xml.etree.ElementTree as ET
import logging

import threading
import Queue

import musiccast2mqtt as mcc

LOG = logging.getLogger(__name__)

_CATCH_ERRORS = (AttributeError, IndexError, KeyError, TypeError, ValueError)

_UPNP_BROADCAST = ('239.255.255.250', 1900) # UPnP protocol broadcast address
_MSEARCH_MSG = '\r\n'.join(['M-SEARCH * HTTP/1.1',
                            'HOST:{ip}:{port}',
                            'MAN:"ssdp:discover"',
                            'ST:{st}',
                            'MX:{mx}',
                            '', ''])
_MEDIARENDERER_TARGET = 'urn:schemas-upnp-org:device:MediaRenderer:1'
_YAMAHA_IDS = ('<manufacturer>Yamaha Corporation</manufacturer>',
               '<yamaha:X_device>',
               '<yamaha:X_yxcControlURL>/YamahaExtendedControl/v1/</yamaha:X_yxcControlURL>'
              )

# XML Helpers: The dictionaries _XML_TAGS, _XML_NAMESPACES and the function _xml_tag go 'together'.
_XML_TAGS = {'friendlyName': ('upnp:device', 'upnp:friendlyName'),
             'serialNumber': ('upnp:device', 'upnp:serialNumber'),
             'UDN': ('upnp:device', 'upnp:UDN'),
             'modelDescription': ('upnp:device', 'upnp:modelDescription'), # optional
             'modelName': ('upnp:device', 'upnp:modelName'), # optional
             'modelURL': ('upnp:device', 'upnp:modelURL'), # optional
             'yamaha_URLBase': ('yamaha:X_device', 'yamaha:X_URLBase')
            }
''' Dictionary of relevant tags inside the XML dataframe.
The keys of the dictionary are arbitrary names for the field being referred to; usually it is
the same as the tag name of the XML element being sought, but it does not have to be.
The values are lists of tag names that represent the path down the XML tree to reach the
element requested.'''
_XML_NAMESPACES = {'upnp': 'urn:schemas-upnp-org:device-1-0',
                   'yamaha': 'urn:schemas-yamaha-com:device-1-0',
                   'dlna': 'urn:schemas-dlna-org:device-1-0'
                  }
''' This dictionary provides the full name-spaces needed to properly parse the tree with the
_XML_TAGS dictionary.  It simply avoids to write down the long name-spaces for every tag in the
_XML_TAGS dictionary.'''

def _xml_tag(root, key):
    ''' Retrieves the content of the tag based on the key in the dictionary _XML_TAGS.'''
    elem = root
    for child_tag in _XML_TAGS[key]:
        elem = elem.find(child_tag, _XML_NAMESPACES)
    return elem

#==OBSOLETE=========================================================================================
# XML_REPLACEMENT = '''<root xmlns="urn:schemas-upnp-org:device-1-0"\
#  xmlns:yamaha="urn:schemas-yamaha-com:device-1-0"\
#  xmlns:dlna="urn:schemas-dlna-org:device-1-0"'''
#===================================================================================================

_RESPONSE_HEADERS = {'location': 'LOCATION', # URL to the UPnP description of the root device
                     'cache': 'CACHE-CONTROL',
                     'target': 'ST',
                     'usn': 'USN' # Unique Service Name. Format "uuid:<device-UUID>[::<other stuff>]
                    }
''' Dictionary that maps the headers of the search response with the attributes of the class.'''

class searchResponse(object):
    ''' Represents a response to the SSDP search.
    The attributes of this class are listed as values in the _RESPONSE_HEADERS dictionary,
    except for sender which is retrieved from the second field in the response parameter.

    Args:
        response: the data as returned by the call to socket.recvfrom

    '''
    def __init__(self, response):
        # create empty attributes
        for k in _RESPONSE_HEADERS: setattr(self, k, '')
        try:
            self.sender = response[1] # address of the socket sending the data
            lines = response[0].split('\r\n')
            self.status = lines.pop(0) # remove the status on the first line
            for line in lines:
                tokens = line.split(':', 1)
                for k, values in _RESPONSE_HEADERS.iteritems():
                    if tokens[0].upper() == values:
                        setattr(self, k, tokens[1].strip())
            # retrieve the device_id; it is the last 12 digits of the first part of the USN.
            self.device_id = self.usn.strip().split('::', 1)[0][-12:].upper()
        except _CATCH_ERRORS:
            raise TypeError

class musiccastDiscovery(object):
    ''' Manages the periodic discovery process for new devices online.

    The discovery process for MusicCast devices (based on Yamaha documentation):
    - launches a SSDP search for Media Renderers;
    - Read the responses as they arrive;
    - Put all valid devices on the outgoing queue.

    Args:
        device_queue (:class:Queue): to put the new devices
        cycle (int): maximum time between 2 searches, in seconds. Loops only once if it is <= 0.
        refresh_event (Event): triggers a new search before waiting for the end of cycle.

    '''
    def __init__(self, device_factory_queue, refresh_event=None, cycle=mcc.DISCOVERY_CYCLE):
        self._device_factory_queue = device_factory_queue
        self._cycle = cycle
        self._ssdp_responses = Queue.Queue(maxsize=10) # 10 is arbitrary and should be ok
        self._online_devices_shared = {} # dictionary {device_id: ip_address} of online devices
        self._online_devices_lock = threading.Lock()

        # use refresh_event to trigger a new search, or create it for the delay, if undefined
        if refresh_event is None: self._refresh_event = threading.Event()
        else: self._refresh_event = refresh_event
        self._loop_stop_event = threading.Event()
        return

    def loop_start(self):
        ''' Starts the loop in a separate thread.'''
        loop_thread = threading.Thread(target=self._loop, name='UPnP Thread')
        self._refresh_event.clear()
        self._loop_stop_event.clear()
        loop_thread.start()
        LOG.debug('UPnP search started.')
        return

    def loop_stop(self):
        ''' Stops the loop via the appropriate events.'''
        self._loop_stop_event.set()
        self._refresh_event.set() # trigger a refresh in order not to wait for the end of the delay
        return

    def _loop(self):
        ''' The actual loop.
        It does a full search then waits either for a 'refresh' event or for the full
        cycle, then tests the 'loop_stop' event if to exit or loop again.'''
        while True:
            self._search()
            if self._cycle <= 0: break # run only once if cycle value is <= 0. TODO: optimise
            self._refresh_event.wait(self._cycle)
            self._refresh_event.clear() # in any case, either time-out or event set.
            if self._loop_stop_event.is_set(): break
        LOG.debug('UPnP search stopped.')
        return

    def _search(self):
        ''' Full search process to discover online devices.

        Launches two threads and blocks until they are both finished.
        '''
        discovery_thread = threading.Thread(target=self._discovery,
                                            name='Discovery',
                                            kwargs={'target':_MEDIARENDERER_TARGET, 'mx':3})
        description_thread = threading.Thread(target=self._description, name='Description')
        description_thread.start() # order is important obviously
        discovery_thread.start()
        LOG.debug('UPnP search threads started.')
        discovery_thread.join()
        description_thread.join()
        LOG.debug('UPnP search threads ended.')
        return

    def _discovery(self, target, mx=3):
        '''
        Launches the discovery process.

        Sends a search request (SSDP search) then listens to the socket for responses.
        Terminates after the socket timeout.
        '''
        LOG.debug('_discovery stage started.')
        if mx < 1 or mx > 5: mx = 3
        timeout = mx * 2 # arbitrary; probably could be "= mx", or "= mx+1"
        # create socket.
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Re-use socket
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 5) # Time To Live, was at 2
        sock.settimeout(timeout)
        # send search message
        msg = _MSEARCH_MSG.format(ip=_UPNP_BROADCAST[0], port=_UPNP_BROADCAST[1], st=target, mx=mx)
        sock.sendto(msg, _UPNP_BROADCAST)
        # listen to responses until timeout is reached
        try:
            while True:
                data = sock.recvfrom(mcc.SOCKET_BUFFER_SIZE)
                self._ssdp_responses.put(data)
        except socket.timeout:
            pass
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()
        # send final event
        self._ssdp_responses.put(mcc.END_QUEUE)
        LOG.debug('_discovery stage ended.')
        return

    def _description(self):
        ''' Retrieves the description of any device found from the search.

        Reads the queue for new found devices, retrieves the address to call for
        the description, makes the 'GET' request accordingly, filters to keep only
        the right devices, parses the XML data and puts a new device object on the
        new device queue.
        '''
        LOG.debug('_description stage started.')
        while True:
            # wait for SSDP responses to show up in the queue
            data = self._ssdp_responses.get(block=True, timeout=None) # blocking call
            self._ssdp_responses.task_done()
            if data == mcc.END_QUEUE: break # the discovery thread is done, so are we.
            # parse the data in a searchResponse object
            try:
                resp = searchResponse(data)
            except TypeError:
                continue

            # check the device_id from the USN against the already online devices. REMOVED FOR NOW.
            #=======================================================================================
            # device_exists = False
            # with self._online_devices_lock:
            #     if resp.device_id in self._online_devices_shared: # TODO: check also the IP address?
            #         device_exists = True
            # if device_exists:
            #         continue
            #=======================================================================================

            # use the location address to request the description of the device
            try:
                url = urlparse(resp.location)
            except _CATCH_ERRORS:
                continue
            try:
                conn = httplib.HTTPConnection(url.netloc, timeout=2)
                conn.request(method='GET', url=url.path)
                httpresponse = conn.getresponse()
                data = httpresponse.read()
            except httplib.HTTPException:
                continue
            # look for specific strings to identify Yamaha devices; discard if not present
            if any(((data.find(str_id) < 0) for str_id in _YAMAHA_IDS)):
                continue

            #== the following is only needed if the XLM data is missing the name-spaces definitions
            #=======================================================================================
            # if data.find('xmlns') >= 0: # there are name-spaces definition in the XML file
            #     newdata = data # hopefully this is a valid XML
            # else: # we need to add the name-spaces to the data
            #     newdata = data.replace('<root', XML_REPLACEMENT, 1)
            # data = newdata
            #=======================================================================================

            # parse the XML data to retrieve the right attributes
            try:
                root = ET.fromstring(data)
            except ET.ParseError:
                continue
            # retrieve relevant attributes from parsed XML data
            # retrieve the device_id.  It is the last 12 digits of the UDN
            device_id = _xml_tag(root, 'UDN').text.strip()[-12:].upper()
            #serial_num = _xml_tag(root, 'serialNumber').text.strip().upper()
            url = urlparse(_xml_tag(root, 'yamaha_URLBase').text.strip())
            LOG.debug(''.join(('\tDevice found: id - ', device_id, '; host - ', url.hostname)))
            #print '\tDevice: id - ', device_id, '; ip - ', ip_address
            # update the dictionary of new devices
            self._device_factory_queue.put(mcc.DeviceHandle(mcc.DeviceHandle.CREATE,
                                                            device_id=device_id,
                                                            host=url.hostname,
                                                            api_port=url.port))
        LOG.debug('_description stage ended.')
        return

if __name__ == '__main__':
    device_q = Queue.Queue()
    mcDiscovery = musiccastDiscovery(device_factory_queue=device_q, cycle=30)
    mcDiscovery.loop_start() # non-blocking call
    while True:
        device = device_q.get(block=True, timeout=None)
        device_q.task_done()
        print device

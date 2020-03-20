'''Interface for MusicCast gateway

=== OLD System Docstring
Representation of the Audio-Video system, including non-MusicCast devices.

The Audio-Video system is represented by a tree structure made of the :class:`System`
as root, having a list of :class:`musiccastDevice` objects as branches.
Devices have then lists of :class:`Input` objects and lists of :class:`Zone` objects.

The initialisation process is separated in 3 steps:

#. Instantiate objects, load the static data from a JSON file into local attributes
   and propagate this initialisation steps to the next level, i.e. devices and then
   inputs and zones.

#. Post initialisation step, where some attributes are created based on the whole
   tree structure being already initialised in step 1.  For example, finding and
   assigning the actual object represented by a string *id* in the JSON file, is done
   here.

#. Attempt to retrieve *live* data from all the MusicCast devices
   and initialise various parameters based on this data.  In case of failure,
   the retrieval of the information is delayed and the functionality of the
   device is not available until it goes back *online*.  Beware that in this
   case some *helper* dictionaries might still point to objects that are not valid,
   so always test if a device is *ready* before proceeding using MusicCast related
   attributes.


The execution of a command is triggered by a lambda function retrieved from the
ACTIONS dictionary.
These lambda functions are methods called from a :class:`Zone` objects that
perform all the steps to execute these actions, including sending the actual
requests to the devices over HTTP (through the `musiccast_comm` module).

Note on replies:
The policy to send back status messages depends on the addressing used
by the incoming MQTT message: if it is addressed specifically to this
interface or to a specific MusicCast device, then a reply will always be sent
back (case called ``explicit``); if it is not, a reply is sent only if a command
is executed, otherwise it stays silent as the message is probably intended for
somebody else.

.. reviewed 13 OCt 2018.
   TODO: implement locations
'''

import json
import threading
import Queue
import logging

import musiccast2mqtt as mcc
from musiccast2mqtt.musiccast_device import musiccastDevice
from musiccast2mqtt.musiccast_discovery import musiccastDiscovery
from musiccast2mqtt.musiccast_listener import musiccastListener

from mqttgateway.app_properties import AppProperties

LOG = logging.getLogger(__name__)

class musiccastInterface(object):
    '''The Interface.

    Resolves the system definition file path and calls the System class in musiccast_system.
    Creates the locations and devices dictionaries.

    Args:
        params (dictionary): includes all options from the dedicated section
            of the configuration file.  This class only requires the **sysdefpath** option
            to be defined. It is the location of the JSON file describing the system.  If
            that option is not found then the local directory is used instead.
        msglist_in (list of :class:`internalMsg`): the list of incoming messages.
        msglist_out (list of :class:`internalMsg`): the list of outgoing messages.
    '''

    def __init__(self, params, msglist_in, msglist_out):

        # Load the message lists
        self._msgl_in = msglist_in
        self._msgl_out = msglist_out
        self._explicit = False # if the 'address' of the message is 'explicit'

        # Check the system definition file, if any.  First get the path where to find it.
        try: jsonpath = params['sysdefpath']
        except KeyError:
            LOG.info('The "sysdefpath" option is not defined in the configuration file.'\
                         'Using ".".')
            jsonpath = '.'
        jsonfilepath = AppProperties().get_path(jsonpath, extension='.json')
        # load the system definition data if any; any errors here and we discard everything.
        try:
            with open(jsonfilepath, 'r') as json_file:
                json_data = json.load(json_file)
        except (IOError, OSError):
            LOG.debug(''.join(('Can''t open ', jsonfilepath, '.')))
            json_data = None
        except ValueError: # py3 has a different exception name
            LOG.debug(''.join(('Can''t JSON-parse ', jsonfilepath, '.')))
            json_data = None
        # TODO: Check validity of json_data, transfer in more friendly structure, keep in object.
        if json_data is None:
            pass # dummy statement for further development
        else:
            pass # TODO: process json_data

        # Create the device dictionary {'device_id' : musiccastDevice object}
        self._devices_lock = threading.RLock()
        self._devices_shared = {}
        # Prepare the device factory
        self.device_factory_queue = Queue.Queue(maxsize=mcc.MAX_QUEUE_SIZE)
        self._device_factory_thread = threading.Thread(target=self._device_factory, name='Device Factory')
        # Prepare the discovery loop
        self._discovery_trigger_event = threading.Event()
        self._discovery = musiccastDiscovery(refresh_event=self._discovery_trigger_event,
                                             device_factory_queue=self.device_factory_queue)
        # Load the port to listen to MusicCast events
        try: self.listenport = int(params['listenport'])
        except KeyError:
            self.listenport = mcc.DEFAULT_LISTEN_PORT
            LOG.info(''.join(('The <listenport> option is not defined in the configuration.',
                                  ' Using <', mcc.DEFAULT_LISTEN_PORT, '>.')))
        except TypeError:
            self.listenport = mcc.DEFAULT_LISTEN_PORT
            LOG.info(''.join(('The <listenport> option: <', params['listenport'],
                                  '> is not an int:. Using <', mcc.DEFAULT_LISTEN_PORT, '>.')))
        # Prepare the event processor
        self._event_processor_thread = threading.Thread(target=self._event_processor,
                                                        name='Event Processor')
        # Prepare the event listener
        self._listener = musiccastListener(self.listenport)
        self._musiccast_events_queue = self._listener.get_musiccast_events_queue()

        # Prepare the message processor
        self._message_processor_thread = threading.Thread(target=self._message_processor,
                                                          name='Message Processor')

    def _get_device_from_id(self, device_id, raises=False):
        ''' Returns the device object if found, None otherwise.'''
        with self._devices_lock:
            try:
                device = self._devices_shared[device_id]
            except KeyError:
                if raises:
                    raise mcc.ConfigError(''.join(('Device <', device_id, '> not found.')))
                else:
                    device = None
        return device

    def _device_factory(self):
        ''' Waits on the queue for tasks relating to the devices list.

        This is a loop in a thread listening to a queue of devices represented by their
        device_id and the IP address where they can be reached.
        If the device_id is definitely new then the musiccastDevice class is called to create a new device.
        The item in the queue has to be a dictionary containing the following keys:

        - 'device_id': a 12 digit ASCII string,

        - 'ip_address': a valid address string e.g. '127.0.0.1',

        - 'task': one of CREATE or DELETE objects (defined in the package's __init__)

        '''
        while True:
            item = self.device_factory_queue.get(block=True, timeout=None)
            self.device_factory_queue.task_done()
            with self._devices_lock:
                if item.task == mcc.DeviceHandle.CREATE:
                    if item.device_id not in self._devices_shared:
                        device = musiccastDevice(device_id=item.device_id,
                                                 host=item.host,
                                                 api_port=item.api_port,
                                                 listenport=self.listenport,
                                                 msgl_out=self._msgl_out,
                                                 device_factory_queue=self.device_factory_queue)
                        self._devices_shared[item.device_id] = device
                    else:
                        LOG.debug(''.join(('CREATE: Device <', item.device_id, '> already online.')))
                elif item.task == mcc.DeviceHandle.DELETE:
                    if item.device_id in self._devices_shared:
                        device = self._devices_shared.pop(item.device_id)
                        device.task_queue.put(mcc.DeviceTask(mcc.DeviceTask.DISABLE_DEVICE))
                    else:
                        LOG.debug(''.join(('DELETE: Device <', item.device_id, '> not found.')))
                else: # task unrecognised
                    continue
        return

    def _event_processor(self):
        ''' Wait for a MusicCast event and dispatches it to the right device.

        OLD DOCSTRING:
        Checks if a MusicCast event has arrived and parses it.

        This method uses the dictionary EVENTS based on all possible fields that
        a MusicCast can have (see Yamaha doc for more details).  This
        dictionary has only 2 levels and every *node* is either a **dict** or a
        **callable**.  Any *event* object received from a MusicCast device should
        have a structure which is a subset of the EVENTS one.  The algorithm
        goes through the received *event* structure in parallel of going through
        the EVENTS one.  If there is a key mismatch, the specific key in *event*
        that cannot find a match in EVENTS is ignored.  If there is a key match,
        the lambda function found as value of that key in EVENTS is called with
        the value of that same key found in *event* (the *argument*).

        TODO: check if more than one event could be received in a single call.

        '''
        LOG.debug('Event processor started.')
        while True:
            # the queue delivers JSON-style dictionaries representing MusicCast events
            event = self._musiccast_events_queue.get(block=True, timeout=None)
            self._musiccast_events_queue.task_done()
            # Find device within the event dictionary
            device_id = event.pop('device_id', None) # read and remove key
            if device_id is None: # log error and move on
                LOG.debug('Event has no device_id. Ignore.')
                continue
            device = self._get_device_from_id(device_id, raises=False)
            # multithread comment: if device is found, from now on it might still become an 'orphan'
            #     at any time; if so, it does not matter, the task gets queued but probably never
            #     picked up.
            if device is None:
                LOG.debug('Event has unrecognised device_id. Ignore.')
                continue
            # queue the item
            device.task_queue.put(mcc.DeviceTask(mcc.DeviceTask.PROCESS_EVENT, event=event))
        LOG.debug('Event processor ended.')
        return

    @staticmethod
    def _filter_topics(msg):
        ''' Returns True is topics are valid, False otherwise. '''
        if not msg.iscmd: # ignore status messages for now?
            return False
        if msg.sender == mcc.APP_NAME: # ignore echoes
            return False
        # the following filters could be dealt by subscriptions
        if not msg.function and not msg.gateway:
            raise mcc.LogicError('No function or gateway in message.')
        if msg.gateway and msg.gateway != mcc.APP_NAME:
            return False
        if msg.function and msg.function != mcc.APP_FUNCTION:
            return False
        return True

    def _resolve_zone(self, msg):
        ''' Finds the zone to operate by resolving the "address" from the topic items.

        The resolution uses both location and device fields from the topic.
        The current algorithm is a *strict* one, meaning that if a field is provided, it needs
        to exist otherwise an exception is thrown.  One could imagine a more *tolerant* algorithm
        if necessary (e.g. if both location and device are provided and the location produces
        a valid result while the device does not, then the location resolution *wins*).
        The location defines a zone directly.
        The device defines only the device (...) so the zone has to be in the arguments otherwise
        a default is taken (the first zone in the list).  This implies that there should always be
        at least 1 zone in a device and that the first one should be the *main* one if possible.
        This method should be thread-safe. It uses a re-entrant lock for the devices disctionary.

        Args:
            msg (:class:internalMsg): the incoming message to parse.

        Returns:
            :class:Zone: a valid Zone object

        Raises:
            LogicError, ConfigError.
        '''

        msg.location = None # TODO: implement location processing; ignore location for now

        self._explicit = msg.gateway or msg.device # defines if to send a reply or not
        if not msg.location and not msg.device:
            raise mcc.LogicError('No location or device in message.')

        # to properly find the right zone and be consistent, we have to lock the dictionary
        with self._devices_lock:
            # sets zone_from_location based on the location, None if not found.
            if msg.location:
                zone_from_location = None # TODO: implement location processing
            if msg.device:
                device = self._get_device_from_id(msg.device, raises=True)
                # find the zone in the device from the arguments, None if not found
                zone_id = msg.arguments.get('zone', None)
                if zone_id is not None: # assume it is the zone mcid.
                    # TODO: implement rename and friendly name
                    zone_from_device = device.get_zone(zone_mcid=zone_id, raises=False)
                else:
                    zone_from_device = None
            if msg.location and msg.device:
                # check consistency. (1) devices found have to be the same
                if device != zone_from_location.device:
                    raise mcc.LogicError('Location and device point to different devices.')
                # (2) if zone_from_device is defined, the zones need to be the same
                if zone_from_device is not None:
                    if zone_from_device != zone_from_location:
                        raise mcc.LogicError('Location and device point to different zones.')
                zone_returned = zone_from_location
            elif msg.device:
                if zone_from_device is None:
                    zone_from_device = device.zones[0] # take the first one by default
                zone_returned = zone_from_device
            else: # msg.location is not None
                zone_returned = zone_from_location
        return zone_returned

    def _message_processor(self):
        ''' Waits for a message, parses and executes it.'''
        LOG.debug('Message processor started.')
        while True:
            msg = self._msgl_in.get(block=True, timeout=None)
            self._msgl_in.task_done()
            LOG.debug(''.join(('Processing message: ', msg.str())))

            if not self._filter_topics(msg):
                LOG.debug('Topics do not match.')
                continue

            try:
                zone = self._resolve_zone(msg)
            except (mcc.ConfigError, mcc.LogicError):
                LOG.debug('Zone can not be resolved.')
                continue

            zone.device.task_queue.put(mcc.DeviceTask(mcc.DeviceTask.PROCESS_MESSAGE,
                                                      msg=msg, zone=zone))
        LOG.debug('Message processor ended.')
        return

    def loop_start(self):
        ''' Starts all the threads and loops needed.'''
        self._message_processor_thread.start()
        self._device_factory_thread.start() # Start the device factory thread
        self._discovery.loop_start() # Start the discovery loop
        self._event_processor_thread.start() # Start the event processor thread
        self._listener.loop_start() # Start the event listener
        return

    def loop_stop(self):
        ''' Stops all loops and threads started in `loop_start`.'''
        # TODO: Implement loop_stop
        return

if __name__ == '__main__':
    pass

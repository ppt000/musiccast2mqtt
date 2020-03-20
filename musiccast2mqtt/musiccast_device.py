''' Declaration of musiccastDevice objects.

musiccastDevice objects are created when a new device is discovered by the discovery process or when it
is present in the cache file at start-up.
As soon as they are created, a new thread is started with the its own queue to process incoming
events or incoming messages.

Notes on refreshing the device:

There are 3 reasons why one needs to refresh the status of a device:

1- because the MusicCast devices need to receive at least one request every 10 minutes
   (with the right headers) so that they keep sending events;

2- when this gateway has sent a **set** command and one wants to check if the command
   has been successful.  It seems though that one needs to wait a bit before requesting
   a fresh status as experience shows that firing a **getStatus** request straight after a
   command does not reflect the change even if the command is supposed to be successful.

3- when the device is 'down' or 'offline', e.g. it has had a few errors of communication
   and this application has decided to categorise it as not available but still existing,
   and therefore at some point it needs to be initialised again (or at least this
   application should 'try' to initialise it again).

.. reviewed 9 November 2018
'''

import time
import threading
import Queue
import logging

import musiccast2mqtt as mcc
from musiccast2mqtt.musiccast_comm import musiccastComm
from musiccast2mqtt.musiccast_playinfotype import Tuner, CD, NetUSB
from musiccast2mqtt.musiccast_input import Feed, Source
from musiccast2mqtt.musiccast_zone import Zone

LOG = logging.getLogger(__name__)

class musiccastDevice(object):
    ''' Represents a device in the audio-video system.

    Args:
        device_id (string): 12 digit ASCII uniquely representing the device
        ip_address (string): where to reach the device
        listenport (int): the port where to listen for incoming events
        msgl_out: the queue for the outgoing messages
        device_factory_queue: the device factory queue (...)

    '''

    def __init__(self, device_id, host, api_port, listenport, msgl_out, device_factory_queue):
        self._device_mcid = device_id.upper()
        self._host = host
        self._api_port = api_port
        self._listenport = listenport
        self._device_factory_queue = device_factory_queue
        self._msgl_out = msgl_out
        self._msg = None # current message being processed.

        # attributes defined later
        self.conn = None # connection to send the request
        self._dev_info = None # dictionary of device information
        self._serial_num = None # serial number, also called system_id
        self._model = None
        self._features = None # dictionary of device features
        self.zones = [] # list (later tuple) of zones
        self.zone_d = {} # to help the event processor. {zone_mcid: Zone object}
        self.feeds = [] # list (later tuple) of feeds
        self.sources = [] # list (later tuple) of sources
        self.inputs = None # will be tuple of all inputs (feeds + sources)

        self._inputs_d = {}
        self._infotype_d = {}

        self._ready = False
        self._load_time = 0

        # Thread related attributes
        self.task_queue = Queue.Queue(maxsize=mcc.MAX_QUEUE_SIZE)
        self._thread = threading.Thread(target=self._device_loop,
                                        name=''.join(('Device Thread - ', self._device_mcid)))

        # List to implement periodic refresh
        self._delayed_request_list = []

        # Start the thread for this device
        self._thread.start()
        LOG.debug(''.join(('Device thread for <', self.get_id(), '> started.')))

        return

    def get_id(self):
        ''' Getter for _device_mcid.'''
        return self._device_mcid

    def name(self):
        ''' Returns a friendly name for the device.'''
        return ''.join((self._model, '#', self._device_mcid))

    def get_argument(self, arg):
        ''' Retrieves argument from arguments dictionary.

        This method is used by the lambdas to get access to the argument of the message.
        It is essential that the lambdas are running in the same thread as the one that updated
        the _msg attribute in the same musiccastDevice instance.

        Args:
            arg (string): the name of the argument sought
        '''
        if self._msg is None:
            raise mcc.LogicError(''.join(('No message to look into.')))
        try:
            value = self._msg.arguments[arg]
        except KeyError:
            raise mcc.LogicError(''.join(('No argument <', arg, '> found.')))
        return value

    def get_zone(self, zone_mcid, raises=False):
        ''' Returns the :class:`Zone` object from its identification.

        Args:
            zone_mcid (string): the MusicCast id of the zone searched
            raises (boolean): if True, raises an exception instead of returning ``False``
        '''
        if zone_mcid is None:
            if raises: raise mcc.ConfigError('Zone id cannot be None.')
            else: return None
        try:
            return self.zone_d[zone_mcid]
        except KeyError:
            if raises: raise mcc.ConfigError(''.join(('Zone id <', zone_mcid,
                                                      '> not found in device <',
                                                      self.name(), '>.')))
            else: return None

    def get_input(self, input_mcid, raises=False):
        ''' Returns the :class:`Input` object from its mcid.
        Args:
            input_mcid (string): the MusicCast id of the input searched
            raises (boolean): if True, raises an exception instead of returning ``False``

        Returns:
            :class:`Input` object if found, or ``None``

        Raises:
            ConfigError or LogicError.
        '''
        if input_mcid is None:
            if raises:
                raise mcc.ConfigError(''.join(('No valid input id argument on device <',
                                               self.name(), '>.')))
            else:
                return None
        else:
            try:
                inp = self._inputs_d[input_mcid]
            except KeyError:
                if raises:
                    raise mcc.ConfigError(''.join(('MusicCast input <', input_mcid,
                                                   '> not found in device <', self.name(), '>.')))
                else: return None
        return inp

    def init_infotype(self, play_info_type):
        ''' Returns a new or an existing instance of PlayInfoType.

        For each type there is only one instance of the corresponding class.

        Args:
            play_info_type (string): one of **tuner**, **cd**, or **netusb**.

        Raises:
            ConfigError: if the play_info_type is not recognised.
        '''
        if play_info_type in self._infotype_d:
            return self._infotype_d[play_info_type]
        if play_info_type == 'tuner':
            self._infotype_d[play_info_type] = Tuner(self)
            return self._infotype_d[play_info_type]
        elif play_info_type == 'cd':
            self._infotype_d[play_info_type] = CD(self)
            return self._infotype_d[play_info_type]
        elif play_info_type == 'netusb':
            self._infotype_d[play_info_type] = NetUSB(self)
            return self._infotype_d[play_info_type]
        elif play_info_type == 'none':
            return None
        else:
            raise mcc.ConfigError(''.join(('PlayInfoType <', play_info_type, '> does not exist.')))

    def get_infotype(self, play_info_type):
        ''' Retrieves the info_type instance.

        Only used (for now) by the event lambdas.
        '''
        try: return self._infotype_d[play_info_type]
        except KeyError:
            raise mcc.ConfigError(''.join(('InfoType <', play_info_type, '> not found.')))

    def get_feature(self, flist):
        ''' Returns a branch from the getFeatures tree.

        This method retrieves a branch or leaf from a JSON type object.
        The argument is a list made of strings and/or pairs of string.
        For each string, the method expect to find a dictionary as the next branch,
        and selects the value (which is another branch or leaf) returned by that string as key.
        For each single key dictionary {key: value}, it expects to find an array or similar objects,
        and in that case it searches for the array that contains the right 'value' for that 'key'.

        This method helps in reading the responses from Yamaha MusicCast API.

        Args:
            flist: list representing a leaf or a branch from a JSON type of string

        Raises:
            CommsError, ConfigError.

        Example:
            Use get_feature(('zone', {'id': 'main'}, 'range_step', {'id': 'volume'}, 'max'))
            to retrieve
        '''
        branch = self._features
        if isinstance(flist, basestring): # Python 3: isinstance(arg, str)
            flist = (flist,)
        for arg in flist:
            if isinstance(arg, basestring):
                try: branch = branch[arg]
                except KeyError:
                    raise mcc.ConfigError(''.join(('Argument <', str(arg),
                                                   '> not found in current branch: ',
                                                   str(branch))))
                except TypeError:
                    raise mcc.CommsError(''.join(('The current branch is not a dictionary: ',
                                                  str(branch))))

            elif isinstance(arg, dict) and len(arg) == 1: # arg is a single key dictionary
                key, value = arg.items()[0]
                try:
                    _ = iter(branch)
                except TypeError:
                    raise mcc.ConfigError(''.join(('The current branch is not an array: ',
                                                   str(branch))))
                obj = None
                found = False
                for obj in branch:
                    try: found = (obj[key] == value)
                    except KeyError:
                        raise mcc.ConfigError(''.join(('Key <', str(key),
                                                       '> not found in current branch: ',
                                                       str(obj))))
                    except TypeError:
                        raise mcc.ConfigError(''.join(('The current branch is not a dictionary: ',
                                                       str(obj))))
                    if found: break
                if obj is None:
                    raise mcc.ConfigError(''.join(('The current branch has no length: ',
                                                   str(branch))))
                if not found:
                    raise mcc.ConfigError(''.join(('Value <', str(value), '> for key <',
                                                   str(key), '> not found in array.')))
                branch = obj
            else: # unrecognised token
                raise mcc.ConfigError(''.join(('Unrecognised token: ', str(arg))))
        return branch

    def is_ready(self, raises=False):
        ''' Returns True if the device is ready to be operated.

        Args:
            raises (boolean): if True, raises an exception when device is not ready, otherwise
                it just returns False.

        Returns:
            boolean: True if device is ready, False if not and `raises` is False.

        Raises:
            LogicError: if the device is not ready and the `raises` argument is True.
        '''
        if self._ready: return True
        elif raises: raise mcc.LogicError(''.join(('The device ', self.name(), ' is not available.')))
        else: return False

    def disable(self):
        ''' Disables the device to make requests. Can be called more than once.'''
        self.conn.disable()
        return

    def insert_delayed_request(self, delay, zone):
        ''' Inserts a delayed request in the appropriate list.'''
        if delay < 0: return
        delayed_time = time.time() + delay
        request = {'time': delayed_time, 'zone': zone}
        index = 0
        for item in self._delayed_request_list:
            if delayed_time > item['time']: break
            index += 1
        self._delayed_request_list.insert(index, request)
        return

    def _device_loop(self):
        ''' Main thread for a new device.'''

        LOG.debug('Entered the _device_loop method.')
        process_error = False

        try:
            self._init_device()
        except (mcc.CommsError, mcc.ConfigError) as err:
            LOG.debug(''.join(('_init_device has failed with error:', str(err))))
            process_error = True # any error during initialisation and the device is out

        # TODO: improve the error processing with retries
        while not process_error: # here any error during operation and the device is out
            now = time.time()
            # process the delayed request list.
            while True: # check first for items that are already too old
                try:
                    request = self._delayed_request_list[0]
                except IndexError: # list empty
                    break
                if request['time'] > (now + 0.01): # TODO: put in constant
                    break # request is in the future
                # here the request has already passed; put it in the queue for immediate execution
                self.task_queue.put(mcc.DeviceTask(mcc.DeviceTask.REFRESH_STATUS,
                                                   zone=request['zone']))
                del self._delayed_request_list[0]
            try:
                timeout_request = self._delayed_request_list[0]
            except IndexError: # list empty
                self.insert_delayed_request(delay=mcc.STALE_CONNECTION, zone=self.zones[0])
                timeout_request = self._delayed_request_list[0]
            timeout = timeout_request['time'] - time.time()
            # wait for an item in the queue
            try:
                item = self.task_queue.get(block=True, timeout=timeout)
            except Queue.Empty: # timed out
                continue # the next loop will put the timeout request in the queue as it will be old

                #===================================================================================
                # try: # refresh the connection
                #     timeout_request['zone'].refresh_status()
                #     self._zone_index = (self._zone_index + 1) % self._zone_num # next zone
                # except (mcc.CommsError, mcc.ConfigError):
                #     process_error = True
                #     continue
                # del self._delayed_request_list[0]
                # continue
                #===================================================================================
            self.task_queue.task_done()
            # switch on task
            if item.task == mcc.DeviceTask.PROCESS_EVENT:
                try:
                    self.process_event(item.event)
                except (mcc.CommsError, mcc.ConfigError):
                    process_error = True
                    continue
            elif item.task == mcc.DeviceTask.PROCESS_MESSAGE:
                try:
                    self.process_message(item.msg, item.zone)
                except (mcc.CommsError, mcc.ConfigError):
                    process_error = True
                    continue
            elif item.task == mcc.DeviceTask.DISABLE_DEVICE:
                self.disable()
            elif item.task == mcc.DeviceTask.REFRESH_STATUS:
                try:
                    item.zone.refresh_status()
                except (mcc.CommsError, mcc.ConfigError):
                    process_error = True
                    continue
            else: # unrecognised task
                continue

        LOG.debug('Device has failed. Ending _device_loop.')
        # if we are here it means that there was a process error and the device is terminated
        self.disable()
        # make sure the device is removed from the list of devices
        self._device_factory_queue.put(mcc.DeviceHandle(mcc.DeviceHandle.DELETE,
                                                        device_id=self._device_mcid))
        return # this will end this thread

    def _init_device(self):
        ''' Initialise the device within its own thread.

        Raises:
            CommsError, ConfigError.
        '''

        self.conn = musiccastComm(self._host, self._api_port, self._listenport)

        # Retrieve the device info and load them
        self._dev_info = self.conn.mcrequest('system', 'getDeviceInfo')
        try:
            device_id = self._dev_info['device_id'].upper()
            self._serial_num = self._dev_info['system_id']
            self._model = self._dev_info['model_name']
        except KeyError:
            raise mcc.CommsError('getDeviceInfo does not have the expected structure.')
        if self._device_mcid != device_id: # sanity check
            raise mcc.ConfigError('getDeviceInfo does not yield the expected device_id.')

        # Retrieve the device features
        self._features = self.conn.mcrequest('system', 'getFeatures')

        # Create the zones
        for zone_data in self.get_feature('zone'):
            zone = Zone(zone_data, self)
            if zone.zone_mcid == 'main': # ensure first in the list is 'main'
                self.zones.insert(0, zone)
            else:
                self.zones.append(zone)
            self.zone_d[zone.zone_mcid] = zone # update the helper dictionary
        if not self.zones:
            raise mcc.ConfigError(''.join(('Device <', self.name(), '> has no zones.')))
        self.zones = tuple(self.zones) # 'freeze' the list in a tuple

        # Create the inputs, sources and feeds
        for input_data in self.get_feature(('system', 'input_list')):
            try:
                play_info_type = input_data['play_info_type']
            except KeyError:
                mcc.CommsError('getFeatures does not have the expected structure.')
            if play_info_type == 'none':
                feed = Feed(input_data, self)
                self.feeds.append(feed)
            else:
                source = Source(input_data, self)
                self.sources.append(source)
        self.feeds = tuple(self.feeds)
        self.sources = tuple(self.sources)
        self.inputs = self.feeds + self.sources
        if not self.inputs:
            raise mcc.ConfigError(''.join(('Device <', self.name(), '> has no inputs.')))
        self._inputs_d = {inp.input_mcid:inp for inp in self.inputs}

        # success
        self._ready = True
        self._load_time = time.time() # time of initialisation for future reference
        LOG.debug(''.join(('Initialisation of device <', self.name(), '> successful.')))

        return

    def process_event(self, event):
        ''' Processes the event received and executes whatever lambdas found.

        This method parses the event through a function and dictionary in musiccast_data that
        walks through the event ad matches every step with the template event dictionary.
        When it reaches the leaf, a set of lambdas are found to be executed.
        '''
        func_list = musiccastDevice.parse_event(event)
        # now execute the lambdas
        while True:
            try: func, arg = func_list.pop(0)
            except IndexError: break
            try: func(self, arg)
            except mcc.AnyError as err:
                LOG.info(''.join(('Problem processing event item. Ignore.\n\tError: ',
                                      repr(err))))
        return

    def process_message(self, msg, zone):
        ''' Processes the incoming message, passing it to the relevant zone.

        This method simply handles the incoming message to the right zone.
        '''
        self._msg = msg # update the attribute to give access to the lambdas
        response, reason = zone.execute_action(msg)
        if response:
            self._msgl_out.push(self._msg.reply(response, reason))
        return

    @staticmethod
    def parse_event(event):
        ''' Reads event dictionary and returns lambdas for each key match found.'''
        flist = [] # list of all lambdas to call; the elements are pairs (func, arg)
        for key1 in event:
            try: isdict = isinstance(musiccastDevice.EVENTS[key1], dict)
            except KeyError:
                LOG.info(''.join(('Event has an unknown item <', str(key1), '>. Ignore.')))
                continue
            if isdict:
                if not isinstance(event[key1], dict):
                    raise mcc.ConfigError('Unexpected structure of event. Ignore.')
                for key2 in event[key1]:
                    try: func = musiccastDevice.EVENTS[key1][key2]
                    except KeyError:
                        LOG.info(''.join(('Unknown item in event <', str(key2), '>. Ignore.')))
                        continue
                    if func is not None: flist.append((func, event[key1][key2]))
            else:
                func = musiccastDevice.EVENTS[key1]
                if func is not None: flist.append((func, event[key1]))
        return flist

    EVENTS = { # lambdas to be called by a Device object; value is always a string
        'system': {
            'bluetooth_info_updated': None, # not implemented; use 'getBluetoothInfo'
            'func_status_updated': None, # not implemented; use 'getFuncStatus'
            'speaker_settings_updated': None, # not implemented
            'name_text_updated': None, # not implemented; use 'getNameText'
            'tag_updated': None, # not implemented
            'location_info_updated': None, # not implemented; use 'getLocationInfo'
            'stereo_pair_info_updated': None # not implemented
        },
        'main': {
            'power': lambda self, value: self.get_zone('main', True).update_power(mcvalue=value),
            'input': lambda self, value: self.get_zone('main', True).update_input(mcvalue=value),
            'volume': lambda self, value: self.get_zone('main', True).update_volume(mcvalue=value),
            'mute': lambda self, value: self.get_zone('main', True).update_mute(mcvalue=value),
            'status_updated': lambda self, value:
                              self.get_zone('main', True).refresh_status() if value else None,
            'signal_info_updated': None # not implemented; use 'getSignalInfo'
        },
        'zone2': {
            'power': lambda self, value: self.get_zone('zone2', True).update_power(mcvalue=value),
            'input': lambda self, value: self.get_zone('zone2', True).update_input(mcvalue=value),
            'volume': lambda self, value: self.get_zone('zone2', True).update_volume(mcvalue=value),
            'mute': lambda self, value: self.get_zone('zone2', True).update_mute(mcvalue=value),
            'status_updated': lambda self, value:
                              self.get_zone('zone2', True).refresh_status() if value else None,
            'signal_info_updated': None, # not implemented; use 'getSignalInfo'
        },
        'zone3': {},
        'zone4': {},
        'tuner': {
            'play_info_updated': lambda self, value:
                                 self.get_infotype('tuner').update_play_info() if value else None,
            'preset_info_updated': lambda self, value:
                                   self.get_infotype('tuner').update_preset_info() if value else None,
        },
        'netusb': {
            'play_error': None, # TODO: implement
            'multiple_play_errors': None, # TODO: implement
            'play_message': lambda self, value:
                            self.get_infotype('netusb').update_play_message(value),
            'account_updated': None, # not implemented; use 'getAccountStatus'
            'play_time': lambda self, value:
                         self.get_infotype('netusb').update_play_time(value),
            'preset_info_updated': lambda self, value:
                                   self.get_infotype('netusb').update_preset_info() if value else None,
            'recent_info_updated': None, # not implemented; use 'getRecentInfo'
            'preset_control': None, # not implemented; read the value field for info
            # value is a dict:
            #    {'type': ['store', 'clear', 'recall'],
            #     'num': int,
            #     'result': ['success' (for all types),'error' (for all types),
            #                'empty' (only for recall),
            #                'not_found' (only for recall)]}
            # Implementing this event might be needed to detect if the 'station'
            #   has been changed; hopefully if this happens it also triggers a
            #   'play_info_updated' event, which IS implemented, so we don't need
            #   this one.
            'trial_status': None, # not implemented
            # value = {'input': (string), 'enable': (boolean)}
            'trial_time_left': None, # not implemented
            # value = {'input': (string), 'time': (int)}
            'play_info_updated': lambda self, value:
                                 self.get_infotype('netusb').update_play_info() if value else None,
            'list_info_updated': None # not implemented; use 'getListInfo'
        },
        'cd': {
            'device_status': None, # not implemented; use 'cd_status'
            'play_time': lambda self, value:
                         self.get_infotype('cd').update_play_time(value),
            'play_info_updated': lambda self, value:
                                 self.get_infotype('cd').update_play_info() if value else None,
        },
        'dist': {
            'dist_info_updated': None # not implemented
        },
        'clock': {
            'settings_updated': None # not implemented
        },
        'device_id': None
    }
    '''
    Dictionary to decode incoming events.

    The lambdas should be called by a :class:`Device` object.
    '''

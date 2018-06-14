''' Representation of the Audio-Video system, including non-MusicCast devices.

.. reviewed 31 May 2018

The Audio-Video system is represented by a tree structure made of the
:class:`System` as root, having a list of :class:`Device` objects as branches.
Devices have then lists of :class:`Input` objects and lists of :class:`Zone` objects.

The initialisation process is separated in 3 steps:

1. Instantiate objects, load the static data from a JSON file into local attributes
   and propagate this initialisation steps to the next level, i.e. devices and then
   inputs and zones.

2. Post initialisation step, where some attributes are created based on the whole
   tree structure being already initialised in step 1.  For example, finding and
   assigning the actual object represented by a string *id* in the JSON file, is done
   here.

3. Attempt to retrieve *live* data from all the MusicCast devices
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
'''

import musiccast2mqtt.musiccast_exceptions as mcx
#import musiccast2mqtt.musiccast_comm as mcc
from musiccast2mqtt.musiccast_comm import musiccastListener
from musiccast2mqtt.musiccast_data import EVENTS
from musiccast2mqtt.musiccast_device import Device

import mqttgateway.utils.app_properties as app
_logger = app.Properties.get_logger(__name__)

class System(object):
    '''Root of the audio-video system.

    This class loads the *static* data into local attributes from the JSON file.
    Some checks are performed.
    Configuration errors coming from a bad description of the system in the file are
    fatal.

    It then retrieves MusicCast parameters from the MusicCast devices through HTTP requests.
    In case of connection errors, the device concerned is put in a *not ready* state,
    and its update delayed.

    The initialisation process also starts the events listener, which is unique
    across all MusicCast devices.

    Args:
        json_data (string): JSON valid code describing the system.
            Check it against the available schema.
        msgl (MsgList object): the outgoing message list

    Raises:
        Any of AttributeError, IndexError, KeyError, TypeError, ValueError:
            in case the unpacking of the JSON data fails, for whatever reason.
    '''

    def __init__(self, json_data, listenport, msgl):
        # Initialise the events listener.
        self.listen_port = listenport
        #mcc.set_socket(listen_port)
        self._listener = musiccastListener(self.listen_port)
        # Assign locally the message attributes
        self._msgl = msgl
        self._msgin = None
        #self._msgout = None
        self._arguments = {}
        self._explicit = False # indicates if the addressing is explicit or not
        # Create the list of devices; this unwraps the whole JSON structure
        devices = []
        for device_data in json_data['devices']:
            try: device = Device(device_data, self)
            except mcx.AnyError as err:
                _logger.info(''.join(('Problem loading device. Error:\n\t', str(err))))
                continue
            devices.append(device)
        self.devices = tuple(devices)
        # some helpers
        self.mcdevices = tuple([dev for dev in self.devices if dev.musiccast])
        self._devices_by_id = {dev.id: dev for dev in self.devices}
        #self._devices_by_yxcid = {} # updated in load_musiccast
        # Assign the device and zone connected to each feed.
        for dev in self.devices:
            try: dev.post_init()
            except mcx.AnyError as err:
                _logger.info(''.join(('Problem in post initialisation. Error:\n\t', str(err))))
                continue
        # Now we can initialise MusicCast related fields
        for dev in self.mcdevices:
            try: dev.load_musiccast()
            except mcx.CommsError as err:
                _logger.info(''.join(('Cannot initialise MusicCast device <', dev.id,
                                      '>. Error:\n\t', str(err))))
                continue
            except mcx.ConfigError as err:
                # These should be only related to a bad system definition? unrecoverable?
                _logger.info(''.join(('MusicCast device ', self.id,
                                      ' seems badly configured. Error:\n\t', str(err))))
                continue
            except mcx.AnyError as err:
                _logger.info(''.join(('Problem in loading MusicCast information. Error:\n\t',
                                      str(err))))
                continue
            # create the {location: zone} dictionary
            self._locations = {zone.location: zone
                               for dev in self.devices
                               for zone in dev.zones
                               if zone.location}
        return

    def _filter_topics(self):
        ''' docstring '''
        _logger.debug('Filtering topics')
        if not self._msgin.iscmd: # ignore status messages (for now?)
            return False
        if self._msgin.sender == 'musiccast': # ignore echoes
            return False
        # the following filters could be dealt by subscriptions
        if not self._msgin.function and not self._msgin.gateway:
            raise mcx.LogicError('No function or gateway in message.')
        if self._msgin.gateway and self._msgin.gateway != 'musiccast':
            return False
        if self._msgin.function and self._msgin.function != 'AudioVideo':
            return False
        if not self._msgin.location and not self._msgin.device:
            raise mcx.LogicError('No location or device in message.')
        return True

    def _resolve_zone(self):
        ''' docstring'''
        _logger.debug('Resolve zone')
        # find the zone to operate by resolving the 'address'
        self._explicit = False
        zone_from_location = None
        zone_from_device = None
        #
        if self._msgin.gateway: self._explicit = True
        if self._msgin.location:
            try: zone_from_location = self._locations[self._msgin.location]
            except KeyError:
                raise mcx.LogicError(''.join(('Location <', self._msgin.location, '>not found.')))
        if self._msgin.device:
            self._explicit = True
            try: device = self._devices_by_id[self._msgin.device]
            except KeyError:
                raise mcx.LogicError(''.join(('Device <', self._msgin.device, '> not found')))
            # check if the zone in the device is provided in the arguments
            zone_id = self._msgin.arguments.get('zone', None)
            if zone_id:
                zone_from_device = device.get_zone(zone_id=zone_id, raises=True)
            # if there was no zone specified in the arguments, zone_from_device is still None here
            # check consistency between device and location, if location was resolved
            if zone_from_location:
                if zone_from_location.device != device:
                    raise mcx.LogicError('Location and device point to different devices.')
                if zone_from_device and zone_from_location != zone_from_device:
                        raise mcx.LogicError('Location and device point to different zones.')
                return zone_from_location # all other cases lead to this
            else:
                if not zone_from_device:
                    zone_from_device = device.zones[0] # take the first one by default
                return zone_from_device
        return zone_from_location

    def process_msg(self, msg):
        ''' docstring '''
        # keep message locally
        self._msgin = msg
        # TODO: can't we just leave the arguments where they are?
        self._arguments.clear()
        if msg.arguments:
            for arg in msg.arguments: self._arguments[arg] = msg.arguments[arg] # copy arguments
        # process the message
        if not self._filter_topics(): return
        zone = self._resolve_zone()
        response, reason = zone.execute_action(self._msgin.action)
        if response:
            self._msgl.push(self._msgin.reply(response, reason))
        return

    def get_device(self, device_id=None, yxc_id=None, raises=False):
        ''' Returns the :class:`Device` object from its id or Yamaha id.

        Args:
            device_id (string): the id of the device sought
            yxc_id (string): the Yamaha hardware id of the device sought
            raises (boolean): if True, raises an exception instead of returning ``False``
        '''
        if device_id:
            try: return self._devices_by_id[device_id]
            except KeyError:
                err = ''.join(('Device id <', str(device_id), '> not found.'))
        elif yxc_id:
            for dev in self.devices:
                if yxc_id == dev.get_yxcid(raises=False): return dev
            err = ''.join(('Yamaha id <', str(yxc_id), '> not found.'))
            # The code below can be reinstated once the dictionary works
            #try: return self._devices_by_yxcid[yxc_id]
            #except KeyError: err = ''.join(('Yamaha id <', str(yxc_id), '> not found.'))
        else:
            err = 'No valid argument in get_device()'
        if raises: raise mcx.ConfigError(err)
        else: return None

    def get_argument(self, arg):
        ''' Retrieves argument from arguments dictionary.

        Args:
            arg (string): the name of the argument sought
        '''
        try: return self._arguments[arg]
        except KeyError: raise mcx.LogicError(''.join(('No argument <', arg, '> found.')))

    def listen_musiccast(self):
        ''' Checks if a MusicCast event has arrived and parses it.

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
        #event = mcc.get_event()
        event = self._listener.get_event()
        if event is None: return
        # Find device within the event dictionary
        device_id = event.pop('device_id', None) # read and remove key
        if device_id is None: raise mcx.CommsError('Event has no device_id. Ignore.')
        device = self.get_device(yxc_id=device_id, raises=True)
        # Read event dictionary and call lambda for each key match found
        flist = [] # list of all lambdas to call; the elements are pairs (func, arg)
        for key1 in event:
            try: isdict = isinstance(EVENTS[key1], dict)
            except KeyError:
                _logger.info(''.join(('Event has an unknown item <', str(key1), '>. Ignore.')))
                continue
            if isdict:
                if not isinstance(event[key1], dict):
                    raise mcx.ConfigError('Unexpected structure of event. Ignore.')
                for key2 in event[key1]:
                    try: func = EVENTS[key1][key2]
                    except KeyError:
                        _logger.info(''.join(('Unknown item in event <', str(key2), '>. Ignore.')))
                        continue
                    if func is not None: flist.append((func, event[key1][key2]))
            else:
                func = EVENTS[key1]
                if func is not None: flist.append((func, event[key1]))
        # now execute the lambdas
        while True:
            try: func, arg = flist.pop(0)
            except IndexError: break
            try: func(device, arg)
            except mcx.AnyError as err:
                _logger.info(''.join(('Problem processing event item. Ignore. Error:\n\t',
                                      repr(err))))
        return

    def refresh(self):
        ''' Performs various periodic checks and refreshers on all devices.'''
        for dev in self.mcdevices:
            try: dev.refresh()
            except mcx.AnyError as err:
                _logger.info(''.join(('Problem refreshing device. Error:\n\t', str(err))))
                continue

'''
Representation of the Audio-Video system, including non-MusicCast devices.

The initialisation process is separated in 2 steps:

#. Load the static data from a JSON file into a local hierarchy made of
   a single system with devices that each have zones, sources and feeds.

#. Attempt to retrieve *live* data from all the MusicCast devices
   and initialise various parameters based on this data.  In case of failure,
   the retrieval of the information is delayed and the functionality of the
   device is not available until it goes back *online*.

The execution of a command is triggered by a lambda function retrieved from the
ACTIONS dictionary (done within the loop in the `musiccast_interface` module).
These lambda functions are methods called from a :class:`Zone` objects that
perform all the steps to execute these actions, including sending the actual
requests to the devices over HTTP (through the `musiccast_comm` module).

'''

import mqtt_gateways.musiccast.musiccast_exceptions as mcx
import mqtt_gateways.musiccast.musiccast_comm as mcc
from mqtt_gateways.musiccast.musiccast_data import ACTIONS, EVENTS
from mqtt_gateways.musiccast.musiccast_device import Device

import mqtt_gateways.utils.app_properties as app
_logger = app.Properties.get_logger(__name__)

class System(object):
    '''Root of the audio-video system.

    This class loads the *static* data into local attributes from the JSON file.  Some checks are
    performed. Configuration errors coming from a bad description of the system in the file are
    fatal.

    Then it retrieves MusicCast parameters from the MusicCast devices through HTTP requests.  In
    case of connection errors, the device concerned is put in a *not ready* state, and its update
    delayed.

    The initialisation process also starts the events listener, which is unique
    across all MusicCast devices.

    Args:
        json_data (string): JSON valid code describing the system.
            Check it against the available schema.
        msgl (MsgList object): the outgoing message list #TODO:move it to upload method

    Raises:
        Any of AttributeError, IndexError, KeyError, TypeError, ValueError:
            in case the unpacking of the JSON data fails, for whatever reason.
    '''

    def __init__(self, json_data, msgl):

        # Initialise the events listener.
        listen_port = 41100 # TODO: check what port to use
        mcc.set_socket(listen_port)

        # Assign locally the message attributes
        self._msgl = msgl
        self._msgin = None
        self._msgout = None
        self._arguments = {}

        # Create the list of devices; this unwraps the whole JSON structure
        devices = []
        for device_data in json_data['devices']:
            try: devices.append(Device(device_data, self))
            except mcx.AnyError as err:
                _logger.info(''.join(('Problem loading device. Error:\n\t', repr(err))))
                continue
        self.devices = tuple(devices)
        # some helpers
        self.mcdevices = tuple([dev for dev in self.devices if dev.musiccast])
        self._devices_by_id = {dev.id: dev for dev in self.devices}

        # Assign the device and zone connected to each feed.
        for dev in self.devices:
            dev.post_init()

        # Now we can initialise MusicCast related fields
        for dev in self.mcdevices:
            dev.load_musiccast()

        return

    def put_msg(self, msg):
        '''
        Load locally internal message coming from the mapping engine.

        Load message, unpack arguments and transform them to the MusicCast
        protocol for easy access later by the lambda functions. The arguments in
        `msg.arguments` are strings of *internal* keywords. They need to be
        transformed into a MusicCast format (even it is only really needed for
        values like volume or booleans). The *local* dictionary `self._arguments`
        contains the same keys as `msg.arguments`.
        '''
        # TODO: can't we just leave the arguments where they are?
        self._msgin = msg
        self._arguments.clear()
        if not msg.arguments: return
        for arg in msg.arguments: self._arguments[arg] = msg.arguments[arg] # copy arguments
        return

    def get_msg(self):
        ''' Docstring '''
        return self._msgout

    def get_device(self, device_id=None, yxc_id=None, raises=False):
        ''' Returns the Device object from its id.'''
        if device_id:
            try: return self._devices_by_id[device_id]
            except KeyError: err = ''.join(('Device id <', str(device_id), '> not found.'))
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

        FEATURE?: this method could take the value of the argument sought. If None, look for it in
        the dictionary, if not None then check for its validity against the features.
        '''
        try: return self._arguments[arg]
        except KeyError: raise mcx.LogicError(''.join(('No argument <', arg, '> found.')))

    def execute_action(self, zone, action):
        ''' docstring'''
        # TODO: implement
        # retrieve the function to execute for this action
        try: func = ACTIONS[action]
        except KeyError: # the action is not found
            errtxt = ''.join(('Action ', action, ' not found.'))
            _logger.info(errtxt)
            return

        # execute the function in the zone
        try: func(zone)
        except mcx.AnyError as err:
            _logger.info(''.join(('Can\'t execute command. Error:\n\t', repr(err))))

        return

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

        event = mcc.get_event()
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

    def refresh(self):
        ''' Performs various periodic checks and refreshers on all devices.'''
        for dev in self.mcdevices: dev.refresh()

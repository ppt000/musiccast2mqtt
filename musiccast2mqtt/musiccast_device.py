'''


Assumptions on Devices:
- the gateway knows NOTHING about the state of non MusicCast at any point in time; their state can
  change without the gateway knowing and their state at startup is unknown.
'''
import time
import musiccast2mqtt.musiccast_exceptions as mcx
import musiccast2mqtt.musiccast_comm as mcc
from musiccast2mqtt.musiccast_input import Feed, Source
from musiccast2mqtt.musiccast_zone import Zone

import mqttgateway.utils.app_properties as app
_logger = app.Properties.get_logger(__name__)


_INIT_LAG = 600 # seconds, time between re-trials to initialise MusicCast devices
_BUFFER_LAG = 5 # seconds, minimum lag between a request and a status refresh
_STALE_CONNECTION = 300 # seconds, maximum time of inactivity before Yamaha API stops sending events

class Device(object):
    ''' Represents a device in the audio-video system.

    Most methods are used by the lambdas to deal with the incoming events.

    Args:
        device_data (JSON string): a JSON type string representing a device.
        system (System object): the parent system of this device.
    '''

    def __init__(self, device_data, system):
        self.system = system
        self.id = device_data['id']
        self._model = device_data.get('model', None)
        self._protocol = device_data.get('protocol', None)
        self.gateway = device_data.get('gateway', None)
        self.musiccast = (self._protocol == 'YEC')
        if self.musiccast: self._host = device_data['host']
        else: self._host = device_data.get('host', None)
        # Load the feeds, sources and zones from the static data. Zones need to be done at the end.
        feeds = []
        for feed_data in device_data['feeds']: feeds.append(Feed(feed_data, self))
        self.feeds = tuple(feeds)
        sources = []
        for source_data in device_data['sources']: sources.append(Source(source_data, self))
        self.sources = tuple(sources)
        self.inputs = self.feeds + self.sources
        if not self.inputs:
            raise mcx.ConfigError(''.join(('Device <', self.id, '> has no inputs.')))
        self._sources_d = {src.id:src for src in self.sources}
        self._inputs_d = {src.id:src for src in self.sources}
        self._inputs_d.update({feed.id:feed for feed in self.feeds})
        # TODO: enforce in schema that a device needs to have at least one input.
        zones = []
        for zone_data in device_data['zones']: zones.append(Zone(zone_data, self))
        self.zones = tuple(zones)
        # MusicCast related attributes
        if self.musiccast:  # this is a MusicCast device
            self._ready = False
            self._load_time = 0 # time when load_musiccast was last called
            self.conn = mcc.musiccastComm(self._host)
            self._dev_info = None
            self._features = None
            # dictionaries to help the event processor, initialised in load_musiccast
            self._mcinfotype_d = {}
            self._mczone_d = {}
            #self.mcsource_dict = {}
            # refresh related attribute
            self._zone_index = 0
            self._zone_num = len(self.zones)
        return

    def post_init(self):
        ''' Docstring'''
        for inp in self.inputs: inp.post_init()

    def is_musiccast(self, raises=False):
        ''' Tests if the device is MusicCast.

        Always returns True if the device is MusicCast.

        Args:
            raises (boolean): if True, raises an exception when device is not MusicCast, otherwise
                it just returns False.

        Returns:
            boolean: True if device is MusicCast, False if not and `raises` is False.

        Raises:
            LogicError: if the device is not ready and the `raises` argument is True.
        '''
        if self.musiccast: return True
        elif raises: raise mcx.LogicError(''.join(('The device ', self.id, ' is not MusicCast.')))
        else: return False

    def is_mcready(self, raises=False):
        ''' Tests if the device is MusicCast and ready to be operated.

        Always returns True if the device is MusicCast Ready.

        Args:
            raises (boolean): if True, raises an exception when device is not ready, otherwise
                it just returns False.

        Returns:
            boolean: True if device is ready, False if not and `raises` is False.

        Raises:
            LogicError: if the device is not ready and the `raises` argument is True.
        '''
        if self.musiccast and self._ready: return True
        elif raises: raise mcx.LogicError(''.join(('The device ', self.id, ' is not available.')))
        else: return False

    def load_musiccast(self):
        '''Initialisation of MusicCast related characteristics.

        This method will make HTTP requests to all relevant devices,  In case of failure, the device
        `_ready` attribute is simply left `False` and the device will not be available to be
        operated. This method can be called again at any time to try again this initialisation.

        Returns:
            boolean: True if initialisation succeeded
        '''
        if self._ready: return True # ready already!
        self._load_time = time.time()
        try:
            # Retrieve the device infos
            if not self._dev_info:
                self._dev_info = self.conn.mcrequest('system', 'getDeviceInfo')
            # Retrieve the device features
            if not self._features:
                self._features = self.conn.mcrequest('system', 'getFeatures')
            for zone in self.zones:
                zone.load_musiccast()
                self._mczone_d[zone.mcid] = zone
            for source in self.sources:
                source.load_musiccast()
        except mcx.CommsError as err:
            _logger.info(''.join(('Cannot initialise MusicCast device <', self.id,
                                  '>. Error:\n\t', repr(err))))
            return False
        except mcx.ConfigError as err:
            # These are unrecoverable errors # TODO: check if that is True; what do we do then?
            _logger.info(''.join(('MusicCast device ', self.id,
                                  ' has to be disabled. Error:\n\t', repr(err))))
            return False
        # success
        self._ready = True
        _logger.debug(''.join(('MusicCast initialisation of device <', self.id, '> successful.')))
        return True

    #===============================================================================================
    # def get_input(self, input_id):
    #     ''' Returns the Source or Feed object by their id.'''
    #     try: return self._inputs_d[input_id]
    #     except KeyError:
    #         raise mcx.ConfigError(''.join(('Input <', input_id,
    #                                        '> not found in device <', self.id, '>.')))
    #===============================================================================================

    def get_yxcid(self, raises=False):
        ''' Returns the Yamaha device id, if it exists.'''
        if not self.is_mcready(raises): return None
        try: return self._dev_info['device_id']
        except KeyError:
            if raises: raise mcx.ConfigError('No device_id in getFeatures.')
            else: return None

    def get_zone(self, zone_id=None, zone_mcid=None, raises=False):
        ''' Docstring'''
        if zone_id is None and zone_mcid is None:
            if raises: raise mcx.ConfigError('No valid Zone id arguments to get Zone.')
            else: return None
        for zone in self.zones:
            if zone.is_zone_id(zone_id=zone_id, zone_mcid=zone_mcid, raises=False):
                return zone
        if raises:
            raise mcx.ConfigError(''.join(('No Zone found with id ',
                                           zone_id if zone_id else zone_mcid, '.')))
        else:
            return None

    def sources_by_id(self):
        ''' Returns the dictionary id -> Source'''
        return self._sources_d

    def get_feature(self, flist):
        ''' Returns a branch from the getFeatures tree.
        
        This method retrieves a branch or leaf from a JSON type object.
        The argument is a list made of strings and/or pairs of string.
        For each string, the method expect to find a dictionary as the next branch,
        and selects the value (which is another branch or leaf) returned by that string as key.
        For each pair (key, value), it expects to find an array of similar objects, and in that case it
        searches for the array that contains the right 'value' for that 'key'.
        '''
        branch = self._features
        if isinstance(flist, basestring): # Python 3: isinstance(arg, str)
            flist = (flist,)
        for arg in flist:
            if isinstance(arg, basestring):
                try: branch = branch[arg]
                except KeyError:
                    raise mcx.ConfigError(''.join(('Argument <', str(arg),
                                                   '> not found in current branch: ',
                                                   str(branch))))
                except TypeError:
                    raise mcx.CommsError(''.join(('The current branch is not a dictionary: ',
                                                  str(branch))))
            else: # assume arg is a pair (key, value)
                try:
                    key = arg[0]
                    value = arg[1]
                except (IndexError, TypeError):
                    raise ValueError(''.join(('Argument <', str(arg), '> should be a pair.')))
                found = False
                for obj in branch: # assume branch is an array
                    try: found = (obj[key] == value)
                    except KeyError:
                        raise mcx.ConfigError(''.join(('Key <', str(key),
                                                       '> not found in current branch: ',
                                                       str(branch))))
                    except TypeError:
                        raise mcx.CommsError(''.join(('The current branch is not a dictionary: ',
                                                      str(branch))))
                    if found: break
                if not found:
                    raise mcx.ConfigError(''.join(('Value <', str(value),
                                                   '> for key <', str(key),
                                                   '> not found in array.')))
                branch = obj
        return branch

    def init_infotype(self, play_info_type):
        ''' Returns a new or an existing instance of PlayInfoType.

        For each type there is only one instance of the corresponding class.

        Args:
            play_info_type (string): one of **tuner**, **cd**, or **netusb**.

        Raises:
            ConfigError: if the play_info_type is not recognised.
        '''
        if play_info_type in self._mcinfotype_d:
            return self._mcinfotype_d[play_info_type]
        if play_info_type == 'tuner':
            self._mcinfotype_d[play_info_type] = Tuner(self)
            return self._mcinfotype_d[play_info_type]
        elif play_info_type == 'cd':
            self._mcinfotype_d[play_info_type] = CD(self)
            return self._mcinfotype_d[play_info_type]
        elif play_info_type == 'netusb':
            self._mcinfotype_d[play_info_type] = NetUSB(self)
            return self._mcinfotype_d[play_info_type]
        else:
            raise mcx.ConfigError(''.join(('PlayInfoType <', play_info_type, '> does not exist.')))

    def find_infotype(self, play_info_type):
        ''' Retrieves the info_type instance.

        Only used (for now) by the event lambdas.
        '''
        try: return self._mcinfotype_d[play_info_type]
        except KeyError:
            raise mcx.ConfigError(''.join(('InfoType <', play_info_type, '> not found.')))

    def find_mczone(self, mcid):
        ''' Returns the MusicCast zone from its id.
        
        CHECK: this is redundant with get_zone().

        Needed by the event processor, it is called by the lambdas.

        Args:
            mcid (string): MusicCast id of the zone.  Normally one of 'main,
                zone2, zone3, zone4'.  See list _ZONES.

        Raises:
            ConfigError: if the zone is not found, either because it is not a
                valid zone or because it does not exist in this device.
        '''
        try: return self._mczone_d[mcid]
        except KeyError:
            raise mcx.ConfigError(''.join(('MusicCast zone <', mcid, '> not found in device <',
                                           self.id, '>.')))

    def get_input(self, input_id=None, input_mcid=None):
        ''' Returns the Input object from its id or mcid.

        If input_id is present, then it is used, otherwise input_mcid is used.
        '''
        if input_id is not None:
            try: return self._inputs_d[input_id]
            except KeyError:
                raise mcx.ConfigError(''.join(('Input <', input_id, '> not found in device <',
                                               self.id, '>.')))
        elif input_mcid is not None:
            if not self.musiccast:
                raise mcx.LogicError(''.join(('Can not find MusicCast input <', input_mcid,
                                              '> on non-MusicCast device <', self.id, '>.')))
            # TODO: make a dictionary to find the MusicCast input out of its MusicCast id.
            for inp in self.inputs:
                if inp.mcid == input_mcid: return inp
            raise mcx.ConfigError(''.join(('MusicCast input <', input_mcid,
                                           '> not found in device <', self.id, '>.')))
        else:
            raise mcx.ConfigError(''.join(('No valid arguments in get_input() on device <',
                                           self.id, '>.')))

    def refresh(self):
        ''' Refresh status of device.

        There are 2 reasons why one needs to refresh the status of a device:

        1- because the MusicCast devices need to receive at least one request every 10 minutes (with
        the right headers) so that they keep sending events;

        2- because this gateway has sent a **set** command and it is good to check if the command
        has indeed *delivered*.  It seems though that one needs to wait a bit before requesting
        a fresh status as experience shows that firing a **getStatus** request straight after a
        command does not reflect the change even if the command is supposed to be successful.

        '''
        now = time.time()
        # check if the device is online
        if not self._ready: # try to initialise MusicCast device at regular intervals
            if now - self._load_time > _INIT_LAG:
                self.load_musiccast()
            return # return anyway. at best the device just went ready, at worst it failed again.
        # check if a request has been made *too* recently
        if now - self.conn.request_time < _BUFFER_LAG:
            return
        # check now if there are zones that have requested a status refresh
        for _count in range(self._zone_num):
            zone = self.zones[self._zone_index]
            self._zone_index = (self._zone_index + 1) % self._zone_num
            if zone.status_requested: # status refresh has been requested
                _logger.debug('Refresh status on request.')
                zone.refresh_status()
                return
        # check if it is time to refresh the device so it keeps sending the events
        if now - self.conn.request_time > _STALE_CONNECTION:
            _logger.debug('Refreshing the connection after long inactivity.')
            zone = self.zones[self._zone_index]
            self._zone_index = (self._zone_index + 1) % self._zone_num
            zone.refresh_status()
            return

class PlayInfoType(object):
    '''Represents information that is not source specific in Yamaha API.

    Some of the information about sources in MusicCast devices are only available for groups of
    sources, and not source by source.  This is true for the **netusb** type, which covers a wide
    range of sources (*server*, *net_radio*, and all streaming services).  This information can not
    be stored on a source by source basis but in an ad-hoc structure that sources will link to.
    For any device, there can be only one instance of each type (**cd**, **tuner** and **netusb**)
    so the instantiation of these classes is triggered by the Source object initialisation, that
    finds out of what type it is and then calls a sort of factory method within the parent Device
    object that then decides to instantiate a new object if it does not exist yet or returns the
    existing object (a sort of singleton pattern).

    Args:
        play_info_type (string): one of **tuner**, **cd**, or **netusb**.
        device (Device object): parent device of the source.
    '''

    def __init__(self, play_info_type, device):
        self.type = play_info_type
        self.device = device
        self.play_info = None
        self._preset_separate = False
        self._max_presets = 0

    def update_play_info(self):
        ''' Retrieves the play_info structure.

        The sources involved in this command are **tuner**, **cd**, and all
        sources part of the **netusb** group.
        '''
        self.play_info = self.device.conn.mcrequest(self.type, 'getPlayInfo')

    def update_preset_info(self):
        ''' Retrieves the preset_info structure.

        The `getPresetInfo` request involves only types **tuner** and **netusb**. Treatment in
        either case is different, see the Yamaha doc for details.
        '''
        raise mcx.LogicError(''.join(('Type <', self.type, '> does not have preset info.')))

    def update_play_time(self, value):
        ''' Updates the play_time attribute with the new value.

        Only concerns MusicCast types **cd** and **netusb**.
        The **play_time** event get sent every second by MusicCast devices
        once a cd or a streaming service starts playing.  Maybe it is not
        necessary to process it every second.

        Args:
            value (integer in string form): the new value of play_time.
        '''
        raise mcx.LogicError(''.join(('Type <', self.type, '> does not have play time info.')))

    def update_play_message(self, value):
        ''' Updates the play_message attribute with the new value.

         This event only applies to the **netusb** group.

        Args:
            value (string): the new value of play_message.
        '''
        raise mcx.LogicError(''.join(('Type <', self.type, '> does not have play message info.')))

    def get_preset_arguments(self, source, preset_num):
        ''' docstring.'''
        raise mcx.LogicError(''.join(('Source ', source.mcid, ' does not have presets.')))

class Tuner(PlayInfoType):
    ''' Tuner specific information.

    Args:
        device (Device object): parent device.
    '''

    def __init__(self, device):
        super(Tuner, self).__init__('tuner', device)
        # Resolve the _preset_separate and the _info_bands
        preset_type = self.device.get_feature(('tuner', 'preset', 'type'))
        if preset_type == 'separate': self._preset_separate = True
        else: self._preset_separate = False
        if self._preset_separate:
            func_list = self.device.get_feature(('tuner', 'func_list'))
            self._info_bands = [band for band in func_list if band in ('am', 'fm', 'dab')]
        # load the max_preset
        try: self._max_presets = int(self.device.get_feature(('tuner', 'preset', 'num')))
        except ValueError:
                raise mcx.CommsError('getFeatures item <max_presets> not an int.')
        # Load the preset_info
        self._preset_info = None
        self.update_preset_info()
        return

    def update_preset_info(self):
        ''' Retrieves the preset_info structure.

        Info type == **tuner**: the request requires a `band` argument that depends on the
        features of the device.  As the structure returned by the request is a list of objects that
        always include the band that the preset relates to, we can concatenate all the preset lists.
        '''

        if self._preset_separate:
            preset_info = []
            for band in self._info_bands:
                response = self.device.conn.mcrequest('tuner',
                                                      ''.join(('getPresetInfo?band=', band)))
                try: preset_info.extend(response['preset_info'])
                except KeyError:
                    raise mcx.CommsError('getPresetInfo did not return a preset_info field.')
            self._preset_info = preset_info # update attribute only after all worked properly
        else:
            response = self.device.conn.mcrequest('tuner', 'getPresetInfo?band=common')
            try: self._preset_info = response['preset_info']
            except KeyError:
                raise mcx.CommsError('getPresetInfo did not return a preset_info field.')
        return

    def get_preset_arguments(self, source, preset_num):
        ''' docstring.'''
        args={}
        if self._preset_separate:
            args['band'] = 'dab' # for now that's the only preset we want to use.
            # TODO: include other bands selection.
        else: args['band'] = 'common'
        if preset_num < 1 or preset_num > self._max_presets:
            raise mcx.LogicError(''.join(('Preset ', str(preset_num), ' is out of range.')))
        args['preset_num'] = str(preset_num)
        return args

class CD(PlayInfoType):
    ''' CD specifc information.

    Args:
        device (Device object): parent device.
    '''

    def __init__(self, device):
        super(CD, self).__init__('cd', device)
        self._play_time = '0'

    def update_play_time(self, value):
        ''' Updates the play_time attribute with the new value.

        Args:
            value (integer in string form): the new value of play_time.
        '''
        self._play_time = value

class NetUSB(PlayInfoType):
    '''NetUSB specific information.
    Args:
        device (Device object): parent device.
    '''
    def __init__(self, device):
        super(NetUSB, self).__init__('netusb', device)
        self._preset_info = None
        self._play_time = '0'
        self._play_message = ''
        # load the max_preset
        try: self._max_presets = int(self.device.get_feature(('netusb', 'preset', 'num')))
        except ValueError:
                raise mcx.CommsError('getFeatures item <max_presets> not an int.')
        # Load the preset_info
        self._preset_info = None
        self.update_preset_info()
        return

    def update_preset_info(self):
        ''' Retrieves the preset_info structure.

        Info type == **netusb**: the request is sent *as is* and the structure
        returned includes a list of objects where one of fields indicates the
        input that the preset relate to (I am not sure what the input can be
        anything else that **net_radio** though).
        '''
        self._preset_info = self.device.conn.mcrequest(self.type, 'getPresetInfo')

    def update_play_time(self, value):
        ''' Updates the play_time attribute with the new value.

        Note: There is an uncertainty on which source is playing when the type is **netusb**.  The
        event does not give any extra information.  It probably means that there can only be one
        source that can play at any given time in the **netusb** group, even if there are multiple
        zones in the device.

        Args:
            value (integer in string form): the new value of play_time.
        '''
        self._play_time = value

    def update_play_message(self, value):
        ''' Updates the play_message attribute with the new value.

        Args:
            value (string): the new value of play_message.
        '''
        self._play_message = value
        return

    def get_preset_arguments(self, source, preset_num):
        ''' docstring'''
        args = {}
        if source.mcid == 'net_radio': args['band'] = ''
        else: # source.mcid not 'net_radio'
            raise mcx.LogicError(''.join(('Source ', source.mcid, ' does not have presets.')))
        if preset_num < 1 or preset_num > self._max_presets:
            raise mcx.LogicError(''.join(('Preset ', str(preset_num), ' is out of range.')))
        args['preset_num'] = str(preset_num)
        return args

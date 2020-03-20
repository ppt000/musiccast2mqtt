''' Representation of a zone.

.. reviewed --

Assumptions on Zones:

- all MusicCast zones have always a valid input assigned (even when off).

'''

import time
import logging

import musiccast2mqtt as mcc

LOG = logging.getLogger(__name__)

class Zone(object):
    ''' Represents a zone on the device.

    Args:
        zone_data (dictionary): the zone data returned from the getFeatures call to the API
        device (:class:`Device`): the parent device.
    '''

    def __init__(self, zone_data, device):
        try: self.zone_mcid = zone_data['id']
        except KeyError: raise mcc.CommsError('getFeatures does not have the expected structure.')
        self.device = device
        self._zone_mcrename = None
        self._zone_friendly = None
        self._zone_location = None

        self._power = False
        self._volume = 0
        self._mute = False
        self._status = {}
        self._status_time = 0 # time of last successful status request
        self.status_requested = False # set to True if the status needs to be refreshed

        self.current_input = None      # will be updated with the first status refresh here below

        self._response = ''
        self._reason = ''

        volume_data = self.device.get_feature(('zone', {'id': self.zone_mcid},
                                               'range_step', {'id': 'volume'}))
        self._volume_min = volume_data['min']
        self._volume_max = volume_data['max']
        self._volume_step = volume_data['step']
        self._volume_range = self._volume_max - self._volume_min

        self.refresh_status()
        return

    def name(self):
        ''' Returns a friendly name for the zone.'''
        return str(self.zone_mcid)

    def _get_dict_item(self, dico, key):
        ''' Retrieves the item in the dictionary.

        This is a safety method in case a structure sent back by MusicCast
        does not have the item expected.  It catches the KeyError exception
        and changes it into a CommsError one.

        Args:
            dico (dict): the dictionary to look into
            item (string): the key to look for
        '''
        try: return dico[key]
        except KeyError:
            raise mcc.CommsError(''.join(('The dictionary provided by device <', self.device.name(),
                                          '> does not contain the item <', key, '>')))

    def _transform_arg(self, key, invalue=None, mcvalue=None):
        '''Transforms a message argument from/to internal to/from MusicCast.

        This method goes hand in hand with the TRANSFORM_ARG dictionary.

        Args:
            key (string): internal name of argument.
            invalue (string): the internal value to be transformed; if provided the transformation
              is done from this value to the MusicCast value, which is returned.
            mcvalue (string): the MusicCast value to be transformed; relevant only if ``invalue`` is
              None, in which case the transformation is done from this value to the
              internal value, which is returned.

        Returns:
            string: the transformed representation of the value.
        '''
        try: func = TRANSFORM_ARG[key] # Retrieve the transformation lambdas
        except KeyError:
            raise mcc.LogicError(''.join(('Argument ', str(key), ' has no transformation.')))
        if invalue is not None: # transform from internal to MusicCast
            value = invalue
            trsfrm = 0
        elif mcvalue is not None: # transform from MusicCast to internal
            value = mcvalue
            trsfrm = 1
        else:
            raise mcc.ConfigError(''.join(('No valid parameters to transform <', str(key),
                                           '> on zone <', self.name(), '> of device <',
                                           self.device.name(), '>.')))
        try: trsfrm_value = func[trsfrm](self, value)
        except (TypeError, ValueError) as err: # errors to catch in case of bad format
            raise mcc.LogicError(''.join(('Value ', str(value), ' of argument ', str(key),
                                          ' seems of the wrong type. Error:\n\t', str(err))))
        return trsfrm_value

    def execute_action(self, msg):
        ''' Executes the action requested in the message

        This method relies on the ACTIONS dictionary to produce the lambda to execute.

        Args:
            msg (:py:class:internalMsg): internal message

        Raises:
            LogicError, ConfigError, CommsError: in case of error in executing the lambdas
        '''
        action = msg.action
        LOG.debug(''.join(('Execute action <', action, '> on zone <', self.name(),
                               '> of device <', self.device.name(), '>.')))
        self._response = ''
        self._reason = ''
        try: # retrieve the function to execute for this action
            func = ACTIONS[action]
        except KeyError: # the action is not found
            raise mcc.LogicError(''.join(('Action ', action, ' not found.')))
        func(self) # execute the function in the zone
        return self._response, self._reason

    def refresh_status(self):
        ''' Retrieve the state of the zone and store it locally.'''
        self._status = self.device.conn.mcrequest(self.zone_mcid, 'getStatus')
        self._status_time = time.time() # record time of refresh
        self.update_power(mcvalue=self._get_dict_item(self._status, 'power'))
        self.update_volume(mcvalue=self._get_dict_item(self._status, 'volume'))
        self.update_mute(mcvalue=self._get_dict_item(self._status, 'mute'))
        self.update_input(mcvalue=self._get_dict_item(self._status, 'input'))
        self.status_requested = False
        return

    def update_power(self, mcvalue):
        ''' Updates internal state of zone after change in power state.

        Args:
            invalue (boolean): the new value of the power state
            mcvalue (string): "on" or "standby"

        Returns:
            Boolean: True if there is a change.
        '''
        power = self._transform_arg('power', mcvalue=mcvalue)
        if self._power == power: return False # do nothing if no change
        LOG.info(''.join(('Power from <', str(self._power), '> to <', str(power), '>.')))
        self._power = power
        return True

    def set_power(self, power):
        ''' Sets the power of the zone.

        Args:
            power (boolean): converted into 'on' or 'standby'.
        '''
        self.device.is_ready(raises=True)
        mc_power = self._transform_arg('power', invalue=power)
        cmdtxt = 'setPower?power={}'.format(mc_power)
        self.device.conn.mcrequest(self.zone_mcid, cmdtxt)
        self.update_power(mcvalue=mc_power)
        self.status_requested = True
        self._response = 'OK'
        self._reason = ''.join(('power is ', mc_power))
        return

    def is_power_on(self, raises=False):
        ''' Helper function to test if power of zone is ON.

        Always returns True if the zone is ON.

        Args:
            raises (boolean): if True, raises an exception when zone is OFF, otherwise
                it just returns False.

        Returns:
            boolean: True if zone is ON, False if not and `raises` is False.

        Raises:
            LogicError: if the zone is OFF and the `raises` argument is True.
        '''
        self.device.is_ready(raises=True)
        if self._power: return True
        elif raises:
            raise mcc.LogicError(''.join(('The zone ', self.name(),
                                          ' of device ', self.device.name(), ' is not turned on.')))
        else: return False

    def update_volume(self, mcvalue=None):
        ''' Updates internal state of zone after change in volume.

        Args:
            invalue (int): the new value of the volume in internal metric
            mcvalue (int): the new value of the volume in MusicCast metric

        Returns:
            Boolean: True if there is a change.
        '''
        volume = self._transform_arg('volume', mcvalue=mcvalue)
        if self._volume == volume: return False # do nothing if no change
        LOG.info(''.join(('Volume from <', str(self._volume), '> to <', str(volume), '>.')))
        self._volume = volume
        return True

    def set_volume(self, vol_up=None):
        ''' Sets the volume of the zone.

        Args:
            vol_up (boolean): if given defines if volume is stepped up or down, if
              not then the volume to set has to be in the arguments.
        '''
        self.device.is_ready(raises=True)
        self.is_power_on(raises=True)
        if vol_up is None:
            # retrieve the volume in the arguments; cast it to int just in case it's a string
            try: volume = int(self.device.get_argument('volume'))
            except (TypeError, ValueError): raise mcc.LogicError('Invalid volume argument')
            # TODO: check that volume is within range (0-100?)
            mc_volume = self._transform_arg('volume', invalue=volume)
            mc_volume = min(max(mc_volume, self._volume_min),
                            (self._volume_min + self._volume_range))
            self.device.conn.mcrequest(self.zone_mcid, ''.join(('setVolume?volume=',
                                                                str(mc_volume))))
        else:
            self.device.conn.mcrequest(self.zone_mcid, ''.join(('setVolume?volume=',
                                                                'up' if vol_up else 'down')))
            # calculate volume level to update locally
            mc_volume = self._transform_arg('volume', invalue=self._volume)
            # mc_volume is an int
            mc_volume += (1 if vol_up else -1) * self._volume_step
            mc_volume = min(max(mc_volume, self._volume_min),
                            (self._volume_min + self._volume_range))
            volume = self._transform_arg('volume', mcvalue=mc_volume)
        self.update_volume(mcvalue=mc_volume)
        self.status_requested = True
        self._response = 'OK'
        self._reason = ''.join(('volume is ', str(volume)))
        return

    def update_mute(self, mcvalue=None):
        ''' Updates internal state of zone after change in mute state.

        Args:
            mcvalue (string): "true" or "false"

        Returns:
            Boolean: True if there is a change.
        '''
        mute = self._transform_arg('mute', mcvalue=mcvalue)
        if self._mute == mute: return False # do nothing if no change
        self._mute = mute
        LOG.info(''.join(('Mute from <', str(self._mute), '> to <', str(mute), '>.')))
        return True

    def set_mute(self, mute):
        ''' Sets the mute property of the zone.

        Args:
            mute (boolean): converted into 'true' or 'false'
        '''
        self.device.is_ready(raises=True)
        self.is_power_on(raises=True)
        mc_mute = self._transform_arg('mute', invalue=mute)
        self.device.conn.mcrequest(self.zone_mcid, ''.join(('setMute?enable=', mc_mute)))
        self.update_mute(mc_mute)
        self.status_requested = True
        self._response = 'OK'
        self._reason = ''.join(('mute is ', mc_mute))
        return

    def update_input(self, mcvalue):
        ''' Updates internal value of input object after change in input.

        Args:
            mcvalue(string): a valid Input MusicCast id

        Returns:
            Boolean: True if there is a change.
        '''
        new_input = self.device.get_input(input_mcid=mcvalue, raises=False)
        if new_input is None: # the input does not exist in this device
            return False
        # the following line crashes because current_input = None the first time
        #LOG.info(''.join(('Input from <', self.current_input.input_mcid,
        #                      '> to <', mcvalue, '>.')))
        self.current_input = new_input
        return True

    def set_input(self, input_mcid=None):
        ''' Sets the input of the zone.

        This method simply switches the input of the current zone.  It does not matter if the input
        is a source or not.  No other action is performed, so if for example the input is a source
        on the same device and it needs to be started or tuned, this is not done here.

        Args:
            input_mcid (string): input internal identifier
        '''
        # Find the actual Input object in the device from its input_mcid
        if input_mcid is None: input_mcid = self.device.get_argument('input')
        inp = self.device.get_input(input_mcid=input_mcid, raises=True)
        self.device.is_ready(raises=True)
        self.is_power_on(raises=True)
        self.device.conn.mcrequest(self.zone_mcid, ''.join(('setInput?input=', inp.input_mcid)))
        self.update_input(input_mcid)
        self.status_requested = True
        self._response = 'OK'
        self._reason = ''.join(('input is ', inp.id))
        return

    def get_inputs(self):
        ''' docstring

        '''
        # TODO: implement
        self._response = 'this,should,be,a,list,of,valid,inputs'
        self._reason = 'for now it does not work'
        return

    def get_sources(self):
        ''' docstring

        '''
        # TODO: implement
        self._response = 'this,should,be,a,list,of,valid,sources'
        self._reason = 'for now it does not work'
        return

    def set_playback(self, mc_action, src_mcid=None):
        '''Triggers the specified play-back action.

        To be able to play a source, it has to be selected first.

        Args:
            action (string): the action to send to the MusicCast device.
            src_mcid (string): the MusicCast keyword of the source to be
                played, if supplied, otherwise it is expected to be in the
                arguments.
        '''
        self.device.is_ready(raises=True)
        self.is_power_on(raises=True)
        # Resolve the source and check it is the one playing
        if src_mcid is None: src_mcid = self.device.get_argument('source')
        source = self.current_input
        if src_mcid != source.input_mcid:
            raise mcc.LogicError(''.join(('Can not operate source <', src_mcid,
                                          '> while device <', self.device.name(),
                                          '> is playing <', source.input_mcid, '>.')))
        # Send command
        self.device.conn.mcrequest(source.playinfo_type.type,
                                   ''.join(('setPlayback?playback=', mc_action)))
        #control_zone.send_reply('OK', ''.join(('playback set to ', action)))
        return

    def set_preset(self, src_mcid=None):
        '''Set the preset specified in the arguments for the source.

        Args:
            source_id (string): the MusicCast keyword of the source to be
                preset, if supplied, otherwise it is expected to be in the
                arguments.  It can only be **tuner** or **netusb**.
        '''
        self.device.is_ready(raises=True)
        self.is_power_on(raises=True)
        # Resolve the source and check it is the one playing
        if src_mcid is None: src_mcid = self.device.get_argument('source')
        src = self.current_input
        if src_mcid != src.input_mcid:
            raise mcc.LogicError(''.join(('Can''t preset <', src_mcid,
                                          '> while device <', self.device.name(),
                                          ' is playing input <', src.input_mcid, '>.')))
        # Retrieve the number of the preset.
        try: preset_num = int(self.device.get_argument('preset'))
        except (KeyError, ValueError):
            raise mcc.LogicError('No valid preset argument found.')
        # The command format depends on the source
        qualifier = src.playinfo_type.type
        args = src.playinfo_type.get_preset_arguments(src, preset_num)
        cmdtxt = 'recallPreset?zone={}&band={}&num={}'.format(self.zone_mcid,
                                                              args['band'], args['preset_num'])
        self.device.conn.mcrequest(qualifier, cmdtxt) # Send the command
        #ctrl_zone.send_reply('OK', ''.join(('preset ', src.input_mcid,
        #                                    ' to number ', str(preset_num))))
        return

    def str_status(self):
        ''' Returns the full status dictionary.'''
        return ''.join(([''.join(('\n\t\t\t', key, ': ', str(self._status[key])))
                         for key in self._status]))

    def str_zone(self):
        '''Returns the identification of a zone.'''
        return ''.join((self.device.name(), '.', self.name()))

    def dump_zone(self):
        '''Returns most characteristics of a zone.'''
        lst = []
        lst.append('ZONE ')
        lst.append(self.str_zone())
        #lst.append('\n\tZonesource present: ')
        #lst.append('Yes' if self.zonesource else 'No')
        #if self.zonesource:
        #    lst.append('\n\t\tZonesource is: ')
        #    lst.append(self.zonesource.str_zone())
        lst.append('\n\t\tMusicCast id: ')
        lst.append(str(self.zone_mcid))
        lst.append('\n\t\tState is')
        lst.append(self.str_status())
        return ''.join(lst)

# pylint: disable=bad-whitespace
TRANSFORM_ARG = { # [0]=internal->musiccast, [1]=musiccast->internal
    'power':    (lambda self, value: 'on' if value else 'standby',
                 lambda self, value: value == 'on'),
    'mute':     (lambda self, value: 'true' if value else 'false',
                 lambda self, value: value == 'true'),
    'volume':   (lambda self, value: int(int(value) * self._volume_range / 100),
                 lambda self, value: int(int(value) * 100 / self._volume_range)),
    # Assume same names between internal and MusicCast, for now
    'input':    (lambda self, value: value,
                 lambda self, value: value),
    # Assume same names between internal and MusicCast, for now
    'source':   (lambda self, value: value,
                 lambda self, value: value),
    # Assume same names between internal and MusicCast, for now
    'action':   (lambda self, value: value,
                 lambda self, value: value),
    # Assume same names between internal and MusicCast, for now
    'preset':   (lambda self, value: value,
                 lambda self, value: value),
    }
'''
Transforms arguments from internal keyword to MusicCast keyword and back.

The value for each key is a pair of lambdas; the first one transforms its arguments
from internal representation to Musiccast, and the second one does the reverse.
The lambdas have to be called by a :class:`Zone` object.
'''

ACTIONS = {
    'POWER_OFF':        lambda self: self.set_power(False),
    'POWER_ON':         lambda self: self.set_power(True),
    'SET_VOLUME':       lambda self: self.set_volume(),
    'VOLUME_UP':        lambda self: self.set_volume(vol_up=True),
    'VOLUME_DOWN':      lambda self: self.set_volume(vol_up=False),
    # TODO: implement VOLUME_UP and DOWN with step...
    'MUTE_ON':          lambda self: self.set_mute(True),
    'MUTE_OFF':         lambda self: self.set_mute(False),
    'MUTE_TOGGLE':      lambda self: self.set_mute(not self._mute),
    'GET_INPUTS':       lambda self: self.get_inputs(),
    'SET_INPUT':        lambda self: self.set_input(),
    'INPUT_CD':         lambda self: self.set_input('cd'),
    'INPUT_NETRADIO':   lambda self: self.set_input('net_radio'),
    'INPUT_TUNER':      lambda self: self.set_input('tuner'),
    'INPUT_SPOTIFY':    lambda self: self.set_input('spotify'),
    'GET_SOURCES':      lambda self: self.get_sources(),
    'SET_SOURCE':       lambda self: self.set_source(),
    'SOURCE_CD':        lambda self: self.set_source('cd'),
    'SOURCE_NETRADIO':  lambda self: self.set_source('net_radio'),
    'SOURCE_TUNER':     lambda self: self.set_source('tuner'),
    'SOURCE_SPOTIFY':   lambda self: self.set_source('spotify'),
    'CD_BACK':          lambda self: self.set_playback('previous', 'cd'),
    'CD_FORWARD':       lambda self: self.set_playback('next', 'cd'),
    'CD_PAUSE':         lambda self: self.set_playback('pause', 'cd'),
    'CD_PLAY':          lambda self: self.set_playback('play', 'cd'),
    'CD_STOP':          lambda self: self.set_playback('stop', 'cd'),
    'SPOTIFY_PLAYPAUSE':lambda self: self.set_playback('play_pause', 'netusb'),
    'SPOTIFY_BACK':     lambda self: self.set_playback('previous', 'netusb'),
    'SPOTIFY_FORWARD':  lambda self: self.set_playback('next', 'netusb'),
    'TUNER_PRESET':     lambda self: self.set_preset('tuner'),
    'NETRADIO_PRESET':  lambda self: self.set_preset('net_radio')
    }
'''
The dictionary with all the data to process the various commands.

It has to be called from a :class:`Zone` object.
'''
# pylint: enable=bad-whitespace

''' Representation of a zone.

.. reviewed 31 May 2018

Assumptions on Zones:

- all MusicCast zones have always a valid input assigned (even when off).

'''

import time

import musiccast2mqtt.musiccast_exceptions as mcx
from musiccast2mqtt.musiccast_data import TRANSFORM_ARG, ACTIONS

import mqttgateway.utils.app_properties as app
_logger = app.Properties.get_logger(__name__)

class Zone(object):
    ''' Represents a zone on the device.

    Args:
        zone_data (dictionary): the **zone** characteristics.
        device (:class:`Device`): the parent device.
    '''

    def __init__(self, zone_data, device):
        self.device = device
        self.id = zone_data['id']
        self.location = zone_data['location']
        self._power = False
        self._volume = 0
        self._mute = False
        self._input = None #self.device.inputs[0] # any input will do for now
        self._input_id = '' # self._input.id
        self._amplified = (self.location != '')
        self._response = ''
        self._reason = ''
        if self.device.musiccast:
            self.mcid = zone_data['mcid']
            self._status = {}
            self._status_time = 0 # time of last successful status request
            self.status_requested = False # set to True if the status needs to be refreshed
            self._volume_range = 0
            self._volume_min = 0
            self._volume_step = 0
        return

    def load_musiccast(self):
        '''Initialisation of MusicCast related characteristics.

        This method uses the objects retrieved from previous HTTP requests.
        It can be called at any time to try again this initialisation.
        '''
        range_min = self.device.get_feature(('zone', ('id', self.mcid),
                                             'range_step', ('id', 'volume'), 'min'))
        range_max = self.device.get_feature(('zone', ('id', self.mcid),
                                             'range_step', ('id', 'volume'), 'max'))
        range_step = self.device.get_feature(('zone', ('id', self.mcid),
                                              'range_step', ('id', 'volume'), 'step'))
        self._volume_range = range_max - range_min
        self._volume_min = range_min
        self._volume_step = range_step
        # retrieve the status of the zone and store it locally
        self.refresh_status()
        return

    def is_zone_id(self, zone_id=None, zone_mcid=None, raises=False):
        ''' Returns True if the id corresponds to the current zone.

        Args:
            zone_id (string): zone id
            zone_mcid (string): zone MusicCast id
            raises (boolean): if True, an exception is raised if result is False
        '''
        if zone_id is not None:
            if self.id == zone_id: return True
            msg_id = zone_id
        elif zone_mcid is not None:
            if self.device.is_mcready(raises=False):
                if self.mcid == zone_mcid: return True
                msg_id = zone_mcid
            else: # request to check against mcid on non MusicCast Ready device
                if raises:
                    raise mcx.LogicError('Can not determine MusicCast id on non-MusicCast Ready device')
                else: return False
        else:
            if raises:
                raise mcx.ConfigError('No valid Zone id argument to check against.')
            else: return False
        if raises:
            raise mcx.ConfigError(''.join(('Zone id ', msg_id, ' does not match this zone.')))
        else:
            return False

    def _get_dict_item(self, dico, item):
        ''' Retrieves the item in the dictionary.

        This is a safety method in case a structure sent back by MusicCast
        does not have the item expected.  It catches the KeyError exception
        and changes it into a CommsError one.

        Args:
            dico (dict): the dictionary to look into
            item (string): the key to look for
        '''
        try: return dico[item]
        except KeyError:
            raise mcx.CommsError(''.join(('The dictionary provided by device <', self.device.id,
                                          '> does not contain the item <', item, '>')))

    def _get_current_input(self, raises=False):
        ''' Returns the current input in this zone or None

        Args:
            raises (boolean): if True, raises an exception if not found
        '''
        if self._input is None and raises: raise mcx.ConfigError('Input unassigned.')
        return self._input

    def _transform_arg(self, key, invalue=None, mcvalue=None):
        '''Transforms a message argument from/to internal to/from MusicCast.

        Args:

            key (string): internal name of argument.

            invalue: the internal value to be transformed; if provided the transformation
              is done from this value to the MusicCast value, which is returned.

            mcvalue: the MusicCast value to be transformed; relevant only if ``invalue`` is
              None, in which case the transformation is done from this value to the
              internal value, which is returned.

        Returns:
            string: the transformed representation of the value.
        '''
        # TODO: do we need to transform the keys as well?
        try: func = TRANSFORM_ARG[key] # Retrieve the transformation lambdas
        except KeyError:
            raise mcx.LogicError(''.join(('Argument ', str(key), ' has no transformation.')))
        if invalue is not None: # transform from internal to MusicCast
            value = invalue
            trsfrm = 0
        elif mcvalue is not None: # transform from MusicCast to internal
            value = mcvalue
            trsfrm = 1
        else:
            raise mcx.ConfigError(''.join(('No valid parameters to transform <', str(key),
                                           '> on zone <', str(self.id), '> of device <',
                                           str(self.device.id), '>.')))
        try: trsfrm_value = func[trsfrm](self, value)
        except (TypeError, ValueError) as err: # errors to catch in case of bad format
            raise mcx.LogicError(''.join(('Value ', str(value), ' of argument ', str(key),
                                          ' seems of the wrong type. Error:\n\t', str(err))))
        return trsfrm_value

    def execute_action(self, action):
        ''' Executes the action in the zone provided

        Args:
            action (string): action name in internal vocabulary
        '''
        _logger.debug(''.join(('Execute action <', action, '> on zone <', self.id,
                               '> of device <', self.device.id, '>.')))
        self._response = ''
        self._reason = ''
        # retrieve the function to execute for this action
        try: func = ACTIONS[action]
        except KeyError: # the action is not found
            raise mcx.LogicError(''.join(('Action ', action, ' not found.')))
        # execute the function in the zone
        func(self)
        # Return reply
        return self._response, self._reason

    def refresh_status(self):
        ''' Retrieve the state of the zone and store it locally.'''
        self.device.is_musiccast(raises=True)
        self._status = self.device.conn.mcrequest(self.mcid, 'getStatus')
        self._status_time = time.time() # record time of refresh
        self.update_power(mcvalue=self._get_dict_item(self._status, 'power'))
        self.update_volume(mcvalue=self._get_dict_item(self._status, 'volume'))
        self.update_mute(mcvalue=self._get_dict_item(self._status, 'mute'))
        self.update_input(mcvalue=self._get_dict_item(self._status, 'input'))
        self.status_requested = False

    def update_power(self, invalue=None, mcvalue=None):
        ''' Updates internal state of zone after change in power state.

        Args:
            invalue (boolean): the new value of the power state
            mcvalue (string): "on" or "standby"

        Returns:
            Boolean: True if there is a change.
        '''
        if invalue is None: power = self._transform_arg('power', mcvalue=mcvalue)
        else: power = invalue
        if self._power == power: return False# do nothing if no change
        # do something here if needed
        _logger.info(''.join(('Power from <', str(self._power), '> to <', str(power), '>.')))
        self._power = power
        return True

    def set_power(self, power):
        ''' Sets the power of the zone.

        Args:
            power (boolean): converted into 'on' or 'standby'.
        '''
        self.device.is_mcready(raises=True)
        mc_power = self._transform_arg('power', invalue=power)
        cmdtxt = 'setPower?power={}'.format(mc_power)
        self.device.conn.mcrequest(self.mcid, cmdtxt)
        self.update_power(invalue=power)
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
        self.device.is_mcready(raises=True)
        if self._power: return True
        elif raises:
            raise mcx.LogicError(''.join(('The zone ', self.id,
                                          ' of device ', self.device.id, ' is not turned on.')))
        else: return False

    def update_volume(self, invalue=None, mcvalue=None):
        ''' Updates internal state of zone after change in volume.

        Args:
            invalue (int): the new value of the volume in internal metric
            mcvalue (int): the new value of the volume in MusicCast metric

        Returns:
            Boolean: True if there is a change.
        '''
        if invalue is None: volume = self._transform_arg('volume', mcvalue=mcvalue)
        else: volume = invalue
        if self._volume == volume: return False # do nothing if no change
        # do something here if needed
        _logger.info(''.join(('Volume from <', str(self._volume), '> to <', str(volume), '>.')))
        self._volume = volume
        return True

    def set_volume(self, up=None):
        ''' Sets the volume of the zone.

        Args:
            up (boolean): if given defines if volume is stepped up or down, if
              not then the volume to set has to be in the arguments.
        '''
        self.device.is_mcready(raises=True)
        self.is_power_on(raises=True)
        if up is None:
            # retrieve the volume in the arguments; cast it to int just in case it's a string
            try: volume = int(self.device.system.get_argument('volume'))
            except (TypeError, ValueError): raise mcx.LogicError('Invalid volume argument')
            mc_volume = self._transform_arg('volume', invalue=volume)
            mc_volume = min(max(mc_volume, self._volume_min),
                            (self._volume_min + self._volume_range))
            self.device.conn.mcrequest(self.mcid, ''.join(('setVolume?volume=', str(mc_volume))))
        else:
            self.device.conn.mcrequest(self.mcid, ''.join(('setVolume?volume=',
                                                           'up' if up else 'down')))
            # calculate volume level to update locally
            mc_volume = self._transform_arg('volume', invalue=self._volume)
            # mc_volume is an int
            mc_volume += (1 if up else -1) * self._volume_step
            mc_volume = min(max(mc_volume, self._volume_min),
                            (self._volume_min + self._volume_range))
            volume = self._transform_arg('volume', mcvalue=mc_volume)
        self.update_volume(volume)
        self.status_requested = True
        self._response = 'OK'
        self._reason = ''.join(('volume is ', str(volume)))
        return

    def update_mute(self, invalue=None, mcvalue=None):
        ''' Updates internal state of zone after change in mute state.

        Args:
            invalue (boolean): the new value of the mute state
            mcvalue (string): "true" or "false"

        Returns:
            Boolean: True if there is a change.
        '''
        if invalue is None: mute = self._transform_arg('mute', mcvalue=mcvalue)
        else: mute = invalue
        if self._mute == mute: return False # do nothing if no change
        # do something here if needed
        self._mute = mute
        _logger.info(''.join(('Mute from <', str(self._mute), '> to <', str(mute), '>.')))
        return True

    def set_mute(self, mute):
        ''' Sets the mute property of the zone.

        Args:
            mute (boolean): converted into 'true' or 'false'
        '''
        self.device.is_mcready(raises=True)
        self.is_power_on(raises=True)
        mc_mute = self._transform_arg('mute', invalue=mute)
        self.device.conn.mcrequest(self.mcid, ''.join(('setMute?enable=', mc_mute)))
        self.update_mute(mute)
        self.status_requested = True
        self._response = 'OK'
        self._reason = ''.join(('mute is ', mc_mute))
        return

    def update_input(self, invalue=None, mcvalue=None):
        ''' Updates internal value of input object after change in input.

        Managing the <input> inside the application is complicated by the fact that the device
        might have a lot of valid inputs that are not documented in the system definition if they
        are unused.  For example an HDMI input (say "hdmi5") might not be physically connected and
        therefore does not need to appear in the system defintion, but it still exists.
        Then if another interface or a physical user switches to that input, probably by mistake,
        this interface should handle it and not generate errors.

        Args:
            invalue (string): a valid internal input id
            mcvalue(string): a valid Input MusicCast id

        Returns:
            Boolean: True if there is a change.
        '''
        if invalue is None: input_id_new = self._transform_arg('input', mcvalue=mcvalue)
        else: input_id_new = invalue
        if self._input and self._input.id == input_id_new: return False # do nothing if no change
        # do something here if needed
        if self._input is None: input_id_old = 'None'
        else: input_id_old = self._input.id
        _logger.info(''.join(('Input from <', str(input_id_old), '> to <', str(input_id_new), '>.')))
        self._input_id = input_id_new # assign new value to internal attribute
        # update object reference, if it exists, otherwise it is None
        self._input = self.device.get_input(input_id=input_id_new, raises=False)
        return True

    def set_input(self, input_id=None):
        ''' Sets the input of the zone.

        This method simply switches the input of the current zone.  It does not matter if the input
        is a source or not.  No other action is performed, so if for example the input is a source
        on the same device and it needs to be started or tuned, this is not done here.

        Args:
            input_id (string): input internal identifier
        '''
        # Find the actual Input object in the device from its input_id
        if input_id is None: input_id = self.device.system.get_argument('input')
        inp = self.device.get_input(input_id=input_id, raises=True)
        # Deal first with the non-MusicCast devices
        if not self.device.musiccast:
            # "Release" any connected source here, if necessary
            self._input = inp
            return
        # Now it is a MusicCast Ready device
        self.device.is_mcready(raises=True) # if it is MusicCast but not online, exception raised
        self.is_power_on(raises=True)
        self.device.conn.mcrequest(self.mcid, ''.join(('setInput?input=', inp.mcid)))
        self.update_input(input_id)
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

    def set_source(self, src_id=None):
        ''' Sets the source for the current zone, if available.

        Args:
            src_id (string): source keyword in internal vocabulary.

        This command is complex and involves a lot of decision making if it
        needs to take into account the most diverse set-ups. In most cases,
        every amplified zone will only have one choice per source, and if that
        source is unavailable for any reason (because the device it comes from
        is playing another source for another zone, for example), then there is
        nothing else to do and the command fails. But this method wants also to
        take care of the more complicated cases, where a zone has multiple
        options to select a given source, so that if one is unavailable it can
        choose another one.

        Also, this command has to deal with the case where the zone making the
        call is not a MusicCast one. That is because the source it will connect
        to might be MusicCast and has to be processed by this command.
        Therefore, all the following cases are possible:

        - zone and source are non MusicCast devices: do nothing;
        - zone and source are on same MusicCast device: easy;
        - zone is MusicCast but source is not: less easy;
        - zone and source are different but both MusicCast: a bit tricky;
        - zone is not MusicCast but source is: a bit of a pain...

        Finally, dealing with the source is complicated by the fact that the
        command should not grab the source requested without checking first if
        it is already used by another zone.

        15May2018: Priorities in finding source:

        1) Prefer same device (even if not MusicCast)
        2) Prefer MusicCast devices as remote sources
        3) Prefer source being already played and join it
        4) Take a non MusicCast device if found
        5) Prefer source being already played and join it

        '''

        # Find src_id in the arguments dictionary if it is not given as a method argument
        if src_id is None: src_id = self.device.system.get_argument('source')
        _logger.debug(''.join(('set_source - set src_id = ', str(src_id))))

        # Priority 1: find the source on the same device.
        #   The search is made on the internal keyword, not the MusicCast one,
        #   as we might be on a non MusicCast zone.
        if src_id in self.device.sources_by_id(): # source found in same device
            _logger.debug(''.join(('set_source - source found on same device ', self.device.id)))
            if not self.device.is_mcready(): # not MusicCast ready, abandon.
                raise mcx.LogicError(''.join(('Cannot set source ', src_id,
                                              ' on device ', self.device.id, '.')))
            src = self.device.sources_by_id()[src_id] # FIXME: not great...
            self.set_input(src.mcid) #;self._update_usedby_lists(src)
            return

        _logger.debug('set_source - source not found on same device')
        # Source not found on the same device.
        #   Look for source in all *remote* devices connected to the feeds.
        #   Priority 2: prefer MusicCast devices.
        #      Priority 2a: join a source that is already playing.
        remote_zone_found = False
        for feed in self.device.feeds:
            # look through every feed for MusicCast devices with the right source
            remote_dev = feed.get_remote_dev(raises=True)
            if not remote_dev.is_mcready(): continue # check in MusicCast Ready devices only
            if src_id not in remote_dev.sources_by_id(): continue # no source here
            remote_zone = feed.get_control_zone()
            if remote_zone.is_power_on(): # remote zone is already on
                current_mcid = remote_zone._get_current_input(raises=True).mcid
                target_mcid = remote_dev.get_input(input_mcid=src_id, raises=True).mcid
                if current_mcid == target_mcid: # same source!
                    remote_zone_found = True
                    _logger.debug(''.join(('set_source - using play zone in MusicCast device ',
                                           remote_dev.id, '.')))
                    break
                else: # the zone is playing another source... Take control and change it
                    remote_zone.set_input(src_id)
                    _logger.debug(''.join(('set_source - using busy zone in MusicCast device ',
                                           remote_dev.id, '.')))
                    break
            else:
                if not remote_zone._amplified: # zone OFF and not powering another location, use it
                    remote_zone.set_power(True)
                    remote_zone.set_input(src_id)
                    remote_zone_found = True
                    _logger.debug(''.join(('set_source - using a free zone in MusicCast device ',
                                           remote_dev.id, '.')))
                    break
        if remote_zone_found:
            _logger.debug(''.join(('set_source - using zone ', remote_zone.id,
                                   ' in remote MusicCast device ', remote_dev.id, '.')))
            self.set_input(feed.id)
            #self._update_usedby_lists(src)
            return

        # At this stage there are no usable MusicCast ready sources to use.
        # We care to find a non-MusicCast source (on a remote device) only to set the right input
        #   on the current zone, but there is nothing to check on the source
        #   (is it on already?, being played for something else?...). We just
        #   switch the input to this feed and hope for the best.
        # Also, if this device is not MusicCast ready, we do not care anymore, so we can leave.
        if not self.device.is_mcready():
            raise mcx.LogicError(''.join(('No MusicCast ready source ', src_id,
                                          ' found for this non-MusicCast ready zone.')))
        for feed in self.device.feeds:
            remote_dev = feed.get_remote_dev()
            if remote_dev.musiccast: continue # loop through non-MusicCast devices only
            if src_id in remote_dev.sources_by_id(): # source found
                _logger.debug('set_source - source found on non MusicCast device')
                self.set_input(feed.id) # the current device is MusicCast ready
                _logger.debug(''.join(('set_source - use feed ', feed.id)))
                return

        # if we are here, it means we did not find the source in any non MC device either
        raise mcx.LogicError(''.join(('No available source ', src_id, ' for this zone.')))

    def get_sources(self):
        ''' docstring

        '''
        # TODO: implement
        self._response = 'this,should,be,a,list,of,valid,sources'
        self._reason = 'for now it does not work'
        return

    def set_playback(self, action, src_id=None):
        '''Triggers the specified play-back action.

        To be able to play a source, it has to be selected first, so that
        the attribute `zonesource` is defined properly.
        The zone `zonesource` is expected to be MusicCast otherwise nothing can
        be done anyway.

        Args:
            action (string): the action to send to the MusicCast device.
            src_id (string): the internal keyword of the source to be
                played, if supplied, otherwise it is expected to be in the
                arguments.
        '''
        # Find which zone (remote or not) we need to control to execute this command
        control_zone = self._get_current_input().get_control_zone()
        # Check if it is MusicCast Ready, otherwise there is nothing to do
        control_zone.device.is_mcready(raises=True)
        control_zone.is_power_on(raises=True)
        # Resolve the source and check it is the one playing
        if src_id is None: src_id = self.device.system.get_argument('source')
        source = control_zone._get_current_input()
        if src_id != source.id:
            raise mcx.LogicError(''.join(('Can not operate source <', src_id,
                                          '> while device <', control_zone.device.id,
                                          '> is playing <', source.id, '>.')))

        # Transform action
        mcaction = self._transform_arg('action', invalue=action)

        # Send command
        control_zone.device.conn.mcrequest(source.playinfo_type.type,
                                           ''.join(('setPlayback?playback=', mcaction)))
        #control_zone.send_reply('OK', ''.join(('playback set to ', action)))
        return

    def set_preset(self, src_id=None):
        '''Set the preset specified in the arguments for the source.

        Args:
            action (string): the action to send to the MusicCast device.
            source_id (string): the internal keyword of the source to be
                preset, if supplied, otherwise it is expected to be in the
                arguments.  It can only be **tuner** or **netusb**.
        '''
        # Find which zone (remote or not) we need to control to execute this command
        ctrl_zone = self._get_current_input(raises=True).get_control_zone()
        # Check if it is MusicCast Ready, otherwise there is nothing to do
        ctrl_zone.device.is_mcready(raises=True)
        ctrl_zone.is_power_on(raises=True)
        # Resolve the source and check it is the one playing
        if src_id is None: src_id = self.device.system.get_argument('source')
        src = ctrl_zone._get_current_input()
        if src_id != src.id:
            raise mcx.LogicError(''.join(('Can''t preset <', src_id,
                                          '> while device <', ctrl_zone.device.id,
                                          ' is playing input <', src.id, '>.')))

        # Retrieve the number of the preset.
        try: preset_num = int(self.device.system.get_argument('preset'))
        except (KeyError, ValueError):
            raise mcx.LogicError('No valid preset argument found.')

        # The command format depends on the source
        qualifier = src.playinfo_type.type
        args = src.playinfo_type.get_preset_arguments(src, preset_num)
        cmdtxt = 'recallPreset?zone={}&band={}&num={}'.format(ctrl_zone.mcid,
                                                              args['band'], args['preset_num'])

        # Send the command
        ctrl_zone.device.conn.mcrequest(qualifier, cmdtxt)
        #ctrl_zone.send_reply('OK', ''.join(('preset ', src.mcid,
        #                                    ' to number ', str(preset_num))))
        return

    def str_status(self):
        ''' Returns the full status dictionary.'''
        return ''.join(([''.join(('\n\t\t\t', key, ': ', str(self._status[key])))
                         for key in self._status]))

    def str_zone(self):
        '''Returns the identification of a zone.'''
        return ''.join((self.device.id, '.', self.id))

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
        lst.append('\n\tIs MusicCast? ')
        lst.append('Yes' if self.device.musiccast else 'No')
        lst.append('\n\t\tMusicCast id: ')
        lst.append(str(self.mcid))
        lst.append('\n\t\tState is')
        lst.append(self.str_status())
        return ''.join(lst)

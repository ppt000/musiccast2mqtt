''' Declaration of PlayInfoType structures.

.. reviewed 9 November 2018
'''

import logging

import musiccast2mqtt as mcc

LOG = logging.getLogger(__name__)

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
        device (:class:Device object): parent device of the source.
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
        either case is different, see the Yamaha doc for details. This method is supposed to be
        overridden in both cases.
        '''
        raise mcc.LogicError(''.join(('Type <', self.type, '> does not have preset info.')))

    def update_play_time(self, value):
        ''' Updates the play_time attribute with the new value.

        Only concerns MusicCast types **cd** and **netusb**.
        The **play_time** event get sent every second by MusicCast devices
        once a cd or a streaming service starts playing.

        Args:
            value (integer in string form): the new value of play_time.
        '''
        raise mcc.LogicError(''.join(('Type <', self.type, '> does not have play time info.')))

    def update_play_message(self, value):
        ''' Updates the play_message attribute with the new value.

         This event only applies to the **netusb** group.

        Args:
            value (string): the new value of play_message.
        '''
        raise mcc.LogicError(''.join(('Type <', self.type, '> does not have play message info.')))

    def get_preset_arguments(self, source, preset_num):
        ''' Returns a dictionary with the preset information.

        Args:
            source (:class:`Source`): the source with the preset information
            preset_num (int): the preset number to retrieve
        '''
        raise mcc.LogicError(''.join(('Source ', source.input_mcid, ' does not have presets.')))

class Tuner(PlayInfoType):
    ''' Tuner specific information.

    Args:
        device (Device object): parent device.
    '''

    def __init__(self, device):
        super(Tuner, self).__init__('tuner', device)
        # Resolve the _preset_separate and the _info_bands
        preset_type = self.device.get_feature(('tuner', 'preset', 'type'))
        self._preset_separate = (preset_type == 'separate')
        if self._preset_separate:
            func_list = self.device.get_feature(('tuner', 'func_list'))
            self._info_bands = [band for band in func_list if band in ('am', 'fm', 'dab')]
        # load the max_preset
        try: self._max_presets = int(self.device.get_feature(('tuner', 'preset', 'num')))
        except ValueError:
            raise mcc.LogicError('getFeatures item <max_presets> not an int.')
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
                    raise mcc.CommsError('getPresetInfo did not return a preset_info field.')
            self._preset_info = preset_info # update attribute only after all worked properly
        else:
            response = self.device.conn.mcrequest('tuner', 'getPresetInfo?band=common')
            try: self._preset_info = response['preset_info']
            except KeyError:
                raise mcc.CommsError('getPresetInfo did not return a preset_info field.')
        return

    def get_preset_arguments(self, source, preset_num):
        ''' Returns a dictionary with the preset information.

        Args:
            source (:class:`Source`): the source with the preset information
            preset_num (int): the preset number to retrieve
        '''
        args = {}
        if self._preset_separate:
            args['band'] = 'dab' # for now that's the only preset we want to use.
            # TODO: include other bands selection.
        else: args['band'] = 'common'
        if preset_num < 1 or preset_num > self._max_presets:
            raise mcc.LogicError(''.join(('Preset ', str(preset_num), ' is out of range.')))
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
            raise mcc.CommsError('getFeatures item <max_presets> not an int.')
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
        ''' Returns a dictionary with the preset information.

        Args:
            source (:class:`Source`): the source with the preset information
            preset_num (int): the preset number to retrieve
        '''
        args = {}
        if source.input_mcid == 'net_radio': args['band'] = ''
        else: # source.input_mcid not 'net_radio'
            raise mcc.LogicError(''.join(('Source ', source.input_mcid, ' does not have presets.')))
        if preset_num < 1 or preset_num > self._max_presets:
            raise mcc.LogicError(''.join(('Preset ', str(preset_num), ' is out of range.')))
        args['preset_num'] = str(preset_num)
        return args

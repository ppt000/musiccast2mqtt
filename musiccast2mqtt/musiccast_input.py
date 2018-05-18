'''
Created on 5 May 2018

@author: PierPaolo
'''

import mqtt_gateways.musiccast.musiccast_exceptions as mcx

import mqtt_gateways.utils.app_properties as app
_logger = app.Properties.get_logger(__name__)

class Input(object):
    ''' Represents an input on the device.

    Args:
        data (dictionary): represents the input
        device (:class:`Device`): the parent device
    '''
    def __init__(self, data, device):
        self.device = device
        self.id = data['id']
        if self.device.musiccast: self.mcid = data['mcid']
        return

    def post_init(self):
        ''' Docstring'''
        pass

    def get_source_zone(self, raises=False):
        ''' Returns the control zone connected to this input'''
        return self # by default

    def is_source(self):
        ''' Tests if this is a source.'''
        if not isinstance(self, Source):
            raise mcx.ConfigError(''.join(('This input <', self.id, '> should be a source.')))
        return

    def get_source(self):
        ''' Returns the source playing through this input.'''
        # CHECK: difference with get_source_zone?
        return self # by default

class Feed(Input):
    ''' Represents an input on the device that is not a source.

    TODO: A feed within a MusicCast system is an input for which the `play_info_type`
    field within the getFeatures structure is set to **none**.

    Args:
        feed_data (dictionary): the **feed** characteristics.
        device (:class:`Device`): the parent device.
    '''
    def __init__(self, feed_data, device):
        super(Feed, self).__init__(feed_data, device)
        self._remote_dev_id = feed_data['device_id']
        self._remote_zone_id = feed_data.get('zone_id', None)
        self._remote_dev = None # assigned later when all devices are initialised
        self._remote_zone = None # assigned later and only for MusicCast devices
        #self.remote_source = None
        return

    def post_init(self):
        ''' Docstring '''
        super(Feed, self).post_init()

        self._remote_dev = self.device.system.get_device(device_id=self._remote_dev_id)
        if self._remote_dev is None: # device for that feed was not found
            _logger.info(''.join(('Device ', self._remote_dev_id, ' not defined.')))
        else:
            self._remote_zone = self._remote_dev.get_zone(zone_id=self._remote_zone_id, raises=False)
            if self._remote_zone is None: # zone not found
                if self._remote_dev.is_musiccast(): # does not matter if it is not MusicCast
                    _logger.info(''.join(('Zone ', self._remote_zone_id,
                                          ' not found in device ', self._remote_dev_id, '.')))
                    self._remote_dev = None # disable the device pointer if zone not found

    def get_remote_dev(self, raises=False):
        ''' Returns the remote Device object.'''
        if self._remote_dev is None and raises:
            raise mcx.ConfigError('Current [remote device] unassigned')
        return self._remote_dev

    def get_source_zone(self, raises=False):
        ''' Returns the remote Zone object.'''
        if self._remote_zone is None and raises:
            raise mcx.ConfigError('Current [remote zone] unassigned')
        return self._remote_zone

    def get_remote_source(self, raises=False):
        ''' Finds the remote Source object playing through this feed.'''
        if self._remote_zone is None:
            if raises: raise mcx.ConfigError('Current [remote zone] unassigned.')
            else: return None
        return self._remote_zone.get_current_input(raises=True)

class Source(Input):
    ''' Represents a source on the device.

    A source within a MusicCast system is an input for which the
    `play_info_type` field within the getFeatures structure is set to a
    different value than **none**, normally either **cd**, **tuner** or
    **netusb**.

    Args:
        source_data (dictionary): the **source** characteristics.
        device (:class:`Device`): the parent device.
    '''
    def __init__(self, source_data, device):
        super(Source, self).__init__(source_data, device)
        #self.usedby = [] # TODO: Remove?
        self.playinfo_type = None # set in load_musiccast
        return

    def load_musiccast(self):
        '''Initialisation of MusicCast related characteristics.

        This method uses the objects retrieved from previous HTTP requests.
        It can be called again at any time to try again this initialisation.
        '''
        try:
            for inp in self.device.get_feature(('system', 'input_list')):
                if inp['id'] == self.mcid: play_info_type = inp['play_info_type']
        except KeyError:
            mcx.CommsError('getFeatures object does not contain the keys '\
                           '<system>, <input_list>, <id> or <play_info_type>.')
        self.playinfo_type = self.device.init_infotype(play_info_type)
        return

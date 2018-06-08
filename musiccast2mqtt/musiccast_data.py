''' Dispatch tables for the MusicCast system.

.. reviewed 31MAY2018
'''

TRANSFORM_ARG = { # [0]=internal->musiccast, [1]=musiccast->internal
    'power':    (lambda self, value: 'on' if value else 'standby',
                 lambda self, value: value == 'on'),
    'mute':     (lambda self, value: 'true' if value else 'false',
                 lambda self, value: value == 'true'),
    'volume':   (lambda self, value: int(int(value) * self._volume_range / 100),
                 lambda self, value: int(int(value) * 100 / self._volume_range)),
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
        # preset number, could be an int?
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
    'VOLUME_UP':        lambda self: self.set_volume(up=True),
    'VOLUME_DOWN':      lambda self: self.set_volume(up=False),
    # TODO: implement VOLUME_UP and DOWN with step...
    'MUTE_ON':          lambda self: self.set_mute(True),
    'MUTE_OFF':         lambda self: self.set_mute(False),
    'MUTE_TOGGLE':      lambda self: self.set_mute(not self._mute),
    'GET_INPUTS':       lambda self: self.get_inputs(),
    'SET_INPUT':        lambda self: self.set_input(),
    'INPUT_CD':        lambda self: self.set_input('cd'),
    'INPUT_NETRADIO':  lambda self: self.set_input('net_radio'),
    'INPUT_TUNER':     lambda self: self.set_input('tuner'),
    'INPUT_SPOTIFY':   lambda self: self.set_input('spotify'),
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
    'power': lambda self, value: self.find_mczone('main').update_power(mcvalue=value),
    'input': lambda self, value: self.find_mczone('main').update_input(mcvalue=value),
    'volume': lambda self, value: self.find_mczone('main').update_volume(mcvalue=value),
    'mute': lambda self, value: self.find_mczone('main').update_mute(mcvalue=value),
    'status_updated': lambda self, value:
        self.find_mczone('main').refresh_status() if value else None,
    'signal_info_updated': None # not implemented; use 'getSignalInfo'
},
'zone2': {
    'power': lambda self, value: self.find_mczone('zone2').update_power(mcvalue=value),
    'input': lambda self, value: self.find_mczone('zone2').update_input(mcvalue=value),
    'volume': lambda self, value: self.find_mczone('zone2').update_volume(mcvalue=value),
    'mute': lambda self, value: self.find_mczone('zone2').update_mute(mcvalue=value),
    'status_updated': lambda self, value:
        self.find_mczone('zone2').refresh_status() if value else None,
    'signal_info_updated': None, # not implemented; use 'getSignalInfo'
},
'zone3': {},
'zone4': {},
'tuner': {
    'play_info_updated': lambda self, value:
        self.find_infotype('tuner').update_play_info() if value else None,
    'preset_info_updated': lambda self, value:
        self.find_infotype('tuner').update_preset_info() if value else None,
},
'netusb': {
    'play_error': None, # TODO: implement
    'multiple_play_errors': None, # TODO: implement
    'play_message': lambda self, value:
        self.find_infotype('netusb').update_play_message(value),
    'account_updated': None, # not implemented; use 'getAccountStatus'
    'play_time': lambda self, value:
        self.find_infotype('netusb').update_play_time(value),
    'preset_info_updated': lambda self, value:
        self.find_infotype('netusb').update_preset_info() if value else None,
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
        self.find_infotype('netusb').update_play_info() if value else None,
    'list_info_updated': None # not implemented; use 'getListInfo'
    # Received a 'play_queue':{'updated':true} on 2018-04-12
},
'cd': {
    'device_status': None, # not implemented; use 'cd_status'
    'play_time': lambda self, value:
        self.find_infotype('cd').update_play_time(value),
    'play_info_updated': lambda self, value:
        self.find_infotype('cd').update_play_info() if value else None,
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

_RESPONSE_CODES = {
0: 'Successful request',
1: 'Initialising',
2: 'Internal Error',
3: 'Invalid Request (A method did not exist, wasn''t appropriate etc.)',
4: 'Invalid Parameter (Out of range, invalid characters etc.)',
5: 'Guarded (Unable to setup in current status etc.)',
6: 'Time Out',
99: 'Firmware Updating',
100: 'Access Error',
101: 'Other Errors',
102: 'Wrong User Name',
103: 'Wrong Password',
104: 'Account Expired',
105: 'Account Disconnected/Gone Off/Shut Down',
106: 'Account Number Reached to the Limit',
107: 'Server Maintenance',
108: 'Invalid Account',
109: 'License Error',
110: 'Read Only Mode',
111: 'Max Stations',
112: 'Access Denied'
}

_ZONES = ('main', 'zone2', 'zone3', 'zone4')

_INPUTS = ('cd', 'tuner', 'multi_ch', 'phono', 'hdmi1', 'hdmi2', 'hdmi3',
           'hdmi4', 'hdmi5', 'hdmi6', 'hdmi7', 'hdmi8', 'hdmi', 'av1', 'av2',
           'av3', 'av4', 'av5', 'av6', 'av7', 'v_aux', 'aux1', 'aux2', 'aux',
           'audio1', 'audio2', 'audio3', 'audio4', 'audio_cd', 'audio',
           'optical1', 'optical2', 'optical', 'coaxial1', 'coaxial2', 'coaxial',
           'digital1', 'digital2', 'digital', 'line1', 'line2', 'line3',
           'line_cd', 'analog', 'tv', 'bd_dvd', 'usb_dac', 'usb', 'bluetooth',
           'server', 'net_radio', 'rhapsody', 'napster', 'pandora', 'siriusxm',
           'spotify', 'juke', 'airplay', 'radiko', 'qobuz', 'mc_link',
           'main_sync', 'none')

_SOUNDPROGRAMS = ('munich_a', 'munich_b', 'munich', 'frankfurt', 'stuttgart',
                  'vienna', 'amsterdam', 'usa_a', 'usa_b', 'tokyo', 'freiburg',
                  'royaumont', 'chamber', 'concert', 'village_gate',
                  'village_vanguard', 'warehouse_loft', 'cellar_club',
                  'jazz_club', 'roxy_theatre', 'bottom_line', 'arena', 'sports',
                  'action_game', 'roleplaying_game', 'game', 'music_video',
                  'music', 'recital_opera', 'pavilion', 'disco', 'standard',
                  'spectacle', 'sci-fi', 'adventure', 'drama', 'talk_show',
                  'tv_program', 'mono_movie', 'movie', 'enhanced', '2ch_stereo',
                  '5ch_stereo', '7ch_stereo', '9ch_stereo', '11ch_stereo',
                  'stereo', 'surr_decoder', 'my_surround', 'target', 'straight',
                  'off')

if __name__ == '__main__':
    pass

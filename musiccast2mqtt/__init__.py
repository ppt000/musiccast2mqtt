'''Package header for musiccast2mqtt.

This header declares the version, the exceptions, the constants,
the classes defining the tokens to use in the threading queues,
and the lists of *official* keywords for the MusicCast API.
'''

__version_info__ = (0, 200, 0)
__version__ = '.'.join(str(c) for c in __version_info__)

version = '0.114'
# History
# 24 Sep 2018 - v0.200.0 - Remove non MusicCast devices.

class AnyError(Exception):
    ''' All the errors from this package.'''
    pass

class CommsError(AnyError):
    ''' Communication errors.'''
    pass

class LogicError(AnyError):
    ''' Logic errors.'''
    pass

class ConfigError(AnyError):
    ''' Configuration errors.'''
    pass

# Constants ===================================================================

APP_NAME = 'musiccast'
''' Name of this app to appear as sender and gateway in messages.'''


# Name of the function of this app to be used in messages
APP_FUNCTION = 'audiovideo'
# The default listening port for MusicCast events. Chosen at random here, can be set in config.
DEFAULT_LISTEN_PORT = 41100
# Time between re-trials to initialise MusicCast devices, in seconds.
INIT_LAG = 600
# Minimum lag between two HTTP requests
REQUESTS_LAG = 0.5
# Minimum lag between a request and a status refresh, in seconds
BUFFER_LAG = 5
# Maximum time of inactivity before Yamaha API stops sending events, in seconds
STALE_CONNECTION = 30 # for TEST only, should be 300
# Maximum queue size
MAX_QUEUE_SIZE = 10
# Buffer size of sockets
SOCKET_BUFFER_SIZE = 4096
# Time-out for the select function while listening for events, in seconds
LISTEN_TIMEOUT = 60.0
# Sleep time when socket error happens, before retrying, in seconds
SOCKET_ERROR_SLEEP = 1.0
# Maximum time between SSDP searches, in seconds
DISCOVERY_CYCLE = 30 # for TEST only, should be 600
# The time-out for the HTTP requests, in seconds
HTTP_TIMEOUT = 1


# token to help with queue messaging
END_QUEUE = object()

class DeviceHandle(object):
    ''' The token to be used in the Device Factory queue.'''
    CREATE = 1
    DELETE = 2
    def __init__(self, task, device_id=None, host=None, api_port=None):
        self.task = task
        self.device_id = device_id
        self.host = host
        self.api_port = api_port

class DeviceTask(object):
    ''' The token to be used in the Device Task queues.'''
    REFRESH_STATUS = 0
    PROCESS_EVENT = 1
    PROCESS_MESSAGE = 2
    DISABLE_DEVICE = 3
    def __init__(self, task, zone=None, event=None, msg=None):
        self.task = task
        self.zone = zone
        self.event = event
        self.msg = msg

# pylint: disable=bad-whitespace
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
# pylint: enable=bad-whitespace

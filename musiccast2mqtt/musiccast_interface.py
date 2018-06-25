'''Interface for MusicCast gateway.

.. reviewed 31May2018
'''

import json

import mqttgateway.utils.app_properties as app
_logger = app.Properties.get_logger(__name__)

import musiccast2mqtt.musiccast_exceptions as mcx
from musiccast2mqtt.musiccast_system import System

_DEFAULT_LISTEN_PORT = 41100 # chosen at random within unassigned port numbers

class musiccastInterface(object):
    '''The Interface.

    Resolves the system definition file path and calls the System class in musiccast_system.
    Creates the locations and devices dictionaries.

    Args:
        params (dictionary): includes all options from the dedicated section
            of the configuration file.  This class only requires the **sysdefpath** option
            to be defined. It is the location of the JSON file describing the system.  If
            that option is not found then the local directory is used instead.
        msglist_in (list of :class:`internalMsg`): the list of incoming messages.
        msglist_out (list of :class:`internalMsg`): the list of outgoing messages.
    '''

    def __init__(self, params, msglist_in, msglist_out):
        # Keep the message lists locally
        self._msgl_in = msglist_in
        self._msgl_out = msglist_out
        self._msg = None # 'current' message being processed
        # compute the system definition file path
        try: jsonpath = params['sysdefpath']
        except KeyError:
            _logger.info('The "sysdefpath" option is not defined in the configuration file.'\
                         'Using ".".')
            jsonpath = '.'
        jsonfilepath = app.Properties.get_path(jsonpath, extension='.json')
        # load the system definition data; errors are fatal.
        try:
            with open(jsonfilepath, 'r') as json_file:
                json_data = json.load(json_file)
        except (IOError, OSError):
            _logger.critical(''.join(('Can''t open ', jsonfilepath, '. Abort.')))
            raise
        except ValueError: # python 3 has a different exception name
            _logger.critical(''.join(('Can''t JSON-parse ', jsonfilepath, '. Abort.')))
            raise
        # load the port to listen to for MusicCast events
        try: listenport = int(params['listenport'])
        except KeyError:
            listenport = _DEFAULT_LISTEN_PORT
            _logger.info(''.join(('The <listenport> option is not defined in the configuration file.',
                                  ' Using <', _DEFAULT_LISTEN_PORT, '>.')))
        except TypeError:
            _logger.critical(''.join(('The <listenport> option: <', params['listenport'],
                                      '> is not an int:. Abort.')))
            raise
        # instantiate the system structure
        self._system = System(json_data, listenport, self._msgl_out)
        # create the {device_id: device} dictionary
        #self._mcdevices = {dev.id: dev for dev in self._system.devices if dev.musiccast}

    def loop(self):
        ''' The method called periodically by the main loop.

        The policy to send back status messages depends on the addressing used
        by the incoming MQTT message: if it is addressed specifically to this
        interface or to a specific MusicCast device, then a reply will always be sent
        back (case called ``explicit``); if it is not, a reply is sent only if a command
        is executed, otherwise it stays silent as the message is probably intended for
        somebody else.
        '''

        # process the incoming messages list
        while True:
            self._msg = self._msgl_in.pull() # read messages on a FIFO basis
            if self._msg is None: break # no more messages
            _logger.debug(''.join(('Processing message: ', self._msg.str())))
            try: self._system.process_msg(self._msg)
            except mcx.AnyError as err:
                _logger.info(''.join(('Can\'t execute command. Error:\n\t', str(err))))

        # check if there are any events to process
        try: self._system.listen_musiccast()
        except mcx.AnyError as err:
            _logger.info(''.join(('Can\'t parse event. Error:\n\t', str(err))))

        # refresh the system
        self._system.refresh()

        # example code to write in the outgoing messages list
        #=======================================================================
        # msg = internalMsg(iscmd=True,
        #                   function='',
        #                   gateway='dummy',
        #                   location='Office',
        #                   action='LIGHT_ON')
        # self._msgl_out.push(msg)
        # _logger.debug(''.join(('Message <', msg.str(), '> queued to send.')))
        #=======================================================================

if __name__ == '__main__':
    pass

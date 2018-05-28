'''Interface for MusicCast.'''

import json

import musiccast2mqtt.musiccast_exceptions as mcx
from musiccast2mqtt.musiccast_system import System
from musiccast2mqtt.musiccast_data import ACTIONS

import mqttgateway.utils.app_properties as app
_logger = app.Properties.get_logger(__name__)

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
        jsonfilepath = app.Properties.get_path('.json', jsonpath)

        # load the system definition data; errors are fatal.
        try:
            with open(jsonfilepath, 'r') as json_file:
                json_data = json.load(json_file)
        except (IOError, OSError):
            _logger.critical(''.join(('Can''t open ', jsonfilepath, '. Abort.')))
            raise
        except ValueError:
            _logger.critical(''.join(('Can''t JSON-parse ', jsonfilepath, '. Abort.')))
            raise

        # instantiate the system structure
        self._system = System(json_data, self._msgl_out)

        # create the location to zone dictionary: key is a location, value is a Zone object
        self._locations = {zone.location: zone for dev in self._system.devices
                                                for zone in dev.zones if zone.location}

        # create the device id to device dictionary: key is an id, value is a Device object
        self._mcdevices = {dev.id: dev for dev in self._system.devices if dev.musiccast}

    def loop(self):
        ''' The method called periodically by the main loop.

        The policy to send back status messages depends on the addressing used
        by the incoming MQTT message: if it is addressed specifically to this
        interface or to a specific MusicCast device, then a reply will always be sent
        back (case called *assertive*); if it is not, a reply is sent only if a command
        is executed, otherwise it stays silent as the message is probably intended for
        somebody else.
        '''

        while True: # process the incoming messages list
            self._msg = self._msgl_in.pull() # read messages on a FIFO basis
            if self._msg is None: break # no more messages

            _logger.debug(''.join(('Processing message: ', self._msg.str())))

            if not self._msg.iscmd: continue # ignore status messages
            if self._msg.sender == 'musiccast': continue # ignore echos

            # find the zone to operate by resolving the 'address'
            assertive = False
            zone = None

            # The following filters should be dealt by subscriptions
            if not self._msg.function and not self._msg.gateway: continue
            if self._msg.gateway and self._msg.gateway != 'musiccast': continue
            if self._msg.function and self._msg.function != 'audiovideo': continue

            if self._msg.gateway: assertive = True
            if not self._msg.location and not self._msg.device: 
                self._msg_error('Missing location or device', assertive)
                continue
            if self._msg.location:
                try: zone = self._locations[self._msg.location]
                except KeyError:
                    self._msg_error('Location not found.', assertive)
                    continue
            if self._msg.device:
                assertive = True
                try: device = self._mcdevices[self._msg.device]
                except KeyError:
                    self._msg_error('Device not found', assertive)
                    continue
                else:
                    if zone and zone.device != device: # zone already defined by location
                        self._msg_error('Inconsistent devices', assertive)
                        continue
                    try: zone_id = self._msg.arguments['zone']
                    except KeyError: # if not already defined by location, take the first one
                        if not zone: zone = device.zones[0] 
                    else:
                        zone_bis = device.get_zone(zone_id=zone_id, raises=False)
                        if zone_bis is None:
                            self._msg_error('Zone not found', assertive)
                            continue
                        elif zone and zone!=zone_bis:
                            self._msg_error('Inconsistent zones', assertive)
                            continue
                        else:
                            zone = zone_bis

            # give access to the message attributes by loading them into the system instance
            self._system.put_msg(self._msg)

            # TODO: implement self._system.execute_action
            # retrieve the function to execute for this action
            try: func = ACTIONS[self._msg.action]
            except KeyError:
                self._msg_error('Action not found', assertive)
                continue

            # execute the function in the zone
            try: func(zone)
            except mcx.AnyError as err:
                _logger.info(''.join(('Can\'t execute command. Error:\n\t', str(err))))
                continue

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

    def _msg_error(self, error_text='Addressing error', mqtt_reply=False):
        ''' docstring '''
        _logger.info(''.join((error_text, ' in message ', self._msg.str())))
        if mqtt_reply: self._msgl_out.push(self._msg.reply('Error', error_text))

if __name__ == '__main__':
    pass

'''Interface for MusicCast.'''

import json

import mqtt_gateways.musiccast.musiccast_exceptions as mcx
from mqtt_gateways.musiccast.musiccast_system import System
from mqtt_gateways.musiccast.musiccast_data import ACTIONS

import mqtt_gateways.utils.app_properties as app
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
        self._devices = {dev.id: dev for dev in self._system.devices}

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
            msg = self._msgl_in.pull() # read messages on a FIFO basis
            if msg is None: break # no more messages

            _logger.debug(''.join(('Processing message: ', msg.str())))

            if not msg.iscmd: continue # ignore status messages

            # determine if the message is 'assertive'
            if msg.gateway == 'musiccast': # TODO: there are other cases to deal with
                assertive = True

            # is there a device in the topic?
            if msg.device:
                if msg.device in self._devices:
                    assertive = True
                    # TODO: select the 'default' zone for this device
                pass

            # get the zone for this location
            try: zone = self._locations[msg.location]
            except KeyError: # the location is not found
                errtxt = ''.join(('Location ', msg.location, ' not found.'))
                _logger.info(errtxt)
                if assertive: self._msgl_out.push(msg.reply('Error', errtxt))
                continue # ignore message and go onto next

            # give access to the message attributes by loading them into the system instance
            self._system.put_msg(msg)

            # TODO: implement self._system.execute_action
            # retrieve the function to execute for this action
            try: func = ACTIONS[msg.action]
            except KeyError: # the action is not found
                errtxt = ''.join(('Action ', msg.action, ' not found.'))
                _logger.info(errtxt)
                if assertive: self._msgl_out.push(msg.reply('Error', errtxt))
                continue # ignore message and go onto next

            # execute the function in the zone
            try: func(zone)
            except mcx.AnyError as err:
                _logger.info(''.join(('Can\'t execute command. Error:\n\t', repr(err))))
                continue

            # stack reply on outgoing message list
            #self._msgl_out.push(self.reply())

            #_logger.debug(zone.dump_zone())

        # check if there are any events to process
        try: self._system.listen_musiccast()
        except mcx.AnyError as err:
            _logger.info(''.join(('Can\'t parse event. Error:\n\t', repr(err))))

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

# if device['protocol'] == 'YNCA': conn.request('GET','@SYS:PWR=?\r\n')

if __name__ == '__main__':
    pass

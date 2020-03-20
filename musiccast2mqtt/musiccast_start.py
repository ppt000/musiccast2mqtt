''' Entry point for the MusicCast gateway.

.. reviewed 26 OCT 2018
'''

import logging

# import the module that initiates and starts the gateway
import mqttgateway.start_gateway as start_g

# import the module representing the interface
import musiccast2mqtt.musiccast_interface as mci

from mqttgateway.app_properties import AppProperties

APP_NAME = 'musiccast2mqtt'

def main():
    ''' launch the gateway'''
    # Initialise the application properties
    AppProperties(app_path=__file__, app_name=APP_NAME)
    AppProperties().register_logger(logging.getLogger('mqttgateway'))
    AppProperties().register_logger(logging.getLogger('musiccast2mqtt'))
    start_g.startgateway(mci.musiccastInterface)

if __name__ == '__main__':
    main()

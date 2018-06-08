'''Launcher for the MusicCast gateway.

.. reviewed 31May2018
'''

import os.path

_APP_NAME = 'musiccast2mqtt'

import mqttgateway.utils.app_properties as app
app.Properties.init(app_path=os.path.realpath(__file__), app_name=_APP_NAME)
_logger = app.Properties.get_logger(__name__)

# import the module that initiates and starts the gateway
import mqttgateway.gateway.start_gateway as start_g

# import the module representing the interface
import musiccast2mqtt.musiccast_interface as mci

def main():
    ''' launch the gateway'''
    start_g.startgateway(mci.musiccastInterface)

if __name__ == '__main__':
    main()

'''Launcher for the MusicCast gateway.'''

import os.path

import mqtt_gateways.utils.app_properties as app
app.Properties.init(os.path.realpath(__file__))

# import the module that initiates and starts the gateway
import mqtt_gateways.gateway.start_gateway as start_g
#import mqtt_gateways.gateway.start_gateway_test as start_g # TEST!!!!!

# import the module representing the interface *** add your import here ***
import mqtt_gateways.musiccast.musiccast_interface as mci

if __name__ == '__main__':
    # launch the gateway *** add your class here ***
    start_g.startgateway(mci.musiccastInterface)

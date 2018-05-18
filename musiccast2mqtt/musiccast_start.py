'''Launcher for the MusicCast gateway.'''

import os.path

import mqttgateway.utils.app_properties as app
app.Properties.init(os.path.realpath(__file__))

# import the module that initiates and starts the gateway
import mqttgateway.gateway.start_gateway as start_g

# import the module representing the interface *** add your import here ***
import musiccast2mqtt.musiccast_interface as mci

def main():
    # launch the gateway *** add your class here ***
    start_g.startgateway(mci.musiccastInterface)

if __name__ == '__main__':
    main()
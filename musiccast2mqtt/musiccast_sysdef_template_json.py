# Remove all comments and the first line to make this file a proper JSON file.
Template = \
{ "devices":
 [
     { # This is a MusicCast device:
      "id": "NetworkPlayer", # Required. Will be used to identify the device when addressed by
                             #  messages.
      "model": "CD-NT670D", # Optional and unused for now
      "protocol": "YEC", # Required only if MusicCast, in which case it has to be set to "YEC"
      "host": "192.168.1.10", # Required only if MusicCast
      "zones": [ # 1 zone only here, and it is only a 'pass-through' one.
                {"id": "MAIN", # Required, choose what is best. Only used for logs.
                               # Doesn't have to be the same as the mcid.
                 "location": "", # No location as this is a 'pure player'.
                 "mcid": "main"}], # Only required if MusicCast, in which case it MUST be a valid
                                   #  MusicCast zone identifier for this MusicCast device.
                                   # This means it will normally be either main or zone2, zone3...
      "sources": [ # Only define the sources that will be used.
                  {"id": "SPOTIFY", # Required.  Will be used to identify the source to set in the
                                    #  commands received.
                                    # Doesn't have to be the same as the mcid. Here, it could have
                                    #  been "streaming_service" for example.
                   "mcid": "spotify"}, # Required and HAS to be the exact MusicCast input
                                       #   identifier of the MusicCast device.
                  {"id": "SERVER", "mcid": "server"}, # other sources...
                  {"id": "NETRADIO", "mcid": "net_radio"},
                  {"id": "TUNER", "mcid": "tuner"},
                  {"id": "CD", "mcid": "cd"}],
      "feeds": [] # No feeds on this device.
     },
     { # This is another MusicCast device
      "id": "AVLivingRoom", "model": "RX-A550", "protocol": "YEC", "host": "192.168.1.11",
      "zones": [ # This AV Receiver has only 1 zone, but it is "real".
                {"id": "Room",
                 "location": "livingroom", # Actual location powered by this zone.  The location
                                           #  will be used by messages.
                 "mcid": "main"}],
      "sources": [ # Same as above.
                  {"id": "SPOTIFY", "mcid": "spotify"},
                  {"id": "SERVER", "mcid": "server"},
                  {"id": "NETRADIO", "mcid": "net_radio"},
                  {"id": "TUNER", "mcid": "tuner"}],
      "feeds": [ # This device has feeds.
                {"id": "av4", # Required, choose any name that suits, might be used by commands.
                 "device_id": "NetworkPlayer", # Required, the id of the device that is connected
                                               #  to this input.  It should be a device defined
                                               #  elsewhere in this structure.  If not, the gateway
                                               #  will generate a warning but will not fail.
                 "zone_id": "MAIN", # Required only if the connected device is MusicCast.
                                    # This has to be the id, not the mcid.
                 "mcid": "av4"}, # Required if the device itself is MusicCast.  Again, this is not
                                 #  a choice but it has to be a valid and existing input of the
                                 #  device being defined.
                {"id": "hdmi1",
                 "device_id": "BluRayPlayer", # The connected device is NOT MusicCast, so no need
                                              #  for the zone_id.  As it happens, this device is
                                              #  not even described elsewhere.
                 "mcid": "hdmi1"}, # But this is still required as the device itself is MusicCast.
                {"id": "hdmi2",
                 "device_id": "Satellite", # Similar case as above.
                 "mcid": "hdmi2"}
               ]
     },
     { # A non MusicCast device that is connected to MusicCast devices
      "id": "AudioMatrix",
      "zones": [ # This device has quite a few zones; only the location is needed as the devices
                 #  is not MusicCast.
                {"id": "channel1", "location": "kitchen"},
                {"id": "channel2", "location": "office"},
                {"id": "channel3", "location": "diningroom"}],
      "sources": [], # No sources
      "feeds": [
                {"id": "input1", # Connected to the AV Receiver RX-A550 defined above.
                 "device_id": "AVLivingRoom", # HAS to be exactly the same as the id of the
                                              #  device, obviously...
                 "zone_id": "Room"}, # The zone used by the connected device to feed this one.
                {"id": "input2", # Similar case to above.
                 "device_id": "NetworkPlayer",
                 "zone_id": "MAIN"}]
     }
 ]}
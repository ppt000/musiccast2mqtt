.. This document has been reviewed on 9June2018.

***********************
MusicCast Gateway Usage
***********************

This document describes how to format the MQTT messages addressed to this gateway.

Addressing the MusicCast Gateway
================================

As a reminder, the syntax of the MQTT topics recognised by the gateway is:
``root/function/gateway/location/device/sender/type`` where ``root`` is replaced by whatever
keyword is given as an option either in the configuration file if the mapping is off,
or in the mapping file if it is on, and will be unique for this gateway (for example ``home``),
``type`` can only be ``C`` for **command** or ``S`` for **status**,
and all the other 5 fields are the *characteristics* that can be any string.
Only 4 characteristics are used to determine the destination of the message: the **function**,
the **gateway**, the **location** and the **device**.  Not all of them need to be specified.
The basic rules to make sure the message reaches its destination are the following.

- either **function** or **gateway** need to be set to their only valid value for this
  gateway, which are ``audiovideo`` and ``musiccast``; these 2 keywords are defined in
  the source code;
- either **location** or **device** need to be set to valid location names and
  device names; these names are defined in the system definition file which is written
  by the user;
- if **device** is specified, the **zone** addressed has to be added as an arguments
  to the payload with a pair ``"zone": "whatever_is_the_name_of_the_zone"``,
  otherwise the ``main`` zone is selected;
- if **location** and **device** are both specified they need to be consistent
  (i.e. the location has to be the one that the device zone is associated with in the system
  definition file);

In practice, there are 2 ways to address a device:

- the more *natural* way is by specifying the **function** (``audiovideo``)
  and the **location** (e.g. ``livingroom``): ``home/audiovideo//livingroom//me/C`` will
  work to send a command as long as ``livingroom`` is specified as a location for a MusicCast
  device within the system definition file; the ``me`` is superfluous here and it indicates
  the sender.
- the more *explicit* way is by specifying the **gateway** (``musiccast``)
  and the **device** (e.g. ``networkplayer``): ``home//musiccast//networkplayer/me/C`` will
  work as long as ``networkplayer`` is defined as a MusicCast device within the system
  definition file.  The **zone** should be preferrably added to the arguments but the default
  ``main`` zone will be used if it is not.

Sending commands
================

The action to perform on the addressed device is specified in the payload of the MQTT message.
The payload can have 2 forms: a plain string representing the action to perform, or a JSON
structure including at least one pair ``"action": "whatever_is_the_name_of_the_action"`` and
as many pairs as needed for the arguments, e.g. ``{"action":"SET_VOLUME", "volume": 35}``.

Valid keywords for the actions are defined in the source code.

Vocabulary
==========

The *native* vocabulary is the set of keywords that are defined either in the python code
(generally in :mod:`musiccast_data.py`) or in the system definition file.

More precisely:

- **function** and **gateway** keywords are defined in the code, and the only used for now are
  ``audiovideo`` for **function** and ``musiccast`` for **gateway**;
- **location** and **device** keywords are defined in the system definition file;
- **sender** is only used by the interface to filter *echoes*, i.e. messages where **sender** is
  equal to ``musiccast``; any other keyword will be accepted without consequence;
- **action** keywords are defined in the source code;
- **argument key** keywords are defined in the code mostly with the same syntax as the
  arguments in the Yamaha API, e.g. ``volume``; they are also shown in the table below.

Recognised actions
==================
The actions currently recognised by the interface are listed below.
They are all self-explanatory.
Use those keywords as actions if mapping is disabled.

.. code::

  POWER_OFF
  POWER_ON
  SET_VOLUME # requires a "volume" argument representing a level between 0 and 100
  VOLUME_UP
  VOLUME_DOWN
  MUTE_ON
  MUTE_OFF
  MUTE_TOGGLE
  SET_INPUT # requires an "input" argument
  SOURCE_CD
  SOURCE_NETRADIO
  SOURCE_TUNER
  SOURCE_SPOTIFY
  CD_BACK
  CD_FORWARD
  CD_PAUSE
  CD_PLAY
  CD_STOP
  SPOTIFY_PLAYPAUSE
  SPOTIFY_BACK
  SPOTIFY_FORWARD
  TUNER_PRESET # requires a "preset" argument
  NETRADIO_PRESET # requires a "preset" argument

Mapping
=======

The mapping feature is disabled by default, but if it is implemented,
the *mapped* MQTT keywords have to be used instead of the *native* ones.

Examples
========

Without mapping, based on the system definition ``musiccast_sysdef.json`` provided with
the installation (see below), the topic and payload to use are as follows.

Use the device in the living room with the following topic (no gateway or device specified):
``home/audiovideo//livingroom//me/C``.  As the ``livingroom`` location is associated with the
``main`` zone of the **RX-A550**, this topic should address that device.

Then the payload defines the command:

- Turn on: ``POWER_ON``
- Set the volume to 50%: ``{"action":"SET_VOLUME", "volume": 50}``

If mapping is enabled, the keywords to use depend on the mapping.

The system definition provided with the installation:

.. literalinclude:: ../../musiccast2mqtt/musiccast_sysdef.json

.. This document has been reviewed by Paolo on ?????2018.

***********************
MusicCast Gateway Usage
***********************

This document describes how to format the MQTT messages addressed to this gateway.

Addressing the MusicCast Gateway
================================

As a reminder, the syntax of the MQTT messages recognised by the gateway is:
``root/function/gateway/location/device/sender/type`` where ``root`` is unique for a given
interface, ``type`` can only be ``C`` for **command** or ``S`` for **status**, and all other fields
can be any string.

4 characteristics are used to determine the destination of the message: the **function**,
the **gateway**, the **location** and the **device**.  Not all of them need to be specified.
The basic rules to make sure the message reaches its destination are the following.

- either **function** or **gateway** need to be specified to their only valid value for this
  gateway, which are ``audiovideo`` and ``musiccast``;
- either **location** or **device** need to be specified to valid location names and device names
  as identified in the system definition file;
- if **device** is specified, the **zone** addressed has to be added to the arguments with a pair
  ``"zone": "whatever_is_the_name_of_the_zone"``, otherwise the ``main`` zone is selected;
- if **location** and **device** are both specified they need to be consistent (i.e. the location
  has to be the one that the device zone is associated with in the system definition file);
- the more *natural* way to address a device is by specifying the **function** and the **location**.

Sending commands
================

The action to perform on the addressed device is specified in the payload of the MQTT message.
The payload can have 2 forms: a simple string representing the action to perform, or a JSON
structure including at least one pair ``"action": "whatever_is_the_name_of_the_action"`` and
as many pairs as needed for the arguments.

Vocabulary
==========

The *native* vocabulary is the set of keywords that are defined either in the python code
(generally in :mod:`musiccast_data.py`) or in the system definition file.
More precisely:

- **function** and **gateway** keywords are defined in the code, and the only used for now are
  ``audiovideo`` for **function** and ``musiccast`` for **gateway**;
- **location** and **device** keywords are defined in the system definition file;
- **sender** is only used by the interface to filter *echoes*, i.e. messages where **sender** is
  equal to ``musiccast``; any other keyword should be accepted here;
- **action** keywords are defined in a python table shown below;
- **argument key** keywords are defined in the code mostly with the same syntax as the arguments in
  the Yamaha API, e.g. ``volume``; they are also shown in the table below.

Mapping
=======

The mapping feature is disabled by default, but if it is implemented, then the MQTT keywords from
the mapping have to be used instead of the *native* ones.  That is the whole point of the mapping.

Recognised actions
==================

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

Examples
========

Without mapping, based on the system definition ``musiccast_sysdef.json`` provided with
the installation.

Use the device in the living room with the following topic (no gateway or device specified):
``home/audiovideo//livingroom//me/C``.

The payload defines the command:

- Turn on: ``POWER_ON``
- Set the source to CD: ``SOURCE_CD``
- Set the volume to 50%: ``{"action":"SET_VOLUME", "volume": 50}``

If mapping is enabled, the keywords to use depend on the mapping.

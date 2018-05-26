.. This document has been reviewed by Paolo on ?????2018.

***********************
MusicCast Gateway Usage
***********************

This document describes how to format the MQTT messages addressed to this gateway.

Reaching the Gateway
====================

4 characteristics are used to determine the destination of the message: the **function**,
the **gateway**, the **location** and the **device**.  Not all of them need to be specified.
The basic rules to make sure the message reaches it destination are the following.

- either **function** or **gateway** need to be specified to their only valid value for this
  gateway, which are ``audiovideo`` and ``musiccast``;
- either **location** or **device** need to be specified to valid location names and device names
  as identified in the system definition file;
- if **device** is specified 
- if **location** and **device** are both specified they need to be consistent (i.e. the location
  has to be the one that the device is associated with) -

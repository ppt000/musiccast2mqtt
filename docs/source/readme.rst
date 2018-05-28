#########################
Welcome to musiccast2mqtt
#########################

**MusicCast2MQTT** is a gateway between your Yamaha MusicCast devices and your MQTT broker.
It is based on the `mqttgateway <http://mqttgateway.readthedocs.io/en/latest/>`_ library.
It translates incoming MQTT messages into MusicCast commands.
The MQTT syntax required is flexible and configurable.

Installation
============

**MusicCast2MQTT** is available on ``pip``.  It is preferrable to use the ``--user`` option
or use a virtual environment.

.. code::

    pip install --user musicast2mqtt


Execution
=========

``pip`` installs an *entry-point* called ``musiccast2mqtt``.  Its location depends on your system
but hopefully your ``PATH`` environment variable already points there, so you can type anywhere:

.. code::

    musiccast2mqtt

and you should see a bunch of logs on the console.

Next step is to configure the application.  Check the 
`documentation <http://musiccast2mqtt.readthedocs.io/>`_.

Any issues, let me know `here <https://github.com/ppt000/musiccast2mqtt/issues>`_.

Links
=====

- **Documentation** on `readthedocs <http://musiccast2mqtt.readthedocs.io/>`_.
- **Source** on `github <https://github.com/ppt000/musiccast2mqtt>`_.
- **Distribution** on `pypi <https://pypi.org/project/musiccast2mqtt/>`_.

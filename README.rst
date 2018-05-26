
.. include:: docs/source/banner.txt

The documentation in ``docs/source`` is formatted to be read in
`ReadTheDocs <http://musiccast2mqtt.readthedocs.io/>`_.

Welcome to MusicCast2MQTT
=========================

**MusicCast2MQTT** is a gateway between your Yamaha MusicCast devices and your MQTT broker.
It relies on the ``mqttgateway`` library (documented `here <http://mqttgateway.readthedocs.io/>`_).

Installation
------------

**MusicCast2MQTT** is available on ``pip``.  It is preferrable to use the ``--user`` option
or use a virtual environment.

.. code-block::

    pip install --user musicast2mqtt


Execution
---------

``pip`` install en *entry-point* called ``musiccast2mqtt``.  Its location depends on your system
but hopefully your ``PATH`` environment variable already points there, so you can type anywhere:

.. code-block::

    musiccast2mqtt

and you should see a bunch of logs on the console.

Next step is to configure the application. Head to the
`documentation <http://musiccast2mqtt.readthedocs.io/>`_ for that.

Any issues, let me know.

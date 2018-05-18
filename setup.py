'''A setuptools based setup module.'''

from setuptools import setup

from codecs import open
from os import path

import mqtt_gateways.version

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='mqtt_gateways',
    version=mqtt_gateways.version.version,
    description='Framework for MQTT Gateways',
    long_description=long_description,
    #long_description_content_type='text/x-rst', # apparently it is optional if rst
    url='http://mqtt-gateways.readthedocs.io/en/latest/',
    author='Pier Paolo Taddonio',
    author_email='paolo.taddonio@empiluma.com',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        ],
    keywords='mqtt gateway',
    package_dir={'':'mqtt_gateways'},
    packages=['gateway', 'dummy', 'entry', 'musiccast'],
    install_requires=['paho-mqtt >= 1.3.1','pySerial >= 3.4'],
    #package_data={'mqtt_gateways': ['data/*.map', 'data/*.conf']},
    exclude_package_data={'': ['README.*']},
    entry_points={'console_scripts': ['dummy2mqtt = mqtt_gateways.dummy.dummy2mqtt:__main__'],
                  'console_scripts': ['entry2mqtt = mqtt_gateways.entry.entry2mqtt:__main__'],
                  'console_scripts': ['musiccast2mqtt = mqtt_gateways.musiccast.musiccast2mqtt:__main__']}
)
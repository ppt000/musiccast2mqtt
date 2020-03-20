''' setup file for mqttgateway '''

from setuptools import setup, find_packages

from codecs import open
from os import path

from musiccast2mqtt import __version__

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'docs/source/readme.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='musiccast2mqtt',
    version=__version__,
    description='MQTT gateway for Yamaha MusicCast devices.',
    long_description=long_description,
    #long_description_content_type='text/x-rst', # apparently it is optional if rst
    url='http://musiccast2mqtt.readthedocs.io/en/latest/',
    author='Pier Paolo Taddonio',
    author_email='paolo.taddonio@empiluma.com',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7'
        ],
    keywords='mqtt gateway Yamaha MusicCast',
    packages=find_packages(),
    install_requires=['mqttgateway >= 0.205'],
    package_data={'': ['*.conf', '*.json']},
    entry_points={'console_scripts': ['musiccast2mqtt = musiccast2mqtt.musiccast_start:main']}
)
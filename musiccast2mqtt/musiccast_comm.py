''' Low-level communication with the MusicCast system.

.. Reviewed 9 November 2018
'''

import socket
import httplib
import json
import time
import logging

import musiccast2mqtt as mcc

LOG = logging.getLogger(__name__)

class musiccastComm(object):
    ''' Manages the low-level calls to the MusicCast devices.

    Every instance represents a single live connection to a given MusicCast
    device, represented simply by a host address.

    Args:
        host (string): the HTTP address for the host, as recognisable
            by the httplib library.
        api_port (int): the port of the API where to send the HTTP requests.
        listen_port (int): the port where to listen for events; has to go in the headers.
    '''

    def __init__(self, host, api_port, listen_port):
        self._host = host
        self._api_port = api_port
        self._timeout = mcc.HTTP_TIMEOUT
        self._headers = {'X-AppName': 'MusicCast/0.2(musiccast2mqtt)',
                         'X-AppPort': str(listen_port)}
        self.request_time = 0
        self.mcrequest = self._mcrequest

    def disable(self):
        ''' Disables the requests for this connection.'''
        self.mcrequest = self._dummy
        return

    def _dummy(self, qualifier, mc_command):
        ''' Does nothing.'''
        return

    def _mcrequest(self, qualifier, mc_command):
        ''' Sends a single HTTP request and returns the response.

        This method sends the request and read the response step by step in
        order to catch properly any error in the process. Currently the requests
        are always with method = 'GET' and version = 'v1'.

        Args:
            qualifier (string): the token in the MusicCast syntax representing
                either a zone or a source, depending on the type of command
                sent;
            mc_command (string): the command to send at the end of the request;
                it has to include any extra argument if there are any.

        Raises:
            commsError: in case of any form of Communication Error with the device.

        Returns:
            dictionary: the dictionary equivalent of the JSON structure sent back as a reply
                from the device.
        '''

        remaining_lag = mcc.REQUESTS_LAG - (time.time() - self.request_time)
        if remaining_lag > 0:
            time.sleep(remaining_lag)

        conn = httplib.HTTPConnection(host=self._host, port=self._api_port, timeout=self._timeout)

        LOG.debug(''.join(('Sending to address <', self._host, '> the request: ',
                               '/'.join(('/YamahaExtendedControl/v1', qualifier, mc_command)))))

        try: conn.request(method='GET',
                          url='/'.join(('/YamahaExtendedControl/v1',
                                        qualifier, mc_command)),
                          headers=self._headers)
        except httplib.HTTPException as err:
            conn.close()
            raise mcc.CommsError(''.join(('Can\'t send request. Error:\n\t', str(err))))
        except socket.timeout:
            conn.close()
            raise mcc.CommsError('Can\'t send request. Connection timed-out.')
        except socket.error as err:
            conn.close()
            raise mcc.CommsError(''.join(('Can\'t send request. Socket error:\n\t', str(err))))

        # insert a delay here?

        try: response = conn.getresponse()
        except httplib.HTTPException as err:
            conn.close()
            raise mcc.CommsError(''.join(('Can\'t get response. Error:\n\t', str(err))))
        except socket.timeout:
            conn.close()
            raise mcc.CommsError('Can\'t get response. Connection timed-out.')
        except socket.error as err:
            conn.close()
            raise mcc.CommsError(''.join(('Can\'t get response. Socket error:\n\t', str(err))))

        if response.status != 200:
            conn.close()
            raise mcc.CommsError(''.join(('HTTP response status not OK.'\
                                          '\n\tStatus: ', httplib.responses[response.status],
                                          '\n\tReason: ', response.reason)))

        try: dict_response = json.loads(response.read())
        except ValueError as err:
            conn.close()
            raise mcc.CommsError(''.join(('The response from the device is not'\
                                          ' in JSON format. Error:\n\t', str(err))))

        if dict_response['response_code'] != 0:
            conn.close()
            raise mcc.CommsError(''.join(('The response code from the'\
                                          ' MusicCast device is not OK. Actual code:\n\t',
                                          str(dict_response['response_code']))))

        LOG.debug('Request answered successfully.')

        conn.close()
        self.request_time = time.time()
        return dict_response

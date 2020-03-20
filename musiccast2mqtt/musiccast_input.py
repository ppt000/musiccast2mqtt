''' Representation of Inputs

.. reviewed 9 November 2018
'''

import logging

import musiccast2mqtt as mcc

LOG = logging.getLogger(__name__)

class Input(object):
    ''' Represents an input on the device.

    Args:
        input_data (dict): input data from getFeatures
        device (:class:`Device`): the parent device
    '''
    def __init__(self, input_data, device):
        self.input_data = input_data
        try:
            self.input_mcid = input_data['id']
        except KeyError:
            mcc.CommsError('getFeatures does not have the "id" field.')
        self.device = device
        play_info_type = self.device.get_feature(('system', 'input_list',
                                                  {'id': self.input_mcid}, 'play_info_type'))
        self.playinfo_type = self.device.init_infotype(play_info_type)
        return

class Feed(Input):
    ''' Represents an input on the device that is not a source.

    A feed within a MusicCast system is an input for which the `play_info_type`
    field within the getFeatures structure is set to **none**.

    Args:
        feed_data (data): the feed data
        device (:class:`Device`): the parent device.
    '''
    def __init__(self, feed_data, device):
        super(Feed, self).__init__(feed_data, device)
        return

class Source(Input):
    ''' Represents a source on the device.

    A source within a MusicCast system is an input for which the
    ``play_info_type`` field within the getFeatures structure is set to a
    different value than ``none``, normally either ``cd``, ``tuner`` or
    ``netusb``.

    Args:
        source_data (dict): the source data
        device (:class:`Device`): the parent device.
    '''
    def __init__(self, source_data, device):
        super(Source, self).__init__(source_data, device)
        return

''' Exceptions definitions for the MusicCast package.

.. reviewed 31 May 2018

All are inherited from the Exception class, with the member
'message' available.
'''

class AnyError(Exception):
    ''' All the errors from this package'''
    pass

class CommsError(AnyError):
    ''' Communication errors'''
    pass

class LogicError(AnyError):
    ''' Logic errors'''
    pass

class ConfigError(AnyError):
    ''' Configuration errors'''
    pass

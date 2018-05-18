'''
Exceptions definitions for the MusicCast package.

All are inherited from the Exception class, with the member
'message' available.

Types of Errors:

* CommsError: any type of communication error which should not be due
    to a bad command or a command issued at the wrong time.
*

'''

# TODO: Categorise errors =====================================================
# Connection not working
# Device offline?
# Wrong commands, not recognised
# Data read not as expected
# Arguments from commands missing or wrong type

class AnyError(Exception):
    ''' Docstring'''
    pass

class CommsError(AnyError):
    ''' Docstring'''
    pass

class LogicError(AnyError):
    ''' Docstring'''
    pass

class ConfigError(AnyError):
    ''' Docstring'''
    pass

class MusicCastError(AnyError):
    ''' Docstring'''
    pass

#===============================================================================
#
#
# class mcConfigError(AnyError): #DONE
#     pass
#
# class mcConnectError(AnyError): # DONE
#     ''' There is no connection, so network might be down, or
#     local interface not working...'''
#     pass
#
# class mcDeviceError(AnyError): # DONE
#     ''' The device responds but could not execute whatever was asked.'''
#     pass
#
# class mcSyntaxError(AnyError): #DONE
#     pass
#
# class mcHTTPError(AnyError): # DONE
#     ''' Protocol error, there was misunderstanding in the communication.'''
#     pass
#
# class mcLogicError(AnyError): # DONE
#     pass
#
# class mcProtocolError(AnyError):
#     pass
#===============================================================================

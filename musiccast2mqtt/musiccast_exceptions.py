'''
Exceptions definitions for the MusicCast package.

All are inherited from the Exception class, with the member
'message' available.

Types of Errors:

* CommsError: any type of communication error which should not be due
    to a bad command or a command issued at the wrong time.
*

'''

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


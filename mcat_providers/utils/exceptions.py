class IntegrityError(ValueError):
    '''Generic Error for instances such as a checksum mismatch when hashing files.'''

class DisabledError(ValueError):
    '''Generic Error for disabled providers/sources'''

class DisabledProviderError(DisabledError):
    '''Generic Error for disabled provider'''

class DisabledSourceError(DisabledError):
    '''Generic Error for disabled source'''
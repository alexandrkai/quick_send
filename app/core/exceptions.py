# app/core/exceptions.py
class ConsentException(Exception):
    pass
class ChannelException(Exception):
    pass
class ContactNotFoundError(Exception):
    pass

class ContactAlreadyExistsError(Exception):
    pass
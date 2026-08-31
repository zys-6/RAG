import platform
import random
import uuid


def is_windows():
    return 'windows' in platform.system().lower()


def get_uuid_string():
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(uuid.uuid1()) + str(random.random())))

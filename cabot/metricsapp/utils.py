import re
import logging

logger = logging.getLogger(__name__)


def interval_str_to_int(interval_str):
    '''
    Given an interval string of the form "<count>[smhd]" (eg: "30s", "10m", "1h"),
    convert the string to an integer representing the number of seconds in the interval.
    :param interval_str: string to convert
    :return: seconds in interval, as an integer
    :raises: ValueError if unable to convert the interval string
    '''
    # Convert the string to an integer and return it
    m = re.search('^(\d+)([smhd])$', interval_str)
    if m:
        count = int(m.group(1))
        type = m.group(2)
        if type == 's':
            return count
        if type == 'm':
            return count * 60
        if type == 'h':
            return count * 60 * 60
        if type == 'd':
            return count * 60 * 60 * 24

    # Unable to convert. Raise an error.
    message = "Unable to convert interval string '{}' to an integer".format(interval_str)
    logger.exception(message)
    raise ValueError(message)

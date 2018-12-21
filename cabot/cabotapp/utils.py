from django.conf import settings
from datetime import datetime


def build_absolute_url(relative_url):
    """Prepend https?://host to a url, useful for links going into emails"""
    return '{}://{}{}'.format(settings.WWW_SCHEME, settings.WWW_HTTP_HOST, relative_url)


def format_datetime(dt):
    '''
    Convert datetime to string. None is converted to empty string. This is used
    primarily for formatting datetimes in API responses, whereas format_timestamp
    is used for a more human-readable format to be displayed on the web.
    '''
    return '' if dt is None else datetime.strftime(dt, '%Y-%m-%d %H:%M:%S')

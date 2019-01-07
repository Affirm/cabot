from django.conf import settings
from mock import Mock
from cabot.cabotapp import defs
from datetime import datetime


def build_absolute_url(relative_url):
    """Prepend https?://host to a url, useful for links going into emails"""
    return '{}://{}{}'.format(settings.WWW_SCHEME, settings.WWW_HTTP_HOST, relative_url)


def create_failing_service_mock():
    """
    Create a Mock object mimicking a critical service, with a single (also mocked) failing check.

    Note that not all attributes are mocked (notably hipchat_instance, mattermost_instance).
    Primary keys/IDs are mocked to be 0. Functions that return querysets in reality (like active_status_checks)
    will return hard-coded lists.

    This is typically called by an AlertPlugin.send_test_alert() implementation, and further configured by calling
    service_mock.configure_mock(attr=value, ...) to add any plugin-specific attributes (like mattermost_instance).
    :return: Mock emulating a service with 1 failing check
    """
    check_mock = Mock()
    check_mock.configure_mock(id=0, pk=0, name='Alert Testing Check', active=True,
                              get_status_image=lambda: None, check_category=lambda: "Mock Check",
                              get_importance_display=lambda: "Critical")

    service_mock = Mock()

    service_mock.configure_mock(id=0, pk=0, name='Alert Testing Service', alerts_enabled=True,
                                # plugins use service.CRITICAL_STATUS etc, so we mock these constants too
                                CRITICAL_STATUS=defs.CRITICAL_STATUS, PASSING_STATUS=defs.PASSING_STATUS,
                                WARNING_STATUS=defs.WARNING_STATUS, ERROR_STATUS=defs.ERROR_STATUS,
                                status_checks=[check_mock], recent_snapshots=[],
                                overall_status=defs.CRITICAL_STATUS,
                                active_status_checks=lambda: [check_mock],
                                all_passing_checks=lambda: [], all_failing_checks=lambda: [check_mock])

    return service_mock


def format_datetime(dt):
    '''
    Convert datetime to string. None is converted to empty string. This is used
    primarily for formatting datetimes in API responses, whereas format_timestamp
    is used for a more human-readable format to be displayed on the web.
    '''
    return '' if dt is None else datetime.strftime(dt, '%Y-%m-%d %H:%M:%S')

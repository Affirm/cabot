import logging

from django.db import models
from polymorphic import PolymorphicModel

from cabot.cabotapp.utils import create_failing_service_mock

logger = logging.getLogger(__name__)


class AlertPlugin(PolymorphicModel):
    title = models.CharField(max_length=30, unique=True, editable=False)
    enabled = models.BooleanField(default=True)

    author = None
    # Plugins use name field
    name = 'noop'

    def __unicode__(self):
        return u'%s' % (self.title)

    def send_alert(self, service, users, duty_officers):
        """
        Implement a send_alert function here that shall be called.
        """
        return True

    def send_test_alert(self, user):
        """
        Send a test alert when the user requests it (to make sure config is valid).

        The default implementation creates a fake Service and StatusCheck and calls the normal send_alert().
        Note that the service/check may not be fully configured (e.g. invalid primary key, no HipChat room ID, ...).
        :param user: django user
        :return: nothing, raise exceptions on error
        """
        service_mock = create_failing_service_mock()
        self.send_alert(service_mock, [], [user])


class AlertPluginUserData(PolymorphicModel):
    title = models.CharField(max_length=30, editable=False)
    user = models.ForeignKey('UserProfile', editable=False)

    # This is used to add the "Send Test Alert" button to the edit page.
    # We need this information to be able to map AlertPluginUserData subclasses to their AlertPlugins.
    # It's a list because some plugins (like Twilio) have multiple alert types for one user data type.
    alert_classes = []

    class Meta:
        unique_together = ('title', 'user',)

    def __unicode__(self):
        return u'%s' % (self.title)

    def is_configured(self):
        """
        Override this to show warnings in the profile sidebar when something's not set up (i.e. a field is empty).

        NOTE: This does NOT do validation when submitting the 'update profile' form. You should specify
        models.SomeField(validators=[...]) when declaring your model's fields for that.
        """
        return True


def send_alert(service, duty_officers=[], fallback_officers=[]):
    users = service.users_to_notify.filter(is_active=True)
    for alert in service.alerts.all():
        try:
            alert.send_alert(service, users, duty_officers)
        except Exception:
            logging.exception('Could not sent {} alert'.format(alert.name))
            if fallback_officers:
                try:
                    alert.send_alert(service, users, fallback_officers)
                except Exception:
                    logging.exception('Could not send {} alert to fallback officer'.format(alert.name))


def update_alert_plugins():
    for plugin_subclass in AlertPlugin.__subclasses__():
        plugin_subclass.objects.get_or_create(title=plugin_subclass.name)
    return AlertPlugin.objects.all()

import logging

from datetime import timedelta
from django.db import models
from django.utils import timezone
from polymorphic import PolymorphicModel

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


class AlertPluginUserData(PolymorphicModel):
    title = models.CharField(max_length=30, editable=False)
    user = models.ForeignKey('UserProfile', editable=False)

    class Meta:
        unique_together = ('title', 'user',)

    def __unicode__(self):
        return u'%s' % (self.title)


def send_alert(service, duty_officers=None,
               escalation_officers=None,
               fallback_officers=None):

    duty_officers = duty_officers or []
    escalation_officers = escalation_officers or []
    fallback_officers = fallback_officers or []

    escalation_cutoff = timezone.now() - timedelta(
        minutes=service.escalate_after)

    users = service.users_to_notify.filter(is_active=True)

    for alert in service.alerts.all():
        for user_list in [duty_officers, escalation_officers, fallback_officers]:
            if not user_list:
                continue
            try:
                alert.send_alert(service, users, user_list)
                break
            except Exception:
                logging.exception('Could not sent {} alert'.format(alert.name))

                if escalation_cutoff < service.last_alert_sent:
                    logging.info('Service {}: Not escalating {}'.format(
                        service.name, alert.name))
                    break


def update_alert_plugins():
    for plugin_subclass in AlertPlugin.__subclasses__():
        plugin_subclass.objects.get_or_create(title=plugin_subclass.name)
    return AlertPlugin.objects.all()

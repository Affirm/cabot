import logging

from django.core.mail import send_mail
from django.db import models
import os
from polymorphic import PolymorphicModel
from cabot_alert_hipchat.models import HipchatAlert, HipchatAlertUserData
from cabot_alert_twilio.models import TwilioPhoneCall, TwilioSMS, TwilioUserData

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


def alert_duty_officer_missing_info(service_list, duty_officers, fallback_officers):
    """
    Check that new oncall officers have their information set up.
    :param service_list: services the users are on call for
    :param duty_officers: officers that are supposed to be on call
    :param fallback_officers: fallback officers for the schedule (will be emailed about missing info)
    """
    alerts = []
    for service in service_list:
        alerts.extend([type(alert) for alert in service.alerts.all()])

    emails = [u.email for u in duty_officers] + [u.email for u in fallback_officers]
    for user in duty_officers:
        if HipchatAlert in alerts:
            hipchat_alias_list = HipchatAlertUserData.objects.filter(user=user)
            if hipchat_alias_list == [] or hipchat_alias_list[0] == '':
                _send_missing_info_email(user, 'Hipchat', emails)

        if TwilioPhoneCall in alerts or TwilioSMS in alerts:
            phone_number_list = TwilioUserData.objects.filter(user=user)
            if phone_number_list == [] or len(phone_number_list[0]) < 10:
                _send_missing_info_email(user, 'Twilio', emails)


def _send_missing_info_email(officer, alert_type, emails):
    """
    Send an email about a duty officer missing profile info.
    :param officer: the officer who is missing info
    :param alert_type: the type of alert info is missing for
    :param emails: list of users to email
    """
    subject = 'Cabot Duty Officer {} Missing Information'.format(officer.email)
    body = 'Missing {} info for {}. Make sure all contact details are up to date in the profile page.'.format(
        alert_type, officer.email
    )
    send_mail(
        subject=subject,
        message=body,
        from_email='Cabot {}'.format(os.environ.get('CABOT_FROM_EMAIL')),
        recipients=emails
    )

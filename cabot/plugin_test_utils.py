# -*- coding: utf-8 -*-
from django.utils import timezone
from django.contrib.auth.models import Permission, User
from rest_framework.test import APITestCase

from cabot.cabotapp.alert import update_alert_plugins
from cabot.cabotapp.models import (
    JenkinsStatusCheck,
    HttpStatusCheck,
    TCPStatusCheck,
    Service,
    StatusCheckResult,
    Schedule,
    Shift,
    get_duty_officers,
    get_fallback_officers,
    UserProfile)


class PluginTestCase(APITestCase):
    """
    Sets up the following testing environment:

    .. code-block:: yaml

        self.user:
          email: test@test.test
          username: testuser

        self.duty_officer:
          email: dolores@affirm.com
          username: dolores@affirm.com

        self.fallback_officer:
          email: teddy@affirm.com
          username: teddy@affirm.com

        self.schedule:
          shifts: self.duty_officer
          fallback_officer: self.fallback_officer

        self.jenkins_check:
          name: Jenkins Check
          importance: Error

        self.http_check:
          name: Http Check
          importance: Critical

        self.tcp_check:
          name: TCP Check
          importance: Error

        self.service:
          name: Service
          users_to_notify:
            - self.user
          schedules:
            - self.schedule
          checks:
            - self.http_check
            - self.jenkins_check
            - self.tcp_check

    Make sure you add your alert type in setUp() before testing, like so:

        def setUp(self):
            # call the base class to set up the environment described above
            super(MyCoolPluginTestCase, self).setUp()

            # add the email alert to the test service
            self.email_alert = EmailAlert.objects.get(title=models.EmailAlert.name)
            self.service.alerts.add(self.email_alert)
            self.service.save()

    This class provides two helper functions to help with testing:
        transition_service(old_status, new_status)
    and
        run_checks([(check, passed, acked), ...], from_service_status)

    If your alert type builds a message based on the state of a service's checks (which most plugins do), you should
    probably use run_checks() to simulate failing checks and verify you build your message as expected.
    Otherwise, you can use transition_service() for a simple Service status-based test.

    For example, to run the Jenkins, HTTP, and TCP checks, with the states failing, acked,
    then updating the service (coming from the 'PASSING' status):

        run_checks([
            (self.jenkins_check, False, False),
            (self.http_check, False, True),
            (self.tcp_check, True, True)],
            Service.PASSING_STATUS)

    Or you can just test with the service status, if you don't care about check states:

        transition_service(Service.PASSING_STATUS, Service.ERROR_STATUS)

    You should probably at least test the following situations:
    * passing -> warning
    * passing -> error
    * error -> passing
    * error -> acked
    """
    def setUp(self):
        update_alert_plugins()

        self.user = User.objects.create(username='testuser', password='testuserpassword', email='test@test.test')
        self.user.user_permissions.add(
            Permission.objects.get(codename='add_service'),
            Permission.objects.get(codename='add_httpstatuscheck'),
            Permission.objects.get(codename='add_jenkinsstatuscheck'),
            Permission.objects.get(codename='add_tcpstatuscheck'),
        )
        self.user.save()

        self.jenkins_check = JenkinsStatusCheck.objects.create(
            id=10101,
            name='Jenkins Check',
            created_by=self.user,
            importance=Service.ERROR_STATUS,
            max_queued_build_time=10,
            max_build_failures=5
        )

        self.http_check = HttpStatusCheck.objects.create(
            id=10102,
            name='Http Check',
            created_by=self.user,
            importance=Service.CRITICAL_STATUS,
            endpoint='https://google.com',
            timeout=10,
            status_code='200',
            text_match=None,
        )
        self.tcp_check = TCPStatusCheck.objects.create(
            id=10103,
            name='TCP Check',
            created_by=self.user,
            importance=Service.ERROR_STATUS,
            address='github.com',
            port=80,
            timeout=6,
        )

        self.service = Service.objects.create(id=2194, name='Service')

        self.service.status_checks.add(
            self.jenkins_check,
            self.http_check,
            self.tcp_check
        )

        self.service.users_to_notify.add(self.user)

        self.duty_officer = User.objects.create(
            username='dolores@affirm.com',
            password='fakepassword',
            email='dolores@affirm.com',
            is_active=True
        )
        self.fallback_officer = User.objects.create(
            username='teddy@affirm.com',
            password='fakepassword',
            email='teddy@affirm.com',
            is_active=True
        )

        self.schedule = Schedule.objects.create(name='Test Schedule', fallback_officer=self.fallback_officer)
        Shift.objects.create(user=self.duty_officer,
                             start=timezone.now() - timezone.timedelta(minutes=1),
                             end=timezone.now() + timezone.timedelta(hours=1),
                             schedule=self.schedule)
        self.service.schedules.add(self.schedule)

        self.assertEquals(get_duty_officers(self.schedule), [self.duty_officer])
        self.assertEquals(get_fallback_officers(self.schedule), [self.fallback_officer])

        self.service.update_status()  # set initial status

        # make sure all users have profiles
        for user in self.user, self.duty_officer, self.fallback_officer:
            UserProfile.objects.create(user=user)

        super(PluginTestCase, self).setUp()

    def run_checks(self, checks, from_service_status=None):
        # type: (List[Tuple[StatusCheck, bool, bool]], Union[None, str]) -> None
        """
        Simulates running the given checks with the given results, then updates the service (triggering alerts).
        :param checks: list of (check, succeeded, acked) tuples
        :param from_service_status: specify the service status to transition from (service.old_overall_status), optional
        """
        # clear any previous results
        StatusCheckResult.objects.all().delete()

        for check, succeeded, acked in checks:
            now = timezone.now()
            result = StatusCheckResult(check=check, time=now, time_complete=now, succeeded=succeeded)
            if hasattr(StatusCheckResult, 'acked'):  # forwards-compatible with acks
                result.acked = acked
            result.save()

            check.last_run = now
            check.save()

        if from_service_status:
            self.service.overall_status = from_service_status

        self.service.update_status()

    def transition_service(self, old_status, new_status):
        """
        Set old and current service state (ignoring check states), then trigger alert.
        """
        self.service.old_overall_status = old_status
        self.service.overall_status = new_status
        self.service.last_alert_sent = None

        if self.service.alerts.count() == 0:
            print("transition_service warning: self.service has no alerts registered")

        self.service.alert()

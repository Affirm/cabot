# -*- coding: utf-8 -*-
from django.utils import timezone
from django.contrib.auth.models import Permission, User
from mock import Mock
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
    UserProfile)
from cabot.metricsapp.models import ElasticsearchStatusCheck, ElasticsearchSource


class PluginTestCase(APITestCase):
    """
    This class provides a common testing environment and utility functions for testing Cabot alert plugins.
    The environment includes a service with each type of check, a user on the "users to notify" list, and a
    schedule with an on-call and fallback officer. This class also includes some utility functions for
    testing service states (transition_service_status) and check states (run_checks).

    setUp() sets up the following testing environment:

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

        self.es_check:
          name: ES Metric Check
          importance: Error
          get_status_image: Mock()

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

            # add e.g. the email alert to the test service
            self.email_alert = EmailAlert.objects.get(title=models.EmailAlert.name)
            self.service.alerts.add(self.email_alert)
            self.service.save()

    This class provides two helper functions which set some state then trigger alerts:
        transition_service_status(old_status, new_status)
    and
        run_checks([(check, passed, acked), ...], from_service_status)

    If your alert type builds a message based on the state of a service's checks (which most plugins do), you should
    probably use run_checks() to simulate failing checks and verify you build your message as expected.
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

        self.es_source = ElasticsearchSource.objects.create(
            name='es',
            urls='localhost',
            index='test-index-pls-ignore'
        )

        self.es_check = ElasticsearchStatusCheck.objects.create(
            id=10104,
            name='ES Metric Check',
            created_by=self.user,
            source=self.es_source,
            check_type='>=',
            warning_value=3.5,
            importance=Service.ERROR_STATUS,
            high_alert_importance=Service.CRITICAL_STATUS,
            high_alert_value=3.0,
            queries='[{"query": {"bool": {"must": [{"query_string": {"analyze_wildcard": true, '
                    '"query": "test.query"}}, {"range": {"@timestamp": {"gte": "now-300m"}}}]}}, '
                    '"aggs": {"agg": {"terms": {"field": "outstanding"}, '
                    '"aggs": {"agg": {"date_histogram": {"field": "@timestamp", "interval": "1m", '
                    '"extended_bounds": {"max": "now", "min": "now-3h"}}, '
                    '"aggs": {"sum": {"sum": {"field": "count"}}}}}}}}]',
            time_range=10000
        )
        ElasticsearchStatusCheck.get_status_image = Mock()

        self.service = Service.objects.create(id=2194, name='Service')

        self.service.status_checks.add(
            self.jenkins_check,
            self.http_check,
            self.tcp_check,
            self.es_check,
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

        self.service.update_status()  # set initial status

        # make sure all users have profiles
        for user in self.user, self.duty_officer, self.fallback_officer:
            UserProfile.objects.create(user=user)

        super(PluginTestCase, self).setUp()

    def run_checks(self, checks, from_service_status=None):
        # type: (List[Tuple[StatusCheck, bool, bool]], Union[None, str]) -> None
        """
        Simulates running the given checks with the given results, then updates the service (triggering alerts).
        All previous StatusCheckResults are cleared by calling this function. A check can be listed more than once.
        You should set up self.service.alerts before calling this.
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

    def transition_service_status(self, old_status, new_status):
        # type: (str, str) -> None
        """
        Set old and current service state (ignoring check states) to simulate the service
        transitioning between statuses, then triggers alerts.
        You should set up self.service.alerts before calling this.
        :param old_status old service status (Service.PASSING_STATUS, ...)
        :param new_status new service status (Service.ERROR_STATUS, ...)
        """
        self.service.old_overall_status = old_status
        self.service.overall_status = new_status
        self.service.last_alert_sent = None

        if self.service.alerts.count() == 0:
            print("transition_service_status warning: self.service has no alerts registered")

        self.service.alert()

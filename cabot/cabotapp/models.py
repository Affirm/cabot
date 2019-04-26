import errno

from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.core.validators import MaxValueValidator
from django.db import models, transaction
from polymorphic.models import PolymorphicModel
from timezone_field import TimeZoneField

from .jenkins import get_job_status
from .alert import (send_alert, AlertPluginUserData)
from cabot.cabotapp.models_plugins import (  # noqa (unused, imported for side effects)
    HipchatInstance,
    MatterMostInstance,
)
from cabot.cabotapp import defs
from cabot.cabotapp.fields import PositiveIntegerMaxField

from collections import defaultdict
from datetime import timedelta
from django.utils import timezone
from icalendar import Calendar

import re
import socket
import time
import yaml

import requests
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


def clone_model(model):
    '''
    Utility function to clone a model. You must set both `id` and `pk` to
    `None`, and then save it. It will store a new copy of the model in the
    database, with a new primary key.
    https://docs.djangoproject.com/en/2.0/topics/db/queries/#copying-model-instances
    '''
    model.id = None
    model.pk = None
    model.save()


def serialize_recent_results(recent_results):
    if not recent_results:
        return ''

    def result_to_value(result):
        if result.succeeded:
            return '1'
        else:
            return '-1'
    vals = [result_to_value(r) for r in recent_results]
    vals.reverse()
    return ','.join(vals)


def get_success_with_retries(recent_results, retries=0):
    """
    `retries` are the number of previous failures we need (not including this)
    to mark a search as passing or failing
    Returns:
      True if passing given number of retries
      False if failing
    """
    if not recent_results:
        return True
    retry_window = recent_results[:retries + 1]
    for r in retry_window:
        if r.succeeded:
            return True
    return False


class CheckGroupMixin(models.Model):

    class Meta:
        abstract = True

    PASSING_STATUS = defs.PASSING_STATUS
    ACKED_STATUS = defs.ACKED_STATUS
    WARNING_STATUS = defs.WARNING_STATUS
    ERROR_STATUS = defs.ERROR_STATUS
    CRITICAL_STATUS = defs.CRITICAL_STATUS

    CALCULATED_PASSING_STATUS = 'passing'
    CALCULATED_ACKED_STATUS = 'acked'
    CALCULATED_INTERMITTENT_STATUS = 'intermittent'
    CALCULATED_FAILING_STATUS = 'failing'

    STATUSES = (
        (CALCULATED_PASSING_STATUS, CALCULATED_PASSING_STATUS),
        (CALCULATED_ACKED_STATUS, CALCULATED_ACKED_STATUS),
        (CALCULATED_INTERMITTENT_STATUS, CALCULATED_INTERMITTENT_STATUS),
        (CALCULATED_FAILING_STATUS, CALCULATED_FAILING_STATUS),
    )

    IMPORTANCES = (
        (WARNING_STATUS, 'Warning'),
        (ERROR_STATUS, 'Error'),
        (CRITICAL_STATUS, 'Critical'),
    )

    name = models.TextField()

    users_to_notify = models.ManyToManyField(
        User,
        blank=True,
        help_text='Users who should receive alerts.',
    )
    schedules = models.ManyToManyField(
        'Schedule',
        blank=True,
        help_text='Oncall schedule to be alerted.'
    )
    alerts_enabled = models.BooleanField(
        default=True,
        help_text='Alert when this service is not healthy.',
    )
    status_checks = models.ManyToManyField(
        'StatusCheck',
        blank=True,
        help_text='Checks used to calculate service status.',
    )
    last_alert_sent = models.DateTimeField(
        null=True,
        blank=True,
    )

    alerts = models.ManyToManyField(
        'AlertPlugin',
        blank=True,
        help_text='Alerts channels through which you wish to be notified'
    )

    email_alert = models.BooleanField(default=False)
    hipchat_alert = models.BooleanField(default=True)
    sms_alert = models.BooleanField(default=False)
    telephone_alert = models.BooleanField(
        default=False,
        help_text='Must be enabled, and check importance set to Critical, to receive telephone alerts.',
    )
    overall_status = models.TextField(default=PASSING_STATUS)
    old_overall_status = models.TextField(default=PASSING_STATUS)
    hackpad_id = models.TextField(
        null=True,
        blank=True,
        verbose_name='Recovery instructions',
        help_text='Gist, Hackpad or Refheap js embed with recovery instructions e.g. '
                  'https://you.hackpad.com/some_document.js'
    )
    hipchat_instance = models.ForeignKey(
        'HipchatInstance',
        null=True,
        blank=True,
        help_text='Hipchat instance to send Hipchat alerts to (can be none if Hipchat alerts disabled).',
        on_delete=models.SET_NULL
    )
    hipchat_room_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Id of the Hipchat room to be alerted for this service (can be none).'
    )
    mattermost_instance = models.ForeignKey(
        'MatterMostInstance',
        null=True,
        blank=True,
        help_text='Mattermost instance to send alerts to (can be blank if Mattermost alerts are disabled).',
        on_delete=models.SET_NULL
    )
    mattermost_channel_id = models.CharField(
        null=True,
        blank=True,
        max_length=32,
        help_text='ID of the Mattermost room to be alerted for this service (leave blank for default).'
    )

    def __unicode__(self):
        return self.name

    def most_severe(self, check_list):
        # if a check is acked, instead of importance use ACKED_STATUS
        failures = [c.importance if not c.calculated_status == Service.CALCULATED_ACKED_STATUS
                    else self.ACKED_STATUS
                    for c in check_list]
        if self.CRITICAL_STATUS in failures:
            return self.CRITICAL_STATUS
        if self.ERROR_STATUS in failures:
            return self.ERROR_STATUS
        if self.WARNING_STATUS in failures:
            return self.WARNING_STATUS
        if self.ACKED_STATUS in failures:
            return self.ACKED_STATUS
        return self.PASSING_STATUS

    @property
    def is_critical(self):
        """
        Break out separately because it's a bit of a pain to
        get wrong.
        """
        if self.old_overall_status != self.CRITICAL_STATUS and self.overall_status == self.CRITICAL_STATUS:
            return True
        return False

    def alert(self):
        if not self.alerts_enabled:
            return
        if self.overall_status != self.PASSING_STATUS:
            # We want to alert if the status changes no matter what
            if self.overall_status == self.old_overall_status:
                # Don't alert every time if status hasn't changed
                if self.overall_status == self.ACKED_STATUS:
                    # don't ever retrigger alerts for sustained acked status (it's not necessary)
                    return
                elif self.overall_status == self.WARNING_STATUS:
                    if self.last_alert_sent and (timezone.now() - timedelta(minutes=settings.NOTIFICATION_INTERVAL)) \
                            < self.last_alert_sent:
                        return
                elif self.overall_status in (self.CRITICAL_STATUS, self.ERROR_STATUS):
                    if self.last_alert_sent and (timezone.now() - timedelta(minutes=settings.ALERT_INTERVAL)) \
                            < self.last_alert_sent:
                        return
            self.last_alert_sent = timezone.now()
        else:
            # We don't count "back to normal" as an alert
            self.last_alert_sent = None
        self.save()
        self.snapshot.did_send_alert = True
        self.snapshot.save()

        schedules = self.schedules.all()

        if not schedules:
            send_alert(self)

        for schedule in schedules:
            send_alert(self, duty_officers=get_duty_officers(schedule),
                       fallback_officers=get_fallback_officers(schedule))

    @property
    def recent_snapshots(self):
        snapshots = self.snapshots.filter(
            time__gt=(timezone.now() - timedelta(minutes=60 * 24)))
        snapshots = list(snapshots.values())
        for s in snapshots:
            s['time'] = time.mktime(s['time'].timetuple())
        return snapshots

    # order checks by: critical + failing, error + failing, warning + failing, passing, disabled
    _CHECK_ORDER = "(CASE " \
                   "WHEN calculated_status = '{failing}' AND importance = '{critical}' THEN 1 " \
                   "WHEN calculated_status = '{failing}' AND importance = '{error}' THEN 2 " \
                   "WHEN calculated_status = '{failing}' AND importance = '{warning}' THEN 3 " \
                   "WHEN active = false THEN 99 " \
                   "ELSE 4 " \
                   "END)".format(failing=CALCULATED_FAILING_STATUS,
                                 intermittent=CALCULATED_INTERMITTENT_STATUS,
                                 passing=CALCULATED_PASSING_STATUS,
                                 critical=CRITICAL_STATUS,
                                 error=ERROR_STATUS,
                                 warning=WARNING_STATUS)

    def _order_checks(self, q):
        # break ties by name
        return q.extra(select={'o': self._CHECK_ORDER}, order_by=('o', 'name'))

    def http_status_checks(self):
        return self._order_checks(self.status_checks.filter(polymorphic_ctype__model='httpstatuscheck'))

    def jenkins_status_checks(self):
        return self._order_checks(self.status_checks.filter(polymorphic_ctype__model='jenkinsstatuscheck'))

    def tcp_status_checks(self):
        return self._order_checks(self.status_checks.filter(polymorphic_ctype__model='tcpstatuscheck'))

    def elasticsearch_status_checks(self):
        return self._order_checks(self.status_checks.filter(polymorphic_ctype__model='elasticsearchstatuscheck'))

    def active_http_status_checks(self):
        return self.http_status_checks().filter(active=True)

    def active_jenkins_status_checks(self):
        return self.jenkins_status_checks().filter(active=True)

    def active_tcp_status_checks(self):
        return self.tcp_status_checks().filter(active=True)

    def active_status_checks(self):
        return self.status_checks.filter(active=True)

    def inactive_status_checks(self):
        return self.status_checks.filter(active=False)

    def all_passing_checks(self):
        return self.active_status_checks().filter(calculated_status=self.CALCULATED_PASSING_STATUS)

    def all_failing_checks(self):
        return self.active_status_checks().exclude(calculated_status=self.CALCULATED_PASSING_STATUS)


class Schedule(models.Model):
    name = models.CharField(
        unique=True,
        max_length=50,
        help_text='Display name for the oncall schedule.')
    ical_url = models.TextField(help_text='ical url of the oncall schedule.')
    fallback_officer = models.ForeignKey(
        User,
        blank=True,
        null=True,
        help_text='Fallback officer to alert if the duty officer is unavailable.',
        on_delete=models.SET_NULL
    )

    def get_edit_url(self):
        """Returns the relative URL for modifying this schedule"""
        return reverse('update-schedule', kwargs={'pk': self.pk})

    def has_problems(self):
        return ScheduleProblems.objects.filter(schedule=self).exists()

    def get_calendar_data(self):
        """
        Parse icalendar data
        :return: String containing the calendar data
        """
        resp = requests.get(self.ical_url)
        resp.raise_for_status()
        return Calendar.from_ical(resp.content)

    def __unicode__(self):
        return self.name


class ScheduleProblems(models.Model):
    schedule = models.OneToOneField(
        Schedule,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name='problems',
    )
    silence_warnings_until = models.DateTimeField(
        help_text="Silence configuration warning emails to the fallback officer (e.g. about gaps in the schedule) "
                  "until this time. This will also display a warning in the schedules list.",
        null=True,
    )
    text = models.TextField(
        help_text="Description of the problems with this schedule.",
        blank=False,
        null=False,
    )

    def is_silenced(self, now=None):
        if now is None:
            now = timezone.now()

        return self.silence_warnings_until is not None and self.silence_warnings_until > now


class Service(CheckGroupMixin):

    def update_status(self):
        # Services that have been around for a long time accumulate a huge history of snapshots.
        # When these services are deleted, Django manually deletes these snapshots (through on_delete=models.CASCADE).
        # This is done by enumerating all snapshots with a foreign key pointing to this service, then deleting them
        # one by one.
        # While this snapshot deletion is going on, update_status() may still run concurrently via celery.
        # This causes a new ServiceStatusSnapshot to be created for the service that is being deleted.
        # Once the cascading delete for snapshots completes, Django tries to delete our service's row in the DB,
        # but fails with an IntegrityError:

        #     IntegrityError: update or delete on table "cabotapp_service" violates foreign key constraint
        #     "cabotapp_servicestat_service_id_a9d27aca_fk_cabotapp_" on table "cabotapp_servicestatussnapshot"
        #     DETAIL:  Key (id)=(2194) is still referenced from table "cabotapp_servicestatussnapshot".

        # because Django doesn't see the new ServiceStatusSnapshot.
        # We have a test that demonstrates this behavior in TestWebConcurrency.test_delete_service.

        # So, to work around this behavior, we do two things:
        # 1. Lock the service while we perform a status update.
        # 2. Lock the service while we do the cascading delete and final cleanup delete.

        # note: the exists() is important because:
        # 1. this service may be deleted between celery starting and running this task
        # 2. select_for_update().filter() prepares a queryset, but doesn't actually hit the DB;
        #    the lock is taken only when the queryset is evaluated. exists() is one way to evaluate the queryset.
        with transaction.atomic():
            if not Service.objects.select_for_update().filter(pk=self.pk).exists():
                return

            self.old_overall_status = self.overall_status
            # Only active checks feed into our calculation
            status_checks_failed_count = self.all_failing_checks().count()
            self.overall_status = self.most_severe(self.all_failing_checks())
            self.snapshot = ServiceStatusSnapshot(
                service=self,
                num_checks_active=self.active_status_checks().count(),
                num_checks_passing=self.active_status_checks().count() - status_checks_failed_count,
                num_checks_failing=status_checks_failed_count,
                overall_status=self.overall_status,
                time=timezone.now(),
            )
            self.snapshot.save()
            self.save()

        if not (self.overall_status == Service.PASSING_STATUS and self.old_overall_status == Service.PASSING_STATUS):
            self.alert()

    url = models.TextField(
        blank=True,
        help_text="URL of service."
    )

    def delete(self, *args, **kwargs):
        # to handle django's cascading deletes for large services; see update_status()
        with transaction.atomic():
            Service.objects.select_for_update().filter(pk=self.pk).exists()
            result = super(Service, self).delete(*args, **kwargs)
        return result

    class Meta:
        ordering = ['name']


class Snapshot(models.Model):

    class Meta:
        abstract = True

    time = models.DateTimeField(db_index=True)
    num_checks_active = models.IntegerField(default=0)
    num_checks_passing = models.IntegerField(default=0)
    num_checks_failing = models.IntegerField(default=0)
    overall_status = models.TextField(default=Service.PASSING_STATUS)
    did_send_alert = models.IntegerField(default=False)


class ServiceStatusSnapshot(Snapshot):
    service = models.ForeignKey(Service, related_name='snapshots', on_delete=models.CASCADE)

    def __unicode__(self):
        return u"%s: %s" % (self.service.name, self.overall_status)


class StatusCheck(PolymorphicModel):
    """
    Base class for polymorphic models. We're going to use
    proxy models for inheriting because it makes life much simpler,
    but this allows us to stick different methods etc on subclasses.

    You can work out what (sub)class a model is an instance of by accessing `instance.polymorphic_ctype.model`

    We are using django-polymorphic for polymorphism
    """

    # Common attributes to all
    name = models.TextField()
    active = models.BooleanField(
        default=True,
        help_text='If not active, check will not be used to calculate service status and will not trigger alerts.',
    )
    use_activity_counter = models.BooleanField(
        default=False,
        help_text='When enabled, a check\'s \'activity counter\' is used to tell if '
                  'the check can run. The activity counter starts at zero and may be '
                  'incremented or decremented via API call. When incremented above '
                  'zero, the check may run. When decremented to zero, the check will '
                  'not run. This allows external processes to enable or disable a check '
                  'as needed. (Note: the check must also be marked \'Active\' to run.)',
    )
    importance = models.CharField(
        max_length=30,
        choices=Service.IMPORTANCES,
        default=Service.ERROR_STATUS,
        help_text='Severity level of a failure. Critical alerts are for failures you want to wake you up at 2am, '
                  'Errors are things you can sleep through but need to fix in the morning, '
                  'and warnings for less important things.'
    )
    frequency = models.PositiveIntegerField(
        default=defs.DEFAULT_CHECK_FREQUENCY,
        help_text='Minutes between each check.',
    )
    retries = models.PositiveIntegerField(
        default=defs.DEFAULT_CHECK_RETRIES,
        null=True,
        help_text='Number of successive failures permitted before check will be marked as failed. '
                  'Default is 0, i.e. fail on first failure.'
    )
    run_delay = models.PositiveIntegerField(
        default=0,
        validators=[MaxValueValidator(60)],
        help_text='Minutes to delay running the check, between 0-60. Only for checks using activity counters. '
                  'A run delay can alleviate race conditions between an activity-counted check first running, '
                  'and metrics being available.'
    )
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    calculated_status = models.CharField(
        max_length=50, choices=Service.STATUSES, default=Service.CALCULATED_PASSING_STATUS, blank=True)
    last_run = models.DateTimeField(null=True)
    cached_health = models.TextField(editable=False, null=True)
    runbook = models.TextField(
        default=None,
        null=True,
        blank=True,
        help_text='Notes for on-calls to correctly diagnose and resolve the alert. Supports HTML!',
    )

    class Meta(PolymorphicModel.Meta):
        ordering = ['name']

    def __unicode__(self):
        return self.name

    def recent_results(self):
        # Not great to use id but we are getting lockups, possibly because of something to do with index
        # on time_complete
        return StatusCheckResult.objects.filter(status_check=self).order_by('-id').defer('raw_data')[:10]

    def last_result(self):
        try:
            return StatusCheckResult.objects.filter(status_check=self).order_by('-id').defer('raw_data')[0]
        except:
            return None

    def should_run(self):
        '''Returns true if the check should run, false otherwise.'''

        # Handle special cases for activity-counted checks, which may have run delays
        if self.use_activity_counter:
            # Get the check's counter. If it doesn't exist, the check should not run.
            try:
                counter = ActivityCounter.objects.get(status_check=self)
            except ActivityCounter.DoesNotExist:
                return False

            # If last_enabled is None, then either:
            # - If count == 0, the check should not run, as there is no record of the counter being incremented.
            # - If count > 0, set last_enabled to now to ensure it is not None. This should only happen once,
            #   when this code is first deployed.
            if counter.last_enabled is None:
                if counter.count == 0:
                    return False
                else:
                    # NB: since we are updating last_enabled outside of a transaction, there's a possibility
                    # that we clobber existing data. However, we should almost never enter this if-block, and
                    # worst case we clobber a recent value with a nearly identical value.
                    counter.last_enabled = timezone.now()
                    counter.save(update_fields=["last_enabled"])
                    logger.warning("activity_counter id={} last_enabled is None, setting to now".format(counter.id))

            # For activity-counted checks, we need to determine if the current time is within the
            # window during which the check may run:
            #
            #      (last_enabled+run_delay) <= current_time <= (last_disabled+run_delay)
            #
            # Note that we don't need to check the counter value; it is used by ActivityCounter instance
            # methods to determine when to update last_enabled and last_disabled.
            mins_delay = timedelta(minutes=self.run_delay)
            window_start = counter.last_enabled + mins_delay
            window_end = (counter.last_disabled + mins_delay) if counter.last_disabled else None

            # Check if the current time falls within the time window.
            now = timezone.now()

            # Window is in the future
            if now < window_start:
                return False

            # Window is in the past
            if window_end and window_end > window_start and now > window_end:
                return False

            # The last thing to verify is that the check hasn't run within the frequency

        # Run if we haven't run at all
        if not self.last_run:
            return True

        # Otherwise, determine if the check should run based on its frequency
        next_run_time = self.last_run + timedelta(minutes=self.frequency)
        return timezone.now() > next_run_time

    @transaction.atomic()
    def run(self):
        start = timezone.now()
        try:
            result, tags = self._run()
        except SoftTimeLimitExceeded:
            result = StatusCheckResult(status_check=self, succeeded=False,
                                       error=u'Error in performing check: Celery soft time limit exceeded')
            tags = ['celery_timeout']
        except Exception as e:
            result = StatusCheckResult(status_check=self, succeeded=False,
                                       error=u'Error in performing check: %s' % (e,))
            tags = ['run_error']

        finish = timezone.now()
        result.time = start
        result.time_complete = finish
        result.save()

        # would like to do this in bulk, but django can't fetch the tag object PKs from bulk_create()...
        try:
            tag_objs = [StatusCheckResultTag.objects.get_or_create(value=t)[0] for t in tags if t]
            result.tags.add(*tag_objs)
        except:  # noqa
            # can fail if a tag's name is too long
            logger.exception("Error creating/adding tags: %s", tags)

        if result.succeeded:
            Acknowledgement.close_succeeding_acks(check=self, at_time=finish)
        else:
            acks = Acknowledgement.get_acks_matching_result(result, at_time=finish)
            if len(acks) > 0:
                result.acked = True
                result.save(update_fields=('acked',))

        self.last_run = finish
        self.save()

    def _run(self):
        # type: () -> Tuple[StatusCheckResult, List[str]]
        """
        Implement on subclasses. Should return a `StatusCheckResult` instance and a list of tags.
        """
        raise NotImplementedError('Subclasses should implement')

    def clean(self, *args, **kwargs):
        '''
        Validate the StatusCheck:
        - Ensure all StatusChecks that use activity counters have unique names,
          so that we can identify a check by name via the activity-counter api.
        '''
        if self.use_activity_counter:
            others = StatusCheck.objects.filter(use_activity_counter=True)
            for other in others:
                if other.id != self.id and other.name == self.name:
                    msg = "Names of checks that use activity counters must be " \
                          "unique! This one matches check #{}.".format(other.id)
                    raise ValidationError(msg)

    def save(self, *args, **kwargs):
        if self.last_run:
            recent_results = list(self.recent_results())
            if get_success_with_retries(recent_results, self.retries):
                self.calculated_status = Service.CALCULATED_PASSING_STATUS
            else:
                last_result = recent_results[0] if recent_results and len(recent_results) > 0 else None
                if last_result and last_result.acked:
                    # last result is acked, so we are too
                    self.calculated_status = Service.CALCULATED_ACKED_STATUS
                else:
                    # get_success_with_retries returned False, so we're failing
                    self.calculated_status = Service.CALCULATED_FAILING_STATUS
            self.cached_health = serialize_recent_results(recent_results)
            try:
                StatusCheck.objects.get(pk=self.pk)
            except StatusCheck.DoesNotExist:
                logger.error('Cannot find myself (check %s) in the database, presumably have been deleted' % self.pk)
                return
        else:
            self.cached_health = ''
            self.calculated_status = Service.CALCULATED_PASSING_STATUS
        ret = super(StatusCheck, self).save(*args, **kwargs)
        return ret

    def duplicate(self, inst_set=(), serv_set=()):
        new_check = self
        new_check.pk = None
        new_check.id = None
        new_check.name = 'Copy of {}'.format(self.name)
        new_check.last_run = None
        new_check.save()
        for linked in list(inst_set) + list(serv_set):
            linked.status_checks.add(new_check)
        return new_check.pk

    def get_status_image(self):
        """Return a related image for the check (if it exists)"""
        return None

    def get_status_link(self):
        """Return a link with more information about the check"""
        return None


class ActivityCounter(models.Model):
    '''
    Model containing the current activity-counter value for a check with
    use_activity_counter set to True.

    IMPORTANT: modifying the counter should only be done inside of a transaction.
    Use `ActivityCounter.objects.select_for_update().get(...)` to avoid concurrency issues.
    '''
    status_check = models.OneToOneField(
        StatusCheck,
        on_delete=models.CASCADE,
        related_name='activity_counter',
    )
    count = models.PositiveIntegerField(default=0)
    last_enabled = models.DateTimeField(null=True)
    last_disabled = models.DateTimeField(null=True)

    def increment_and_save(self):
        '''
        Increment the counter, update last_enabled if the count is going from 0 to 1,
        and save the model.
        '''
        if self.count == 0:
            self.last_enabled = timezone.now()
        self.count += 1
        self.save()

    def decrement_and_save(self):
        '''
        Decrement the counter to a minimum of zero. Update last_disabled if going from
        1 to 0. Save the model if it changed.
        '''
        if self.count == 1:
            self.last_disabled = timezone.now()
        if self.count > 0:
            self.count -= 1
            self.save()

    def reset_and_save(self):
        '''
        If the counter is positive, set it to zero, update last_disabled, and save.
        '''
        if self.count > 0:
            self.last_disabled = timezone.now()
            self.count = 0
            self.save()


class HttpStatusCheck(StatusCheck):

    @property
    def check_category(self):
        return "HTTP check"

    @property
    def description(self):
        desc = ['Status code {} from {}'.format(self.status_code, self.endpoint)]
        if self.text_match:
            desc.append('; match text /{}/'.format(self.text_match))
        return ''.join(desc)

    update_url = 'update-http-check'

    icon = 'glyphicon glyphicon-arrow-up'

    endpoint = models.TextField(
        null=True,
        help_text='HTTP(S) endpoint to poll.',
    )
    username = models.TextField(
        blank=True,
        null=True,
        help_text='Basic auth username.',
    )
    password = models.TextField(
        blank=True,
        null=True,
        help_text='Basic auth password.',
    )
    http_method = models.CharField(
        null=False,
        max_length=10,
        default='GET',
        choices=(('GET', 'GET'), ('POST', 'POST'), ('HEAD', 'HEAD')),
        help_text='The method to use for invocation',
    )
    http_params = models.TextField(
        default=None,
        null=True,
        blank=True,
        help_text='Yaml representation of "header: regex" to send as parameters',
    )
    http_body = models.TextField(
        null=True,
        default=None,
        blank=True,
        help_text='Yaml representation of key: value to send as data'
    )
    allow_http_redirects = models.BooleanField(
        default=True,
        help_text='Indicates if the check should follow an http redirect'
    )
    text_match = models.TextField(
        blank=True,
        null=True,
        help_text='Regex to match against source of page.',
    )
    header_match = models.TextField(
        default=None,
        null=True,
        blank=True,
        help_text='Yaml representation of "header: regex" to match in '
                  'the results',
    )
    timeout = PositiveIntegerMaxField(
        default=defs.DEFAULT_HTTP_TIMEOUT,
        max_value=defs.MAX_HTTP_TIMEOUT,
        null=True,
        help_text='Time out after this many seconds.',
     )
    verify_ssl_certificate = models.BooleanField(
        default=True,
        help_text='Set to false to allow not try to verify ssl certificates (default True)',
    )
    status_code = models.TextField(
        default=defs.DEFAULT_HTTP_STATUS_CODE,
        null=True,
        help_text='Status code expected from endpoint.'
    )

    @staticmethod
    def tag_status(status):
        # type: (int) -> str
        return "status:{}".format(status)

    @staticmethod
    def tag_exception(exception):
        # use exception type as tag name (e.g. ConnectionError)
        return type(exception).__name__

    tag_text_match_failed = "text_match_failed"
    tag_missing_header = "missing_header"
    tag_unexpected_header = "unexpected_header"

    def _run(self):
        result = StatusCheckResult(status_check=self)
        if self.username:
            auth = (self.username, self.password)
        else:
            auth = None

        try:
            http_params = yaml.load(self.http_params)
        except:
            http_params = self.http_params

        try:
            http_body = yaml.load(self.http_body)
        except:
            http_body = self.http_body

        try:
            header_match = yaml.load(self.header_match)
        except:
            header_match = self.header_match

        try:
            resp = requests.request(
                method=self.http_method,
                url=self.endpoint,
                data=http_body,
                params=http_params,
                timeout=self.timeout,
                verify=self.verify_ssl_certificate,
                auth=auth,
                allow_redirects=self.allow_http_redirects
            )
        except requests.RequestException as e:
            result.error = u'Request error occurred: %s' % (e.message,)
            result.succeeded = False
            return result, [self.tag_exception(e)]
        else:
            result.raw_data = resp.content
            result.succeeded = False

            if self.status_code and resp.status_code != int(self.status_code):
                result.error = u'Wrong code: got %s (expected %s)' % (
                    resp.status_code, int(self.status_code))
                return result, [self.tag_status(resp.status_code)]

            if self.text_match is not None:
                if not re.search(self.text_match, resp.content):
                    result.error = u'Failed to find match regex /%s/ in response body' % self.text_match
                    return result, [self.tag_text_match_failed]

            if type(header_match) is dict and header_match:
                for header, match in header_match.iteritems():
                    if header not in resp.headers:
                        result.error = u'Missing response header: %s' % (header)
                        return result, [self.tag_missing_header]

                    value = resp.headers[header]
                    if not re.match(match, value):
                        result.error = u'Mismatch in header: %s / %s' % (header, value)
                        return result, [self.tag_unexpected_header]

            # Mark it as success. phew!!
            result.succeeded = True

        return result, []


class JenkinsStatusCheck(StatusCheck):

    @property
    def check_category(self):
        return "Jenkins check"

    @property
    def description(self):
        desc = ['Monitor job {}'.format(self.name)]
        if self.max_queued_build_time is not None:
            desc.append('; no build waiting for > {} minutes'.format(self.max_queued_build_time))
        return ''.join(desc)

    update_url = 'update-jenkins-check'

    icon = 'glyphicon glyphicon-ok'

    max_queued_build_time = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Alert if build queued for more than this many minutes.',
    )

    max_build_failures = models.PositiveIntegerField(
        default=0,
        help_text='Alert if more than this many consecutive failures (default=0)'
    )

    @property
    def failing_short_status(self):
        return 'Job failing on Jenkins'

    tag_job_not_found = "job_not_found"
    tag_bad_response = "bad_response"
    tag_job_disabled = "job_disabled"
    tag_max_queued_build_time_exceeded = "max_queued_build_time_exceeded"
    tag_max_consecutive_failures_exceeded = "max_consecutive_failures_exceeded"
    tag_build_missing = "build_missing"

    def _run(self):
        result = StatusCheckResult(status_check=self)
        try:
            status = get_job_status(self.name)
            active = status['active']
            result.job_number = status['job_number']
            if status['status_code'] == 404:
                result.error = u'Job %s not found on Jenkins' % self.name
                result.succeeded = False
                return result, [self.tag_job_not_found]
            elif status['status_code'] >= 400:
                # Will fall through to next block
                raise Exception(u'returned %s' % status['status_code'])
        except Exception as e:
            # If something else goes wrong, we will *not* fail - otherwise
            # a lot of services seem to fail all at once.
            # Ugly to do it here but...
            result.error = u'Error fetching from Jenkins - %s' % e.message
            result.succeeded = False
            return result, [self.tag_bad_response]

        tags = []
        if not active:
            # We will fail if the job has been disabled
            result.error = u'Job "%s" disabled on Jenkins' % self.name
            result.succeeded = False
            tags.append(self.tag_job_disabled)
        else:
            result.succeeded = True

            if self.max_queued_build_time and status['blocked_build_time']:
                if status['blocked_build_time'] > self.max_queued_build_time * 60:
                    result.succeeded = False
                    result.error = u'Job "%s" has blocked build waiting for %ss (> %sm)' % (
                        self.name,
                        int(status['blocked_build_time']),
                        self.max_queued_build_time,
                    )
                    tags.append(self.tag_max_queued_build_time_exceeded)

            if result.succeeded and status['consecutive_failures'] is not None:
                if status['consecutive_failures'] > self.max_build_failures:
                    result.succeeded = False
                    result.error = u'Job "%s" has failed %s times (> %s)' % (
                        self.name,
                        int(status['consecutive_failures']),
                        self.max_build_failures,
                    )
                    tags.append(self.tag_max_consecutive_failures_exceeded)
                elif status['consecutive_failures'] < 0:
                    result.succeeded = False
                    result.error = u'Job "%s" Last Completed Build not Found' % (
                        self.name
                    )
                    tags.append(self.tag_build_missing)

            if not result.succeeded:
                result.raw_data = status

        return result, tags


class TCPStatusCheck(StatusCheck):

    @property
    def check_category(self):
        return "TCP check"

    @property
    def description(self):
        return 'Monitoring connection of {0}:{1}'.format(self.address, self.port)

    address = models.CharField(
        max_length=1024,
        help_text='IP address or hostname to monitor',)
    port = models.PositiveIntegerField(
        help_text='Port to connect to',)
    timeout = PositiveIntegerMaxField(
        default=defs.DEFAULT_TCP_TIMEOUT,
        max_value=defs.MAX_TCP_TIMEOUT,
        help_text='Time out on idle connection after this many seconds',)

    update_url = 'update-tcp-check'

    icon = 'glyphicon glyphicon-text-wide'

    @staticmethod
    def tag_exception(exception):
        # type: (socket.error) -> str
        # tag with human name of the socket's posix errno
        # special logic for socket.timeout, since it doesn't set errno :shakes_fist:
        error_no = errno.ETIMEDOUT if type(exception) == socket.timeout else abs(exception.errno)
        return "{}".format(errno.errorcode.get(error_no, error_no))

    def _run(self):
        """
        We wish to provide a method to ensure a TCP endpoint is still up. To
        achieve this, we use the python socket library to connect to the TCP
        service listening on the specified address and port. In other words,
        if this call succeeds (i.e. returns without raising an exception and/or
        timing out), we can conclude that the TCP endpoint is valid.
        """
        result = StatusCheckResult(status_check=self)
        tags = []

        try:
            socket.create_connection((self.address, self.port), self.timeout)
            result.succeeded = True
        except socket.error as e:
            result.error = str(e)
            result.succeeded = False
            tags.append(self.tag_exception(e))

        return result, tags


class StatusCheckResultTag(models.Model):
    value = models.CharField(max_length=255, blank=False, primary_key=True)

    def __unicode__(self):
        return self.value


class StatusCheckResult(models.Model):
    """
    We use the same StatusCheckResult model for all check types,
    because really they are not so very different.

    Checks don't have to use all the fields, so most should be
    nullable
    """
    status_check = models.ForeignKey(StatusCheck, on_delete=models.CASCADE)
    time = models.DateTimeField(null=False, db_index=True)
    time_complete = models.DateTimeField(null=True, db_index=True)
    raw_data = models.TextField(null=True)
    succeeded = models.BooleanField(default=False)
    error = models.TextField(null=True)

    tags = models.ManyToManyField(StatusCheckResultTag)
    acked = models.BooleanField(null=False, default=False)

    # Jenkins specific
    job_number = models.PositiveIntegerField(null=True)

    def __unicode__(self):
        return '%s: %s @%s' % (self.status, self.status_check.name, self.time)

    @property
    def status(self):
        if self.succeeded:
            return 'succeeded'
        else:
            return 'failed'

    @property
    def took(self):
        try:
            return (self.time_complete - self.time).microseconds / 1000
        except:
            return None

    @property
    def short_error(self):
        snippet_len = 30
        if len(self.error) > snippet_len:
            return u"%s..." % self.error[:snippet_len - 3]
        else:
            return self.error

    def save(self, *args, **kwargs):
        if isinstance(self.raw_data, basestring):
            self.raw_data = self.raw_data[:defs.RAW_DATA_LIMIT]
        return super(StatusCheckResult, self).save(*args, **kwargs)


class UserProfile(models.Model):
    user = models.OneToOneField(User, related_name='profile', on_delete=models.CASCADE)

    def user_data(self):
        for user_data_subclass in AlertPluginUserData.__subclasses__():
            user_data_subclass.objects.get_or_create(user=self, title=user_data_subclass.name)
        return AlertPluginUserData.objects.filter(user=self)

    def __unicode__(self):
        return 'User profile: %s' % self.user.username

    @property
    def prefixed_mobile_number(self):
        return '+%s' % self.mobile_number

    mobile_number = models.CharField(max_length=20, blank=True, default='')
    hipchat_alias = models.CharField(max_length=50, blank=True, default='')

    timezone = TimeZoneField(default='UTC')


def get_events(schedule):
    """
    Get the events from an ical.
    :param schedule: The oncall schedule we want events for
    :return: A list of dicts of event data
    """
    events = []
    for component in schedule.get_calendar_data().walk():
        if component.name == 'VEVENT':
            events.append({
                'start': component.decoded('dtstart'),
                'end': component.decoded('dtend'),
                'summary': component.decoded('summary'),
                'uid': component.decoded('uid'),
                'attendee': component.decoded('attendee'),
            })
    return events


class Shift(models.Model):
    start = models.DateTimeField()
    end = models.DateTimeField()
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    uid = models.TextField()
    deleted = models.BooleanField(default=False)
    schedule = models.ForeignKey('Schedule', default=1, on_delete=models.CASCADE)

    def __unicode__(self):
        deleted = ''
        if self.deleted:
            deleted = ' (deleted)'
        return "%s: %s to %s%s" % (self.user.username, self.start, self.end, deleted)


class ResultFilter(models.Model):
    """Filter that matches StatusCheckResults."""
    class Meta:
        abstract = True

    status_check = models.ForeignKey(StatusCheck, null=False)

    MATCH_CHECK = 'C'
    MATCH_TYPE_CHOICES = (
        (MATCH_CHECK, 'Match check.'),
    )
    match_if = models.TextField(max_length=1, null=False, blank=False, default=MATCH_CHECK, choices=MATCH_TYPE_CHOICES)

    def matches_result(self, result):
        # type: (StatusCheckResult) -> bool

        # status_check must match, regardless of match type
        if result.status_check_id != self.status_check_id:
            return False

        if self.match_if == self.MATCH_CHECK:
            return True

        raise NotImplementedError()


class Acknowledgement(ResultFilter):
    """
    A filter that matches on a StatusCheck (or subset of a StatusCheck, if matching on tags).
    An Acknowledgement is considered 'open' if closed_at is set to null.

    Acknowledgements "expire" (auto-close) if the expire_at parameter is set. Expiration is performed in two ways:
      1) get_acks_matching_check() will not return checks where expire_at <= now.
      2) A periodic celery task calls ack.close() on checks where expire_at <= now.

    Acknowledgements are also automatically closed when their StatusCheck succeeds at least close_after_successes
    times (consecutively). This is done by Acknowledgement.close_succeeding_acks(), which is called by StatusCheck.run()
    whenever a check succeeds.

    For simplicity, only one Acknowledgement can exist per StatusCheck. This is enforced by automatically closing
    Acknowledgements that already exist for the same status check in Acknowledgement.save() (with a fixed reason).
    """
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_by = models.ForeignKey(User, null=True, default=None)
    note = models.TextField(max_length=255, blank=True,
                            help_text='Leave a note explaining why this ack was created.')

    # if 'closed_at' is set, the ack is considered 'closed'
    closed_at = models.DateTimeField(null=True, default=None, db_index=True)
    closed_reason = models.TextField(max_length=255, null=True, blank=False, default=None)

    expire_at = models.DateTimeField(null=True, default=None, db_index=True,
                                     help_text='After this time the acknowledgement will be automatically closed and '
                                               'alerts will resume, even if the check is still failing.')
    close_after_successes = models.PositiveIntegerField(null=True, default=1,
                                                        help_text='After this many consecutive successful runs the '
                                                                  'acknowledgement will be automatically closed. Enter '
                                                                  '0 to disable.')

    @classmethod
    def get_acks_matching_check(cls, check, at_time=None):
        # type: (StatusCheck, timezone.datetime) -> List[Acknowledgement]
        """
        :param check: check to gather acks for
        :param at_time: only consider acks that were open at this time; leave as None to use timezone.now().
        :returns list of Acknowledgements where ack.
        """
        at_time = at_time or timezone.now()
        acks = cls.objects.filter(status_check_id=check.id)
        return acks.exclude(created_at__gt=at_time).exclude(closed_at__lte=at_time).exclude(expire_at__lte=at_time)

    @classmethod
    def get_acks_matching_result(cls, result, at_time=None):
        # type: (StatusCheckResult, Union[timezone.datetime, None]) -> List[Acknowledgement]
        """
        :param result: result to gather acks for
        :param at_time: only consider acks that were open at this time; leave None for all currently open acks
        :returns list of Acknowledgements where ack.matches_result(result) == True
        """
        return [a for a in cls.get_acks_matching_check(result.status_check, at_time) if a.matches_result(result)]

    @classmethod
    def close_succeeding_acks(cls, check, at_time=None):
        # type: (StatusCheck, Union[timezone.datetime, None]) -> None
        """
        This function closes acks that have hit their close_after_successes threshold.
        This should be called after a StatusCheck saves a new StatusCheckResult (including its tags!).
        It technically only needs to be called after a check succeeds, but it's idempotent - you can call it whenever.
        :param check: StatusCheck to update acks for.
        :param at_time: Time to pass into get_acks_matching_check. Leave as None to use timezone.now().
        """
        for ack in cls.get_acks_matching_check(check, at_time=at_time):
            if ack.close_after_successes:
                # get last n results for our check, regardless of status
                results = StatusCheckResult.objects.filter(status_check=ack.status_check)\
                              .order_by('-time_complete', '-id').only('succeeded')[:ack.close_after_successes]

                # now filter down to the results that succeeded
                results = [r for r in results if r.succeeded]

                # if we hit our threshold, this check should expire
                if len(results) >= ack.close_after_successes:
                    reason = 'check passed {} times'.format(len(results)) if len(results) != 1 else 'check passed'
                    ack.close(reason)

    def save(self, **kwargs):
        # THERE CAN BE ONLY ONE. for log trails.
        existing = Acknowledgement.objects\
            .filter(status_check=self.status_check, closed_at__isnull=True)\
            .exclude(pk=self.pk)
        for old_ack in existing:
            old_ack.close('options changed')

        return super(Acknowledgement, self).save(**kwargs)

    def close(self, reason):
        # type: (str) -> None
        """Set closed_at and closed_reason and update the DB."""
        self.closed_at = timezone.now()
        self.closed_reason = reason
        self.save(update_fields=('closed_at', 'closed_reason'))

    def clone(self, created_by):
        # type: (Union[User, None]) -> Acknowledgement
        """
        Returns a new Acknowledgement with the same parameters as this one. The new ack is saved to the database
        during creation (necessary because of the many-to-many relationship for tags).

        Expiration dates are re-calculated relative to now, maintaining the same duration.

        :param created_by django User that created the check (may be None, but may not be AnonymousUser).
        :returns new Acknowledgement
        """
        ack = Acknowledgement(status_check=self.status_check, match_if=self.match_if, created_by=created_by,
                              expire_at=timezone.now() + (self.expire_at - self.created_at) if self.expire_at else None,
                              close_after_successes=self.close_after_successes)
        ack.save()
        return ack


def get_duty_officers(schedule, at_time=None):
    """
    Return the users on duty for a given schedule and time
    :param schedule: The oncall schedule we're looking at
    :param at_time: The time we want to know about
    :return: List of users who are oncall
    """
    if not at_time:
        at_time = timezone.now()
    current_shifts = Shift.objects.filter(
        deleted=False,
        start__lt=at_time,
        end__gt=at_time,
        schedule=schedule,
    )
    if current_shifts:
        duty_officers = [shift.user for shift in current_shifts]
        return duty_officers
    else:
        if schedule.fallback_officer:
            return [schedule.fallback_officer]
        return []


def get_single_duty_officer(schedule, at_time=None):
    """
    Return one duty officer who is oncall
    :param schedule: The oncall schedule
    :param at_time: The time we want to know about
    :return: One oncall officer or nothing
    """
    officers = get_duty_officers(schedule, at_time)
    if len(officers) > 0:
        return officers[0]
    return ''


def get_all_duty_officers(at_time=None):
    """
    Find all oncall officers and the schedules they're oncall for
    :param at_time: The time we want to know about
    :return: dict of {oncall_officer: schedule}
    """
    out = defaultdict(list)

    for schedule in Schedule.objects.all():
        for user in get_duty_officers(schedule, at_time):
            out[user].append(schedule)

    return out


def get_all_fallback_officers():
    """
    Find all fallback officers and the schedules they're oncall for
    :param at_time:  The time we want to know about
    :return: dict of {fallback_officer: schedule}
    """
    out = defaultdict(list)

    for schedule in Schedule.objects.all():
        out[schedule.fallback_officer].append(schedule)

    return out


def get_fallback_officers(schedule):
    """
    Find the fallback officer
    :return: list of the fallback officer (for parity with get_duty_officers())
    """
    if schedule.fallback_officer:
        return [schedule.fallback_officer]
    return []


def update_shifts(schedule):
    """
    Update oncall Shifts for a given schedule
    :param schedule: The oncall schedule
    :return: none
    """
    events = get_events(schedule)
    users = User.objects.filter(is_active=True)
    user_lookup = {}
    email_lookup = {}
    for u in users:
        user_lookup[u.username.lower()] = u
        email_lookup[u.email.lower()] = u

    with transaction.atomic():
        # Set all shifts to deleted, ones that are still active will set deleted to False
        shifts = Shift.objects.filter(schedule=schedule)
        shifts.update(deleted=True)

        for event in events:
            summary = event['summary'].lower().strip()
            attendee = event['attendee'].lower().strip()

            if summary in user_lookup or summary in email_lookup:
                e = summary
            elif attendee in user_lookup or attendee in email_lookup:
                e = attendee
            else:
                e = None

            if e is not None:
                user = user_lookup.get(e)
                if user is None:
                    user = email_lookup.get(e)

                if user is None:
                    logger.exception('Could not find user % for schedule %'.format(e, schedule.name))
                    return

                s = Shift.objects.filter(uid=event['uid'], schedule=schedule).first()
                if s is None:
                    s = Shift(uid=event['uid'], schedule=schedule)

                s.start = event['start']
                s.end = event['end']
                s.user = user
                s.deleted = False
                s.schedule = schedule
                s.updated = True
                s.save()

import time
import six
from django.template import loader
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse_lazy
from django.conf import settings
from timezone_field import TimeZoneFormField

from cabot.cabotapp.alert import AlertPlugin
from cabot.cabotapp.fields import TimeFromNowField
from models import (StatusCheck,
                    JenkinsStatusCheck,
                    HttpStatusCheck,
                    TCPStatusCheck,
                    StatusCheckResult,
                    ActivityCounter,
                    UserProfile,
                    Service,
                    Shift,
                    Schedule,
                    get_all_duty_officers,
                    get_single_duty_officer,
                    get_all_fallback_officers,
                    update_shifts, ScheduleProblems, Acknowledgement)

from tasks import run_status_check as _run_status_check, update_check_and_services
from .decorators import cabot_login_required
from django.utils.decorators import method_decorator
from django.views.generic import (DetailView,
                                  CreateView,
                                  UpdateView,
                                  ListView,
                                  DeleteView,
                                  TemplateView,
                                  View)
from django import forms
from django.contrib.auth.models import User, AnonymousUser
from django.utils import timezone
from django.utils.timezone import utc
from django.core.urlresolvers import reverse
from django.core.exceptions import ValidationError
from django.db import transaction

from cabot.cabotapp.utils import format_datetime
from defs import EXPIRE_AFTER_HOURS_OPTIONS, NUM_VISIBLE_CLOSED_ACKS, ACK_SERVICE_NOT_YET_UPDATED_MSG, \
    ACK_UPDATE_SERVICE_TIMEOUT_SECONDS
from models import AlertPluginUserData
from django.contrib import messages
from social_core.exceptions import AuthFailed
from social_django.views import complete

from itertools import groupby, dropwhile, izip_longest
import requests
import json
import re
from icalendar import Calendar
from django.template.defaulttags import register

from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)


class LoginRequiredMixin(object):

    @method_decorator(cabot_login_required)
    def dispatch(self, *args, **kwargs):
        return super(LoginRequiredMixin, self).dispatch(*args, **kwargs)


class GroupedModelFormMetaMetaclass(type):
    """
    Metaclass for django's "Meta" class that sets "fields" to all the fields in Meta.grouped_fields (in the right order)
    """
    def __new__(mcs, name, bases, attrs):
        if 'grouped_fields' in attrs:
            if 'fields' in attrs:
                raise Exception('GroupedModelForm: specify either "fields" or "grouped_fields", not both.')

            fields = []
            for group_name, field_names in attrs['grouped_fields']:
                fields += field_names
            attrs['fields'] = fields
        return super(GroupedModelFormMetaMetaclass, mcs).__new__(mcs, name, bases, attrs)


class GroupedModelForm(forms.ModelForm):
    """
    Automatically fills in Meta.fields and sets field.group_name based on Meta.grouped_fields.
    For use with the "group by" Django Templates feature.
    Usage:
    1. Have your View subclass GroupedModelForm
    2. Define "class Meta(GroupedModelForm.Meta):" and fill in 'grouped_fields' instead of 'fields', like so:
       grouped_fields = (
         ("group_1", ("field1", "field2")),
         ("group_2", ("field3", "field4", "field5")),
         ...
       )
    """
    class Meta(six.with_metaclass(GroupedModelFormMetaMetaclass)):
        grouped_fields = ()

    def __init__(self, *args, **kwargs):
        super(GroupedModelForm, self).__init__(*args, **kwargs)
        if hasattr(self.Meta, 'grouped_fields'):
            for group_name, field_names in self.Meta.grouped_fields:
                for field_name in field_names:
                    self.fields[field_name].group_name = group_name


@cabot_login_required
def subscriptions(request):
    """ Simple list of all checks """
    t = loader.get_template('cabotapp/subscriptions.html')
    services = Service.objects.all()
    users = User.objects.filter(is_active=True)
    c = {
        'services': services,
        'users': users,
        'duty_officers': get_all_duty_officers(),
        'fallback_officers': get_all_fallback_officers(),
    }
    return HttpResponse(t.render(c, request))


@cabot_login_required
def run_status_check(request, pk):
    """Runs a specific check"""
    _run_status_check(pk=pk)
    return HttpResponseRedirect(reverse('check', kwargs={'pk': pk}))


def duplicate_check(request, pk):
    check = StatusCheck.objects.get(pk=pk)
    new_pk = check.duplicate()
    return HttpResponseRedirect(reverse('check', kwargs={'pk': new_pk}))


class StatusCheckResultDetailView(LoginRequiredMixin, DetailView):
    model = StatusCheckResult
    context_object_name = 'result'


class SymmetricalForm(forms.ModelForm):
    symmetrical_fields = ()  # Iterable of 2-tuples (field, model)

    def __init__(self, *args, **kwargs):
        super(SymmetricalForm, self).__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            for field in self.symmetrical_fields:
                self.fields[field].initial = getattr(
                    self.instance, field).all()

    def save(self, commit=True):
        instance = super(SymmetricalForm, self).save(commit=False)
        if commit:
            instance.save()
        if instance.pk:
            for field in self.symmetrical_fields:
                setattr(instance, field, self.cleaned_data[field])
            self.save_m2m()
        return instance


base_widgets = {
    'name': forms.TextInput(attrs={
        'style': 'width:30%',
    }),
    'importance': forms.RadioSelect(),
}


class StatusCheckForm(SymmetricalForm, GroupedModelForm):
    symmetrical_fields = ('service_set',)

    service_set = forms.ModelMultipleChoiceField(
        queryset=Service.objects.all(),
        required=False,
        help_text='Link to service(s).',
        widget=forms.SelectMultiple(
            attrs={
                'data-rel': 'chosen',
                'style': 'width: 70%',
            },
        )
    )


class HttpStatusCheckForm(StatusCheckForm):
    class Meta(GroupedModelForm.Meta):
        model = HttpStatusCheck
        grouped_fields = (
            ('Basic', ('name', 'active', 'importance', 'service_set')),
            ('Request', ('endpoint', 'frequency', 'retries', 'http_method', 'http_params', 'http_body')),
            ('Response Validation', ('status_code', 'text_match', 'header_match', 'timeout')),
            ('Authentication', ('username', 'password')),
            ('Advanced', ('allow_http_redirects', 'verify_ssl_certificate', 'use_activity_counter', 'run_delay',
                          'run_window', 'runbook')),
        )
        widgets = dict(**base_widgets)
        widgets.update({
            'endpoint': forms.TextInput(attrs={
                'style': 'width: 100%',
                'placeholder': 'https://www.affirm.com',
            }),
            'username': forms.TextInput(attrs={
                'style': 'width: 30%',
            }),
            'password': forms.TextInput(attrs={
                'style': 'width: 30%',
            }),
            'text_match': forms.TextInput(attrs={
                'style': 'width: 100%',
                'placeholder': '[Cc]abot\s+[Rr]ules',
            }),
            'status_code': forms.TextInput(attrs={
                'style': 'width: 20%',
                'placeholder': '200',
            }),
        })


class JenkinsStatusCheckForm(StatusCheckForm):
    class Meta(GroupedModelForm.Meta):
        model = JenkinsStatusCheck
        grouped_fields = (
            ('Basic', ('name', 'active', 'importance', 'service_set')),
            ('Jenkins', ('max_queued_build_time', 'max_build_failures', 'retries', 'frequency')),
            ('Advanced', ('use_activity_counter', 'run_delay', 'run_window', 'runbook')),
        )
        widgets = dict(**base_widgets)


class TCPStatusCheckForm(StatusCheckForm):
    class Meta(GroupedModelForm.Meta):
        model = TCPStatusCheck
        grouped_fields = (
            ('Basic', ('name', 'active', 'importance', 'service_set')),
            ('TCP', ('address', 'port', 'timeout', 'frequency', 'retries')),
            ('Advanced', ('use_activity_counter', 'run_delay', 'run_window', 'runbook')),
        )
        widgets = dict(**base_widgets)
        widgets.update({
            'address': forms.TextInput(attrs={
                'style': 'width:50%',
            })
        })


class ServiceForm(GroupedModelForm):
    class Meta(GroupedModelForm.Meta):
        model = Service
        template_name = 'service_form.html'
        grouped_fields = (
            ('Service', ['name', 'status_checks']),
            ('Alerts', ['alerts_enabled', 'alerts', 'users_to_notify', 'schedules']),
            ('Alert Options', ['hipchat_instance', 'hipchat_room_id', 'mattermost_instance', 'mattermost_channel_id']),
            ('Other', ['url', 'hackpad_id']),
        )
        widgets = {
            'name': forms.TextInput(attrs={'style': 'width: 30%;'}),
            'url': forms.TextInput(attrs={'style': 'width: 70%;'}),
            'status_checks': forms.SelectMultiple(attrs={
                'data-rel': 'chosen',
                'style': 'width: 70%',
            }),
            'alerts': forms.SelectMultiple(attrs={
                'data-rel': 'chosen',
                'style': 'width: 70%',
            }),
            'users_to_notify': forms.SelectMultiple(attrs={
                'data-rel': 'chosen',
                'style': 'width: 70%',
            }),
            'schedules': forms.SelectMultiple(attrs={
                'data-rel': 'chosen',
                'style': 'width: 70%',
            }),
            'hackpad_id': forms.TextInput(attrs={'style': 'width:30%;'}),
        }

    def __init__(self, *args, **kwargs):
        super(ServiceForm, self).__init__(*args, **kwargs)
        self.fields['users_to_notify'].queryset = User.objects.filter(
            is_active=True)
        self.fields['schedules'].queryset = Schedule.objects.all()

    def clean_hackpad_id(self):
        value = self.cleaned_data['hackpad_id']
        if not value:
            return ''
        for pattern in settings.RECOVERY_SNIPPETS_WHITELIST:
            if re.match(pattern, value):
                return value
        raise ValidationError('Please specify a valid JS snippet link')


class ScheduleForm(SymmetricalForm):
    symmetrical_fields = ('service_set',)

    service_set = forms.ModelMultipleChoiceField(
        queryset=Service.objects.all(),
        required=False,
        help_text='Link to service(s).',
        widget=forms.SelectMultiple(
            attrs={
                'data-rel': 'chosen',
                'style': 'width: 70%',
            },
        )
    )

    class Meta:
        model = Schedule
        template_name = 'schedule_form.html'
        fields = (
            'name',
            'ical_url',
            'fallback_officer',
        )
        widgets = {
            'name': forms.TextInput(attrs={'style': 'width: 80%;'}),
            'ical_url': forms.TextInput(attrs={'style': 'width: 80%;'}),
            'fallback_officer': forms.Select(),
        }

    def clean_ical_url(self):
        """
        Make sure the input ical url data can be parsed.
        :return: the ical url if valid, otherwise raise an exception
        """
        try:
            ical_url = self.cleaned_data['ical_url']
            resp = requests.get(ical_url)
            Calendar.from_ical(resp.content)
            return ical_url
        except Exception:
            raise ValidationError('Invalid ical url {}'.format(self.cleaned_data['ical_url']))

    def __init__(self, *args, **kwargs):
        super(ScheduleForm, self).__init__(*args, **kwargs)

        self.fields['fallback_officer'].queryset = User.objects.filter(is_active=True) \
            .order_by('username')


class StatusCheckReportForm(forms.Form):
    service = forms.ModelChoiceField(
        queryset=Service.objects.all(),
        widget=forms.HiddenInput
    )
    checks = forms.ModelMultipleChoiceField(
        queryset=StatusCheck.objects.all(),
        widget=forms.SelectMultiple(
            attrs={
                'data-rel': 'chosen',
                'style': 'width: 70%',
            },
        )
    )
    date_from = forms.DateField(label='From', widget=forms.DateInput(attrs={'class': 'datepicker'}))
    date_to = forms.DateField(label='To', widget=forms.DateInput(attrs={'class': 'datepicker'}))

    def get_report(self):
        checks = self.cleaned_data['checks']
        now = timezone.now()
        for check in checks:
            # Group results of the check by status (failed alternating with succeeded),
            # take time of the first one in each group (starting from a failed group),
            # split them into pairs and form the list of problems.
            results = check.statuscheckresult_set.filter(
                time__gte=self.cleaned_data['date_from'],
                time__lt=self.cleaned_data['date_to'] + timedelta(days=1)
            ).order_by('time')
            groups = dropwhile(lambda item: item[0], groupby(results, key=lambda r: r.succeeded))
            times = [next(group).time for succeeded, group in groups]
            pairs = izip_longest(*([iter(times)] * 2))
            check.problems = [(start, end, (end or now) - start) for start, end in pairs]
            if results:
                check.success_rate = results.filter(succeeded=True).count() / float(len(results)) * 100
        return checks


class CheckCreateView(LoginRequiredMixin, CreateView):
    template_name = 'cabotapp/statuscheck_form.html'

    def form_valid(self, form):
        if self.request.user is not None and not isinstance(self.request.user, AnonymousUser):
            form.instance.created_by = self.request.user
        return super(CheckCreateView, self).form_valid(form)

    def get_initial(self):
        if self.initial:
            initial = self.initial
        else:
            initial = {}
        metric = self.request.GET.get('metric')
        if metric:
            initial['metric'] = metric
        service_id = self.request.GET.get('service')

        if service_id:
            try:
                service = Service.objects.get(id=service_id)
                initial['service_set'] = [service]
            except Service.DoesNotExist:
                pass

        return initial

    def get_success_url(self):
        if self.request.GET.get('service'):
            return reverse('service', kwargs={'pk': self.request.GET.get('service')})
        return reverse('check', kwargs={'pk': self.object.id})


class CheckUpdateView(LoginRequiredMixin, UpdateView):
    template_name = 'cabotapp/statuscheck_form.html'

    def get_success_url(self):
        return reverse('check', kwargs={'pk': self.object.id})


class HttpCheckCreateView(CheckCreateView):
    model = HttpStatusCheck
    form_class = HttpStatusCheckForm


class HttpCheckUpdateView(CheckUpdateView):
    model = HttpStatusCheck
    form_class = HttpStatusCheckForm


class JenkinsCheckCreateView(CheckCreateView):
    model = JenkinsStatusCheck
    form_class = JenkinsStatusCheckForm

    def form_valid(self, form):
        form.instance.frequency = 1
        return super(JenkinsCheckCreateView, self).form_valid(form)


class JenkinsCheckUpdateView(CheckUpdateView):
    model = JenkinsStatusCheck
    form_class = JenkinsStatusCheckForm

    def form_valid(self, form):
        form.instance.frequency = 1
        return super(JenkinsCheckUpdateView, self).form_valid(form)


class TCPCheckCreateView(CheckCreateView):
    model = TCPStatusCheck
    form_class = TCPStatusCheckForm


class TCPCheckUpdateView(CheckUpdateView):
    model = TCPStatusCheck
    form_class = TCPStatusCheckForm


class StatusCheckListView(LoginRequiredMixin, ListView):
    model = StatusCheck
    context_object_name = 'checks'

    def get_queryset(self):
        return StatusCheck.objects.all().order_by('name').prefetch_related('service_set')


class StatusCheckDeleteView(LoginRequiredMixin, DeleteView):
    model = StatusCheck
    success_url = reverse_lazy('checks')
    context_object_name = 'check'
    template_name = 'cabotapp/statuscheck_confirm_delete.html'


class StatusCheckDetailView(LoginRequiredMixin, DetailView):
    model = StatusCheck
    context_object_name = 'check'
    template_name = 'cabotapp/statuscheck_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super(StatusCheckDetailView, self).get_context_data(**kwargs)
        ctx['show_tags'] = self.request.GET.get('show_tags', False)
        ctx['expire_after_hours'] = EXPIRE_AFTER_HOURS_OPTIONS
        return ctx

    def render_to_response(self, context, *args, **kwargs):
        if context is None:
            context = {}
        context['checkresults'] = self.object.statuscheckresult_set.order_by(
            '-time_complete')[:100]
        context['services'] = self.object.service_set.all()

        return super(StatusCheckDetailView, self).render_to_response(context, *args, **kwargs)


class UserProfileUpdateView(LoginRequiredMixin, View):
    model = AlertPluginUserData

    def get(self, *args, **kwargs):
        return HttpResponseRedirect(reverse('update-alert-user-data', args=(self.kwargs['pk'], u'General')))


class GeneralSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'is_active',)
        labels = {
            'email': 'Email address',
            'is_active': 'Enabled'
        }

    def __init__(self, *args, **kwargs):
        super(GeneralSettingsForm, self).__init__(*args, **kwargs)

        self.profile = UserProfile.objects.get_or_create(user=self.instance)[0] if self.instance else None
        tz = self.profile.timezone if self.instance else None
        self.fields['timezone'] = TimeZoneFormField(initial=tz)

    def save(self, *args, **kwargs):
        ret = super(GeneralSettingsForm, self).save(*args, **kwargs)
        if self.profile:  # TODO respect commit kwarg?
            self.profile.timezone = self.cleaned_data['timezone']
            self.profile.save()
        return ret


class UserProfileUpdateAlert(LoginRequiredMixin, UpdateView):
    """
    The "My Profile" page. Allows editing the current User model and any AlertPluginUserDatas.
    The 'alerttype' kwarg is the AlertPluginUserData.title we're editing, 'pk' is the user whose preferences we're
    editing (superuser can edit anyone's settings).
    The 'General' alerttype is a special case for editing the User model (from Django).
    """
    template_name = 'cabotapp/alertpluginuserdata_form.html'

    # return a 403 if not logged in or the user ID doesn't match the logged in user and the user isn't an admin
    # (this runs before get/post)
    def dispatch(self, request, *args, **kwargs):
        if request.user.id != int(kwargs['pk']) and not request.user.is_superuser:
            return HttpResponse(status=403)
        return super(UserProfileUpdateAlert, self).dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        alerttype = self.kwargs['alerttype']

        user = User.objects.get(pk=self.kwargs['pk'])
        if alerttype == u'General':
            return user

        profile = UserProfile.objects.get_or_create(user=user)[0]
        # note: profile.user_data() has a side-effect of creating AlertPluginUserData for user if it doesn't exist
        return profile.user_data().get(title=alerttype)

    def get_form_class(self):
        if type(self.object) is User:
            return GeneralSettingsForm

        # else object is an AlertPluginUserData subclass
        # create form class
        class AlertPreferencesForm(forms.ModelForm):
            class Meta:
                model = type(self.object)
                exclude = []

        return AlertPreferencesForm

    def get_context_data(self, **kwargs):
        ctx = super(UserProfileUpdateAlert, self).get_context_data(**kwargs)
        user = User.objects.get(pk=self.kwargs['pk'])
        profile = UserProfile.objects.get_or_create(user=user)[0]
        ctx['alert_preferences'] = profile.user_data().order_by('title')

        # so send-test-alert's redirect knows which settings page to return to
        ctx['alerttype'] = self.kwargs['alerttype']

        # set associated_alerts to the list of AlertPlugin objects related to the AlertPluginUserData we are editing
        try:
            alert_userdata = profile.user_data().get(title=self.kwargs['alerttype'])
            alert_names = [a.name for a in alert_userdata.alert_classes if hasattr(a, 'name')]
            alerts = AlertPlugin.objects.filter(title__in=alert_names)
            ctx['associated_alerts'] = alerts
        except AlertPluginUserData.DoesNotExist:
            # special case for the General page...
            ctx['associated_alerts'] = AlertPlugin.objects.filter(title='Email')

        return ctx

    def get_success_url(self):
        return reverse('update-alert-user-data', kwargs=self.kwargs)


class ServiceListView(LoginRequiredMixin, ListView):
    model = Service
    context_object_name = 'services'

    # adds 'service.active_checks_count' and 'service.inactive_checks_count' to the services queryset
    # need raw SQL here because this can't be expressed in django's ORM until at least v1.8...
    _queryset_extra = {
        'select': {
            'active_checks_count':
                "SELECT COUNT(*)\n"
                "FROM {statuscheck}\n"
                "INNER JOIN {service_status_checks} "
                "ON ({statuscheck}.id = {service_status_checks}.statuscheck_id)\n"
                "WHERE {statuscheck}.active = TRUE\n"
                "  AND {service_status_checks}.service_id = {service}.id".format(
                    statuscheck=StatusCheck._meta.db_table,
                    service_status_checks=Service.status_checks.through._meta.db_table,
                    service=Service._meta.db_table,
                ),
            'inactive_checks_count':
                "SELECT COUNT(*)\n"
                "FROM {statuscheck}\n"
                "INNER JOIN {service_status_checks} "
                "ON ({statuscheck}.id = {service_status_checks}.statuscheck_id)\n"
                "WHERE {statuscheck}.active = FALSE\n"
                "  AND {service_status_checks}.service_id = {service}.id".format(
                    statuscheck=StatusCheck._meta.db_table,
                    service_status_checks=Service.status_checks.through._meta.db_table,
                    service=Service._meta.db_table,
                ),
        }
    }

    def get_queryset(self):
        # we preload the check counts manually here to avoid an extra 4 DB hits per service in the template
        return Service.objects.all().order_by('name').extra(**self._queryset_extra)

    def get_context_data(self, **kwargs):
        context = super(ServiceListView, self).get_context_data(**kwargs)
        context['service_image'] = settings.SERVICE_IMAGE
        return context


class ServiceDetailView(LoginRequiredMixin, DetailView):
    model = Service
    context_object_name = 'service'

    def get_context_data(self, **kwargs):
        context = super(ServiceDetailView, self).get_context_data(**kwargs)
        date_from = date.today() - relativedelta(day=1)
        context['report_form'] = StatusCheckReportForm(initial={
            'alerts': self.object.alerts.all(),
            'checks': self.object.status_checks.all(),
            'service': self.object,
            'date_from': date_from,
            'date_to': date_from + relativedelta(months=1) - relativedelta(days=1)
        })
        return context


class ServiceCreateView(LoginRequiredMixin, CreateView):
    model = Service
    form_class = ServiceForm

    def get_success_url(self):
        return reverse('service', kwargs={'pk': self.object.id})


class ScheduleCreateView(LoginRequiredMixin, CreateView):
    model = Schedule
    form_class = ScheduleForm
    success_url = reverse_lazy('shifts')


class ServiceUpdateView(LoginRequiredMixin, UpdateView):
    model = Service
    form_class = ServiceForm

    def get_success_url(self):
        return reverse('service', kwargs={'pk': self.object.id})


class ScheduleUpdateView(LoginRequiredMixin, UpdateView):
    model = Schedule
    form_class = ScheduleForm
    context_object_name = 'schedules'
    success_url = reverse_lazy('shifts')


class ServiceDeleteView(LoginRequiredMixin, DeleteView):
    model = Service
    success_url = reverse_lazy('services')
    context_object_name = 'service'
    template_name = 'cabotapp/service_confirm_delete.html'


class ScheduleDeleteView(LoginRequiredMixin, DeleteView):
    model = Schedule
    form_class = ScheduleForm

    success_url = reverse_lazy('shifts')
    context_object_name = 'schedule'
    template_name = 'cabotapp/schedule_confirm_delete.html'


class ScheduleSnoozeWarningsView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        hours = int(kwargs['hours'])
        if hours < 0 or hours > 24:
            messages.error(request, "Invalid number of hours to snooze for.")
        else:
            try:
                schedule = Schedule.objects.get(pk=kwargs['pk'])
                schedule.problems.silence_warnings_until = timezone.now() + timedelta(hours=hours)
                schedule.problems.save()
            except Schedule.DoesNotExist, ScheduleProblems.DoesNotExist:
                pass

        # user will see the result on the schedules list page, so redirect there
        return HttpResponseRedirect(reverse('shifts'))


class ScheduleListView(LoginRequiredMixin, ListView):
    model = Schedule
    context_object_name = 'schedules'

    def get_queryset(self):
        return Schedule.objects.all().order_by('id')

    def get_context_data(self, **kwargs):
        """Add current duty officer to list page"""
        context = super(ScheduleListView, self).get_context_data(**kwargs)
        duty_officers = {schedule: get_single_duty_officer(schedule) for schedule in Schedule.objects.all()}
        context['duty_officers'] = {
            'officers': duty_officers,
        }
        return context


class ShiftListView(LoginRequiredMixin, ListView):
    model = Shift
    context_object_name = 'shifts'

    def get_queryset(self):
        schedule = Schedule.objects.get(id=self.kwargs['pk'])
        update_shifts(schedule)
        return Shift.objects.filter(
            end__gt=datetime.utcnow().replace(tzinfo=utc),
            deleted=False,
            schedule=schedule).order_by('start')

    def get_context_data(self, **kwargs):
        context = super(ShiftListView, self).get_context_data(**kwargs)

        context['schedule'] = Schedule.objects.get(id=self.kwargs['pk'])
        context['schedule_id'] = self.kwargs['pk']
        return context


class StatusCheckReportView(LoginRequiredMixin, TemplateView):
    template_name = 'cabotapp/statuscheck_report.html'

    def get_context_data(self, **kwargs):
        form = StatusCheckReportForm(self.request.GET)
        if form.is_valid():
            return {'checks': form.get_report(), 'service': form.cleaned_data['service']}


# Misc JSON api and other stuff
def checks_run_recently(request):
    """
    Checks whether or not stuff is running by looking to see if checks have run in last 10 mins
    """
    ten_mins = datetime.utcnow().replace(tzinfo=utc) - timedelta(minutes=10)
    most_recent = StatusCheckResult.objects.filter(time_complete__gte=ten_mins)
    if most_recent.exists():
        return HttpResponse('Checks running')
    return HttpResponse('Checks not running')


def jsonify(d):
    return HttpResponse(json.dumps(d), content_type='application/json')


def json_response(data, code, pretty=False):
    '''
    Return a JSON response containing some data. Supports pretty-printing.
    '''
    dump_opts = {}
    if pretty:
        dump_opts = {'sort_keys': True, 'indent': 4, 'separators': (',', ': ')}
    content = json.dumps(data, **dump_opts) + "\n"
    return HttpResponse(content, status=code, content_type="application/json")


def json_error_response(message, code):
    '''Return a JSON response with an error message'''
    return json_response({'detail': message}, code)


class AuthComplete(View):
    def get(self, request, *args, **kwargs):
        backend = kwargs.pop('backend')
        try:
            return complete(request, backend, *args, **kwargs)
        except AuthFailed:
            messages.error(request, "Your domain isn't authorized")
            return HttpResponseRedirect(reverse('login'))


class LoginError(View):
    def get(self, request, *args, **kwargs):
        return HttpResponse(status=401)


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


class ViewError(Exception):
    '''
    A general-purpose HTTP request-processing exception that carries both an
    error message and HTTP status code to be returned to the client.
    '''
    def __init__(self, message, code):
        super(ViewError, self).__init__(message)
        self.code = code


class ActivityCounterView(View):

    # Enable transactions to prevent race conditions when multiple requests are
    # reading and updating a counter.
    @transaction.atomic
    def get(self, request, pk):
        '''Handle an HTTP GET request'''
        id = request.GET.get('id', None)
        name = request.GET.get('name', None)

        # We require the name or id of a check
        if not (id or name):
            return json_error_response('Please provide a name or id', 400)

        try:
            # Lookup the check and make sure it has a related ActivityCounter
            # - Use select_for_update() to lock matching rows so that concurrent
            #   requests don't clobber each other when inc/decrementing.
            # - IMPORTANT: pass the 'counter' object around rather than re-fetching
            #   it via `check.activity_counter`. This will prevent us from reading
            #   old values during the transaction (particularly for MySQL, which
            #   in our case will snapshot the DB at the start of the transaction.
            check = self._lookup_check(id, name)
            counter = ActivityCounter.objects.select_for_update().get_or_create(status_check=check)[0]

            # Perform the action and return the result
            action = request.GET.get('action', 'read')
            pretty = request.GET.get('pretty') == 'true'
            message = self._handle_action(action, counter)

        except ViewError as e:
            return json_error_response(e.message, e.code)

        data = {
            'check.id': check.id,
            'check.name': check.name,
            'check.run_delay': check.run_delay,
            'counter.count': counter.count,
            'counter.enabled': check.use_activity_counter,
            'counter.last_enabled': format_datetime(counter.last_enabled),
            'counter.last_disabled': format_datetime(counter.last_disabled),
        }
        if message:
            data['detail'] = message
        return json_response(data, 200, pretty=pretty)

    def _lookup_check(self, id, name):
        '''
        Lookup the check by id or name. Id is preferred.
        - Returns a StatusCheck object.
        - Will raise a ViewError if no check is found.
        '''
        checks = None
        if id:
            checks = StatusCheck.objects.filter(id=id)
        if name and not checks:
            checks = StatusCheck.objects.filter(name=name)
            if checks and len(checks) > 1:
                raise ViewError("Multiple checks found with name '{}'".format(name), 500)
        if not checks:
            raise ViewError('Check not found', 404)
        return checks.first()

    def _handle_action(self, action, counter):
        '''
        Perform the given action on the counter.
        - Return a message to be sent back in the response, or None.
        - Raises a ViewError if given an invalid action.
        '''
        if action == 'read':
            return None

        if action == 'incr':
            counter.increment_and_save()
            return 'counter incremented to {}'.format(counter.count)

        if action == 'decr':
            counter.decrement_and_save()
            return 'counter decremented to {}'.format(counter.count)

        if action == 'reset':
            counter.reset_and_save()
            return 'counter reset to 0'

        raise ViewError("invalid action '{}'".format(action), 400)


class SendTestAlertView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        alert = AlertPlugin.objects.get(pk=kwargs['alert_pk'])

        try:
            alert.send_test_alert(self.request.user)
            messages.success(self.request, "Alert sent.", extra_tags="alert-success")
        except Exception as e:
            logger.exception("Exception occurred sending test alert %s to user %s. This can happen normally "
                             "(e.g. if the user did not answer a Twilio phone call).",
                             alert.title, self.request.user)
            messages.error(self.request, "Exception occurred while sending alert: {}. This can happen normally "
                                         "(e.g. if you hung up on a Twilio phone call).".format(e),
                           extra_tags="alert-danger")

        return HttpResponseRedirect(reverse('update-alert-user-data', kwargs={
            'pk': self.request.user.pk,
            'alerttype': kwargs['alerttype']
        }))


class AckListView(LoginRequiredMixin, ListView):
    model = Acknowledgement
    context_object_name = 'acks'

    def get_queryset(self):
        # note: sortnig by status_check actually sorts by status check *name*, due to StatusCheck's meta.ordering
        return Acknowledgement.objects.filter(closed_at__isnull=True).order_by('status_check', '-id').prefetch_related()

    def get_context_data(self, **kwargs):
        ctx = super(AckListView, self).get_context_data(**kwargs)
        threshold = timezone.now() - timezone.timedelta(days=7)
        ctx['closed_acks'] = Acknowledgement.objects.filter(closed_at__gte=threshold) \
                                                    .order_by('-closed_at')[:NUM_VISIBLE_CLOSED_ACKS]
        return ctx


class AckForm(GroupedModelForm):
    class Meta(GroupedModelForm.Meta):
        model = Acknowledgement
        grouped_fields = (
            ('Filter', ('status_check', 'match_if', 'tags', 'note')),
            ('Duration', ('expire_at', 'close_after_successes')),
        )
        widgets = {
            'status_check': forms.Select(attrs={
                'data-rel': 'chosen',
                'style': 'width: 70%',
            }),
            'tags': forms.SelectMultiple(attrs={
                'data-rel': 'chosen',
                'style': 'width: 70%',
            }),
            'match_if': forms.RadioSelect(),
            'note': forms.Textarea(attrs={
                'rows': 2,
                'style': 'width: 70%',
            }),
            'expire_at': TimeFromNowField(
                times=EXPIRE_AFTER_HOURS_OPTIONS,
                choices=[('', 'Never (dangerous!)')],
                attrs={
                    'data-rel': 'chosen',
                    'style': 'width: 70%',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super(AckForm, self).__init__(*args, **kwargs)
        self.fields['tags'].required = False  # tags list can be blank
        self.fields['expire_at'].required = False  # expire_at can be blank
        self.fields['close_after_successes'].required = False  # close_after_successes can be blank


def _update_check_and_services_timeout(ack, timeout_seconds):
    # type: (Acknowledgement, Optional[float]) -> bool
    """
    Runs this ack's status_check and updates the status of any associated services.
    Since the check may take a long time to run (e.g. more than a web request), the check is run by submitting a
    celery task and waiting up to timeout_seconds for it to complete. If it does not complete within
    timeout_seconds, this function will return False (but the task is not aborted; it may still complete).

    You should call this whenever you create or close an ack.
    :param timeout_seconds: Timeout in seconds; if the check takes longer than this to run, will return False.
                            If 0, will schedule the update and immediately return.
                            If None, will block until the check completes (dangerous for UI!).
    :return: True if the check completed within timeout_seconds, False otherwise
    """
    check_id = ack.status_check.id
    start = timezone.now()
    update_check_and_services.apply_async((check_id,))

    # we don't have a result store for celery, so we just poll the DB
    # to see if the check has re-run (and assume the service will update soon after)
    remaining = timeout_seconds
    interval = 0.5
    while remaining > 0:
        interval = min(interval, remaining)
        time.sleep(interval)
        remaining -= interval

        check = StatusCheck.objects.get(id=check_id)
        if check.last_run and check.last_run > start:
            return True

    return False


def _on_ack_changed(request, ack):
    if ack and not _update_check_and_services_timeout(ack, timeout_seconds=ACK_UPDATE_SERVICE_TIMEOUT_SECONDS):
        messages.warning(request, ACK_SERVICE_NOT_YET_UPDATED_MSG, extra_tags="alert-warning")


class AckUpdateView(LoginRequiredMixin, UpdateView):
    form_class = AckForm
    template_name = 'cabotapp/acknowledgement_form.html'
    model = Acknowledgement

    def get_success_url(self):
        return '{}#check-{}'.format(reverse('acks'), self.object.status_check.id)

    def form_valid(self, form):
        if self.request.user is not None and not isinstance(self.request.user, AnonymousUser):
            form.instance.created_by = self.request.user

        # always create a new instance
        old_ack_id = self.object.id
        form.instance.pk = None

        # in transaction since it will probably an existing ack
        with transaction.atomic():
            result = super(AckUpdateView, self).form_valid(form)

        # since _on_ack_changed only knows about the current status check ID, make sure we update
        # the status check from the old ack in case it was changed (but don't bother waiting on it)
        old_ack = Acknowledgement.objects.get(id=old_ack_id)
        if not old_ack.closed_at:
            old_ack.close('ack updated')
            update_check_and_services.apply_async((old_ack.status_check_id,))

        _on_ack_changed(self.request, self.object)

        return result


class AckCreateView(LoginRequiredMixin, CreateView):
    form_class = AckForm
    template_name = 'cabotapp/acknowledgement_form.html'

    def get_success_url(self):
        return '{}#check-{}'.format(reverse('acks'), self.object.status_check.id)

    def get_initial(self):
        result_id = int(self.request.GET.get('result_id', '0'))
        check_id = int(self.request.GET.get('check_id', '0'))
        if result_id and check_id:
            raise ViewError('specify result_id or check_id, not both', 400)

        result = StatusCheckResult.objects.get(id=result_id) if result_id else None
        if check_id:
            check = StatusCheck.objects.get(id=check_id)
        elif result:
            check = result.status_check
        else:
            check = None

        return {
            'status_check': check.pk if check else '',
            'tags': result.tags.all() if result else None,
            'match_if': Acknowledgement.MATCH_CHECK if not result else Acknowledgement.MATCH_ALL_IN,
            'expire_at': self.request.GET.get('expire_after_hours', '4'),  # default to expiring after 4 hours
            'close_after_successes': 1,
        }

    def form_valid(self, form):
        if self.request.user is not None and not isinstance(self.request.user, AnonymousUser):
            form.instance.created_by = self.request.user

        result = super(AckCreateView, self).form_valid(form)
        _on_ack_changed(self.request, self.object)
        return result

    def get_context_data(self, **kwargs):
        context = super(AckCreateView, self).get_context_data(**kwargs)
        return context


class AckCloseView(LoginRequiredMixin, View):
    def get(self, request, pk, **kwargs):
        user = request.user if request.user.pk else None
        username = user.username if user else 'anonymous user'
        ack = Acknowledgement.objects.get(pk=int(pk))
        ack.close('closed by {} through web'.format(username))
        _on_ack_changed(request, ack)
        return HttpResponseRedirect(reverse('acks'))


class AckReopenView(LoginRequiredMixin, View):
    def get(self, request, pk, **kwargs):
        user = request.user if request.user.pk else None  # None if anonymous user
        ack = Acknowledgement.objects.get(pk=int(pk))
        new_ack = ack.clone(created_by=user)
        _on_ack_changed(request, new_ack)
        return HttpResponseRedirect(reverse('acks'))

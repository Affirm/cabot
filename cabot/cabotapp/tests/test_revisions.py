from urlparse import urlsplit

from django.core.urlresolvers import reverse, resolve

from cabot.cabotapp.models import Service, StatusCheck, HttpStatusCheck, TCPStatusCheck, JenkinsStatusCheck
from cabot.cabotapp.tests.utils import LocalTestCase
from cabot.cabotapp.revision_utils import get_revisions
from cabot.cabotapp.views import ServiceForm, HttpStatusCheckForm, JenkinsStatusCheckForm, TCPStatusCheckForm

import reversion


def get_post_data(obj, form_class, changed_fields):
    form = form_class(instance=obj)
    old_fields = {}
    for field_name in form.fields:
        val = form[field_name].value()
        if val is None:
            val = ''
        old_fields[field_name] = val
    return dict(old_fields.items() + changed_fields.items())


def _create_check_url(check_cls):
    urls = {
        HttpStatusCheck: reverse('create-http-check'),
        JenkinsStatusCheck: reverse('create-jenkins-check'),
        TCPStatusCheck: reverse('create-tcp-check'),
    }
    return urls[check_cls]


def _edit_check_url(check):
    if type(check) == HttpStatusCheck:
        return reverse('update-http-check', kwargs={'pk': check.pk})
    raise NotImplemented()


_check_form_classes = {
    HttpStatusCheck: HttpStatusCheckForm,
    JenkinsStatusCheck: JenkinsStatusCheckForm,
    TCPStatusCheck: TCPStatusCheckForm,
}


class TestRevisions(LocalTestCase):
    def setUp(self):
        # make sure we create initial revisions for everything
        with reversion.create_revision():
            super(TestRevisions, self).setUp()

    def _update_service(self, service, changed_fields):
        data = get_post_data(service, ServiceForm, changed_fields)
        response = self.client.post(reverse('update-service', kwargs={'pk': service.pk}), data=data)
        self.assertEqual(response.status_code, 302)

        # return refreshed from db obj
        return Service.objects.get(pk=self.service.pk)

    def _delete_check(self, check):
        response = self.client.post(reverse('delete-check', kwargs={'pk': check.pk}))
        self.assertEqual(response.status_code, 302)
        return None

    def _create_check(self, model, fields):
        data = get_post_data(None, _check_form_classes[model], fields)
        response = self.client.post(_create_check_url(model), data=data)
        self.assertEqual(response.status_code, 302)
        pk = resolve(urlsplit(response.url).path).kwargs['pk']
        return model.objects.get(pk=pk)

    def _update_check(self, check, changed_fields):
        model = type(check)
        data = get_post_data(check, _check_form_classes[model], changed_fields)
        response = self.client.post(_edit_check_url(check), data=data)
        self.assertEqual(response.status_code, 302)
        return model.objects.get(pk=check.pk)

    def test_update_service(self):
        self.service = self._update_service(self.service, {'name': 'cool service'})
        self.assertEqual(self.service.name, 'cool service')

    def test_delete_check(self):
        self.assertTrue(StatusCheck.objects.filter(pk=self.jenkins_check.pk).exists())
        self.assertTrue(StatusCheck.objects.filter(pk=self.http_check.pk).exists())

        self._delete_check(self.jenkins_check)
        self.assertFalse(StatusCheck.objects.filter(pk=self.jenkins_check.pk).exists())
        self._delete_check(self.http_check)
        self.assertFalse(StatusCheck.objects.filter(pk=self.http_check.pk).exists())

    def test_service_revision_single_field(self):
        self.service = self._update_service(self.service, {'name': 'cool service'})

        revisions = get_revisions(self.service, 3)  # request more revisions than there actually are
        self.assertEqual(len(revisions), 1)
        changes = revisions[0][1]
        self.assertEqual(changes['name'][0], 'Service')       # old name
        self.assertEqual(changes['name'][1], 'cool service')  # new name

    def test_service_revision_multiple_fields(self):
        self.service = self._update_service(self.service, {
            'name': 'cool service',
            'users_to_notify': [self.user.pk],
            'url': 'http://google.com',
        })

        revisions = get_revisions(self.service, 1)
        self.assertEqual(len(revisions), 1)
        changes = revisions[0][1]
        self.assertEqual(changes['name'][0], 'Service')
        self.assertEqual(changes['name'][1], 'cool service')
        self.assertEqual(changes['users_to_notify'][0], '[]')
        self.assertEqual(changes['users_to_notify'][1], '[testuser]')
        self.assertEqual(changes['url'][0], '<span class="text-muted">none</span>')
        self.assertEqual(changes['url'][1], 'http://google.com')

    def test_service_multiple_revisions_and_fields(self):
        self.service = self._update_service(self.service, {
            'name': 'revision 1',
        })
        self.service = self._update_service(self.service, {
            'name': 'revision 2',
            'users_to_notify': [self.user.pk],
        })
        self.service = self._update_service(self.service, {
            'name': 'revision 3',
            'url': 'http://google.com',
        })
        self.service = self._update_service(self.service, {
            'name': 'revision 4',
        })

        revisions = get_revisions(self.service, 3)  # request fewer revisions than there actually are
        self.assertEqual(len(revisions), 3)

        none_str = '<span class="text-muted">none</span>'
        expected_changes = [
            {
                'name': ('revision 3', 'revision 4'),
            },
            {
                'name': ('revision 2', 'revision 3'),
                'url': (none_str, 'http://google.com')
            },
            {
                'name': ('revision 1', 'revision 2'),
                'users_to_notify': ('[]', '[testuser]')
            }
        ]

        for expected, revision in zip(expected_changes, revisions):
            actual_changes = revision[1]
            for field_name, (expected_old, expected_new) in expected.items():
                self.assertEqual(actual_changes[field_name][0], expected_old)
                self.assertEqual(actual_changes[field_name][1], expected_new)

    def test_service_check_deleted(self):
        self.assertTrue(self.service.status_checks.filter(pk=self.http_check.pk).exists())
        self._delete_check(self.http_check)
        self.assertFalse(self.service.status_checks.filter(pk=self.http_check.pk).exists())

        revisions = get_revisions(self.service, 1)
        self.assertEqual(len(revisions), 1)
        self.assertEqual(revisions[0][1]['status_checks'],
                         ('[Jenkins Check, TCP Check, <span class="text-muted">deleted: Http Check</span>]',
                          '[Jenkins Check, TCP Check]'))

    def test_check_added_with_service(self):
        """Check if a Service revision is saved when a check is created with some service(s) immediately specified"""
        new_check = self._create_check(HttpStatusCheck, {
            'name': 'New Check',
            'endpoint': 'http://affirm.com',
            'service_set': [self.service.pk]
        })
        self.assertTrue(new_check.service_set.filter(pk=self.service.pk).exists())

        revisions = get_revisions(self.service, 1)
        self.assertEqual(len(revisions), 1)
        self.assertEqual(revisions[0][1]['status_checks'], ('[Http Check, Jenkins Check, TCP Check]',
                                                            '[Http Check, Jenkins Check, New Check, TCP Check]'))

    def test_change_service_from_check(self):
        self.assertTrue(self.service.status_checks.filter(pk=self.http_check.pk).exists())
        self.http_check = self._update_check(self.http_check, {
            'service_set': []
        })
        self.assertFalse(self.service.status_checks.filter(pk=self.http_check.pk).exists())

        revisions = get_revisions(self.service, 1)
        self.assertEqual(len(revisions), 1)
        self.assertEqual(revisions[0][1]['status_checks'], ('[Http Check, Jenkins Check, TCP Check]',
                                                            '[Jenkins Check, TCP Check]'))

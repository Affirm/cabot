# -*- coding: utf-8 -*-
from datetime import timedelta
from datetime import date
import threading

from django.core.urlresolvers import reverse
from django.db import IntegrityError, connection
from django.test.client import Client
from django.utils import timezone

from rest_framework.test import APITransactionTestCase

from cabot.cabotapp.models import Service, HttpStatusCheck, ServiceStatusSnapshot
from cabot.cabotapp.views import StatusCheckReportForm, ServiceListView
from cabot.cabotapp.tests.utils import LocalTestCase


class TestWebInterface(LocalTestCase):

    def setUp(self):
        super(TestWebInterface, self).setUp()
        self.client = Client()

    def test_set_recovery_instructions(self):
        # Get service page - will get 200 from login page
        resp = self.client.get(reverse('update-service', kwargs={'pk': self.service.id}), follow=True)
        self.assertEqual(resp.status_code, 200)

        # Log in
        self.client.login(username=self.username, password=self.password)
        resp = self.client.get(reverse('update-service', kwargs={'pk': self.service.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('username', resp.content)

        snippet_link = 'https://sub.hackpad.com/wiki-7YaNlsC11bB.js'
        self.assertEqual(self.service.hackpad_id, None)
        resp = self.client.post(
            reverse('update-service', kwargs={'pk': self.service.id}),
            data={
                'name': self.service.name,
                'hackpad_id': snippet_link,
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        reloaded = Service.objects.get(id=self.service.id)
        self.assertEqual(reloaded.hackpad_id, snippet_link)
        # Now one on the blacklist
        blacklist_link = 'https://unapproved_link.domain.com/wiki-7YaNlsC11bB.js'
        resp = self.client.post(
            reverse('update-service', kwargs={'pk': self.service.id}),
            data={
                'name': self.service.name,
                'hackpad_id': blacklist_link,
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('valid JS snippet link', resp.content)
        reloaded = Service.objects.get(id=self.service.id)
        # Still the same
        self.assertEqual(reloaded.hackpad_id, snippet_link)

    def test_checks_report(self):
        form = StatusCheckReportForm({
            'service': self.service.id,
            'checks': [self.http_check.id],
            'date_from': date.today() - timedelta(days=1),
            'date_to': date.today(),
        })
        self.assertTrue(form.is_valid())
        checks = form.get_report()
        self.assertEqual(len(checks), 1)
        check = checks[0]
        self.assertEqual(len(check.problems), 1)
        self.assertEqual(check.success_rate, 50)

    def test_services_list(self):
        """test the services list queryset, since it uses some custom SQL for the active/inactive check counts"""
        # add a disabled check
        inactive_check = HttpStatusCheck(active=False)
        inactive_check.save()
        self.service.status_checks.add(inactive_check)
        self.service.save()

        qs = ServiceListView().get_queryset().all()
        self.assertEquals(len(qs), 1)
        service = qs[0]

        # check the extra fields are correct
        self.assertEquals(service.active_checks_count, 3)
        self.assertEquals(service.inactive_checks_count, 1)


class TestWebConcurrency(APITransactionTestCase):
    def setUp(self):
        self.http_check = HttpStatusCheck.objects.create(
            id=10102,
            name='Http Check',
            importance=Service.CRITICAL_STATUS,
            endpoint='http://arachnys.com',
            timeout=10,
            status_code='200',
            text_match=None,
        )
        self.service = Service.objects.create(
            id=2194, name='Service',
        )
        self.service.save()
        self.service.status_checks.add(self.http_check)

        self.client = Client()

    def test_delete_service(self):
        # first, generate a lot of snapshots so the on service delete cascade will take time
        ServiceStatusSnapshot.objects.bulk_create([
            ServiceStatusSnapshot(service=self.service, time=timezone.now()) for _ in range(30000)
        ])

        exceptions = []

        def delete_service():
            try:
                Service.objects.get(pk=self.service.pk).delete()
            except Exception, e:
                exceptions.append(e)
                # note exceptions raised in another thread won't cause the main thread to fail the test
                # but we raise anyway so the exception gets printed to stderr
                raise
            finally:
                # manually close DB connection, otherwise it stays open and tests can't terminate cleanly
                connection.close()

        # start deleting
        delete_thread = threading.Thread(target=delete_service)
        delete_thread.start()

        # simultaneously keep creating snapshots in the background
        try:
            for _ in range(100):
                self.service.update_status()
        except IntegrityError:
            # this happens if the delete succeeded (service no longer exists) and is expected
            pass

        delete_thread.join()

        # check if delete_service failed
        self.assertEquals(len(exceptions), 0)
        self.assertFalse(Service.objects.filter(pk=self.service.pk).exists())

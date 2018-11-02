from django.core.urlresolvers import reverse
from mock import patch, Mock
from django.utils import timezone
from cabot.cabotapp.models import Acknowledgement, StatusCheckResult, StatusCheckResultTags
from .utils import LocalTestCase, fake_http_404_response, fake_http_200_response, patch_field_default

# from cabot.cabotapp.alert import send_alert, AlertPlugin
# @patch('cabot.cabotapp.models.send_alert')
# @patch('cabot.cabotapp.alert.AlertPlugin.send_alert')


class TestAcks(LocalTestCase):
    def setUp(self):
        super(TestAcks, self).setUp()
        self.service.update_status()

        self.client.login(username=self.username, password=self.password)

    def fail_http_check(self):
        """runs self.http_check such that it will fail, then returns the StatusCheckResult"""
        with patch('cabot.cabotapp.models.requests.request', fake_http_404_response):
            self.http_check.run()
        return self.http_check.last_result()

    def pass_http_check(self):
        """runs self.http_check such that it will pass, then returns the StatusCheckResult"""
        with patch('cabot.cabotapp.models.requests.request', fake_http_200_response):
            self.http_check.run()
        return self.http_check.last_result()

    def test_create_ack_for_result(self):
        # TODO test tags here
        result = self.fail_http_check()
        self.assertFalse(result.succeeded)
        self.assertFalse(result.acked)

        resp = self.client.get(reverse('create-ack-for-results', kwargs={'result_ids': result.id}))
        self.assertEquals(resp.status_code, 200)

        ack = Acknowledgement.objects.get(status_check=self.http_check)
        self.assertEquals(ack.created_by_id, self.user.id)
        self.assertTrue(ack.matches_result(result))
        self.assertEquals(ack.match_if, Acknowledgement.MATCH_ALL_IN)

    def test_create_ack_for_result_triggers(self):
        self.fail_http_check()
        result = self.http_check.last_result()
        self.assertFalse(result.succeeded)
        self.assertFalse(result.acked)

        resp = self.client.get(reverse('create-ack-for-results', kwargs={'result_ids': result.id}))
        self.assertEquals(resp.status_code, 200)

        # run the check again
        result = self.fail_http_check()
        self.assertFalse(result.succeeded)  # should still be considered unsuccessful
        self.assertTrue(result.acked)  # ...but acked

    def test_check_acked_status(self):
        # create an ack on this check
        ack = Acknowledgement(status_check=self.http_check, match_if=Acknowledgement.MATCH_CHECK)
        ack.save()

        # test that the check becomes 'acked' if it fails
        result = self.fail_http_check()
        self.assertTrue(result.acked)
        self.assertEquals(self.http_check.calculated_status, 'acked')

        # test that status returns to 'passing' once the check passes (even if there is an active ack)
        result = self.pass_http_check()
        self.assertFalse(result.acked)
        self.assertEquals(self.http_check.calculated_status, 'passing')

    def test_service_acked_status(self):
        self.pass_http_check()

        # verify the service starts out passing
        self.service.update_status()
        self.assertEquals(self.service.overall_status, 'PASSING')

        # test that the service becomes 'acked' if a check becomes 'acked'
        ack = Acknowledgement(status_check=self.http_check, match_if=Acknowledgement.MATCH_CHECK)
        ack.save()

        result = self.fail_http_check()
        self.assertTrue(result.acked)
        self.assertEquals(self.http_check.calculated_status, 'acked')

        self.service.update_status()
        self.assertEquals(self.service.overall_status, 'ACKED')

        # test that service status goes back to normal if we delete the ack and the check still fails
        ack.delete()
        self.fail_http_check()
        self.service.update_status()
        self.assertEquals(self.service.overall_status, 'CRITICAL')

    def test_match_check_only(self):
        ack = Acknowledgement(status_check=self.http_check, match_if=Acknowledgement.MATCH_CHECK)
        ack.save()

        http_result = self.fail_http_check()
        self.jenkins_check.run()
        jenkins_result = self.jenkins_check.last_result()

        self.assertTrue(ack.matches_result(http_result))
        self.assertFalse(ack.matches_result(jenkins_result))

    def test_match_all_in(self):
        tags = [StatusCheckResultTags.objects.get_or_create(value='tag' + str(i))[0] for i in range(3)]
        ack = Acknowledgement(status_check=self.http_check, match_if=Acknowledgement.MATCH_ALL_IN)
        ack.save()
        ack.tags.add(tags[0], tags[1])

        now = timezone.now()
        result = StatusCheckResult(check=self.http_check, succeeded=False, time=now, time_complete=now)
        result.save()

        # no tags matches
        self.assertTrue(ack.matches_result(result))

        # 1 matching tag matches
        result.tags.add(tags[0])
        self.assertTrue(ack.matches_result(result))

        # 1 matching, 1 not should NOT match
        result.tags.add(tags[2])
        self.assertFalse(ack.matches_result(result))

    def test_match_exact(self):
        tags = [StatusCheckResultTags.objects.get_or_create(value='tag' + str(i))[0] for i in range(3)]
        ack = Acknowledgement(status_check=self.http_check, match_if=Acknowledgement.MATCH_EXACT)
        ack.save()
        ack.tags.add(tags[0], tags[1])

        now = timezone.now()
        result = StatusCheckResult(check=self.http_check, succeeded=False, time=now, time_complete=now)
        result.save()

        # no tags does not match
        self.assertFalse(ack.matches_result(result))

        # 1 matching tag still does not match
        result.tags.add(tags[0])
        self.assertFalse(ack.matches_result(result))

        # exact match should match
        result.tags.add(tags[1])
        self.assertTrue(ack.matches_result(result))

        # extra tag should not match
        result.tags.add(tags[2])
        self.assertFalse(ack.matches_result(result))

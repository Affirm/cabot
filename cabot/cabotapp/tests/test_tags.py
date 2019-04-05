from django.utils import timezone

from cabot.cabotapp import tasks
from cabot.cabotapp.models import StatusCheckResult, StatusCheckResultTag
from .utils import LocalTestCase


class TestTags(LocalTestCase):
    def setUp(self):
        super(TestTags, self).setUp()
        self.service.update_status()

        self.client.login(username=self.username, password=self.password)

    def test_clean_orphaned_tags(self):
        StatusCheckResult.objects.all().delete()
        StatusCheckResultTag.objects.all().delete()

        now = timezone.now()
        results = [StatusCheckResult(status_check=self.http_check, time=now, time_complete=now, succeeded=False)
                   for _ in range(100)]
        StatusCheckResult.objects.bulk_create(results)

        tags = [StatusCheckResultTag(value='tag{:03}'.format(i)) for i in range(100)]
        StatusCheckResultTag.objects.bulk_create(tags)

        results = StatusCheckResult.objects.filter(status_check=self.http_check)
        tags = StatusCheckResultTag.objects.all()

        # add tags 0-49 to first 50 results
        for result, tag in zip(results[:50], tags[:50]):
            result.tags.add(tag)

        # tags 50-99 should get cleaned up here
        tasks.clean_orphaned_tags()

        tags = StatusCheckResultTag.objects.order_by('value')
        self.assertEqual(len(tags), 50)  # 50 left
        self.assertEqual(list(tags.values_list('value', flat=True)), [u'tag{:03}'.format(i) for i in range(50)])

        # now if we delete the status check results, all tags should all get cleaned up
        StatusCheckResult.objects.all().delete()
        tasks.clean_orphaned_tags()

        tags = StatusCheckResultTag.objects.order_by('value')
        self.assertEqual(len(tags), 0)

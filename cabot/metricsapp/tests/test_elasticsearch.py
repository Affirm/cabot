from django.test import TestCase
from cabot.metricsapp.models import ElasticsearchSource


class TestElasticsearchSource(TestCase):
    def setUp(self):
        self.es_source = ElasticsearchSource.objects.create(
            name='elastigirl',
            url='localhost',
            index='i'
        )

    def test_client(self):
        client = self.es_source.client
        self.assertIn('localhost', repr(client))

    def test_client_whitespace(self):
        """Whitespace should be stripped from the url"""
        self.es_source.url = '\n\nlocalhost     '
        self.es_source.save()
        client = self.es_source.client
        self.assertIn('localhost', repr(client))
        self.assertNotIn('\nlocalhost', repr(client))
        self.assertNotIn('localhost ', repr(client))

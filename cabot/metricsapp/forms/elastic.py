from django.core.exceptions import ValidationError
from django.forms import ModelForm
from elasticsearch.client import ClusterClient
from elasticsearch.exceptions import ConnectionError
from cabot.metricsapp.api.elastic import create_es_client
from cabot.metricsapp.models import ElasticsearchSource


class ElasticsearchSourceForm(ModelForm):
    class Meta:
        model = ElasticsearchSource

    def clean_url(self):
        """Make sure the input url is a valid Elasticsearch hosts."""
        url = self.cleaned_data['url']

        # Create an Elasticsearch test client and see if a health check for the instance succeeds
        try:
            client = create_es_client(url)
            ClusterClient(client).health()
            return url
        except ConnectionError:
            raise ValidationError('Invalid Elasticsearch host url(s).')

import json
import logging
import requests
import urlparse
from django.core.exceptions import ValidationError


logger = logging.getLogger(__name__)


def get_grafana_auth_headers(api_key):
    """
    Returns request headers for accessing the Grafana API with an API key
    :param api_key: the API key
    :return: dictionary of relevant headers
    """
    return {'Authorization': 'Bearer {}'.format(api_key)}


def get_dashboards(url, api_key):
    """
    Get data for all Grafana dashboards
    :param url: url for the Grafana instance
    :param api_key: API key for the Grafana instance
    :return: api response containing dashboard id, title, uri, etc.
    """
    response = requests.get(urlparse.urljoin(url, 'api/search'), headers=get_grafana_auth_headers(api_key))

    if response.status_code == 200:
        return json.loads(response.text)
    else:
        logger.exception('Request to {} failed'.format(url))
        raise ValidationError('Request to Grafana API failed.')


def get_dashboard_choices(api_response):
    """
    Given a response from the Grafana API, find a list of dashboard name choices
    :param api_response: response data from the Grafana API
    :return: list of dashboard URIs and names
    """
    # Uri format is db/dashboard-name. Get rid of the leading db.
    return [(dash['uri'].split('/')[1], dash['title']) for dash in api_response]


def get_dashboard_info(grafana_url, api_key, dashboard_uri):
    """
    Get data about a Grafana dashboard
    :param url: url for the Grafana instance
    :param api_key: API key for the Grafana instance
    :param dashboard_uri: dashboard part of the url
    :return: api response containing creator information and panel information
    """
    http_api = urlparse.urljoin(grafana_url, 'api/dashboards/db/')
    response = requests.get(urlparse.urljoin(http_api, dashboard_uri), headers=get_grafana_auth_headers(api_key))

    if response.status_code == 200:
        return json.loads(response.text)
    else:
        logger.exception('Request to {} for dashboard {} failed'.format(grafana_url, dashboard_uri))
        raise ValidationError('Request to Grafana API failed.')


def get_panel_choices(dashboard_info, templating_dict):
    """
    Get a list of panel choices (names and data)
    :param dashboard_info: Dashboard data from the Grafana API
    :return list of ({panel_id, datasource, panel_info}, name) tuples for panels
    """
    panels = []
    for row in dashboard_info['dashboard']['rows']:
        for panel in filter(lambda panel: panel['type'] == 'graph', row['panels']):
            datasource = panel.get('datasource')
            # default datasource is not listed in the API response
            if datasource is None:
                datasource = 'default'

            title = template_response(panel['title'], templating_dict)
            panels.append((dict(panel_id=panel['id'], datasource=datasource, panel_info=panel), title))

    return panels


def get_series_choices(dashboard_info, panel_info, templating_dict):
    """
    Get a list of the series for the panel with the input id
    :param dashboard_info: Dashboard data from the Grafana API
    :param panel_id: the id of the selected panel
    :return list of (id, series_info) tuples from the series in the panel
    """
    templated_panel = template_response(panel_info, templating_dict)
    out = []
    # Will display all fields in a json blob (not pretty but it works)
    for series in templated_panel['targets']:
        ref_id = series.pop('refId')
        series.pop('dsType')
        out.append((ref_id, json.dumps(series)))
    return out


def template_response(data, templating_dict):
    """
    Change data from the Grafana dashboard API response
    based on the dashboard templates
    :param data: Data from the Grafana dashboard API
    :param templating_info: dictionary of {template_name, output_value}
    :return: panel_info with all templating values filled in
    """
    data = json.dumps(data)
    # Loop through all the templates and replace them if they're used in this panel
    for template in templating_dict:
        data = data.replace('${}'.format(template), templating_dict[template])
    return json.loads(data)


def create_generic_templating_dict(dashboard_info):
    """
    Generic templating dictionary: name just maps to value
    :param dashboard_info: Grafana dashboard API response
    :return: dict of {"name": "value"}
    """
    templates = {}

    templating_info = dashboard_info['dashboard']['templating']
    for template in filter(lambda template: template.get('current'), templating_info['list']):
        value = template['current']['value']
        name = template['name']

        if isinstance(value, list):
            value = ', '.join(value)
        elif value == '$__auto_interval':
            value = 'auto'

        templates[name] = value

    return templates


def get_status_check_fields(dashboard_info, panel_info, grafana_instance_id, datasource, templating_dict):
    """
    Given dashboard, panel, instance, and datasource info, find the fields for a generic status check
    :param dashboard_info: Grafana API dashboard info
    :param panel_info: Grafana API panel info
    :param grafana_instance_id: ID of the Grafana instance used
    :return: dictionary containing StatusCheck field names and values
    """
    fields = {}

    fields['name'] = template_response(panel_info['title'], templating_dict)
    fields['source_info'] = dict(grafana_source_name=datasource,
                                 grafana_instance_id=grafana_instance_id)

    # Earliest time is formatted "now-3h"
    timestring = str(dashboard_info['dashboard']['time']['from'].split('-')[1])
    # Can be None if the time range is not in days, hours, or minutes
    fields['time_range'] = get_time_range(timestring)
    fields['thresholds'] = [threshold['value'] for threshold in panel_info['thresholds']]

    return fields


def get_time_range(timestring):
    """
    Find the number of digits a time string corresponds to.
    :param timestring: time string in the format "3h" or "1d" or "10m"
    :return: integer number of minutes
    """
    time_range = None
    time_digits = int(filter(str.isdigit, timestring))

    # Days
    if 'd' in timestring:
        time_range = 1440 * time_digits

    # Hours
    elif 'h' in timestring:
        time_range = 60 * time_digits

    # Minutes
    elif 'm' in timestring:
        time_range = time_digits

    return time_range

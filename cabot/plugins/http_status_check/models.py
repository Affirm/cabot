from cabot.cabotapp.models import StatusCheck, StatusCheckResult

import re
import requests
import yaml

class HttpStatusCheck(StatusCheck):

    class Meta(StatusCheck.Meta):
        proxy = True

    @property
    def check_category(self):
        return "HTTP check"

    def _run(self):
        result = StatusCheckResult(check=self)
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
                method = self.http_method,
                url = self.endpoint,
                data = http_body,
                params = http_params,
                timeout = self.timeout,
                verify = self.verify_ssl_certificate,
                auth = auth,
                allow_redirects = self.allow_http_redirects
            )
        except requests.RequestException as e:
            result.error = u'Request error occurred: %s' % (e.message,)
            result.succeeded = False
        else:
            result.raw_data = resp.content
            result.succeeded = False

            if self.status_code and resp.status_code != int(self.status_code):
                result.error = u'Wrong code: got %s (expected %s)' % (
                    resp.status_code, int(self.status_code))
                return result

            if self.text_match is not None:
                if not re.search(self.text_match, resp.content):
                    result.error = u'Failed to find match regex /%s/ in response body' % self.text_match
                    return result

            if type(header_match) is dict and header_match:
                for header, match in header_match.iteritems():
                    if header not in resp.headers:
                        result.error = u'Missing response header: %s' % (header)
                        return result

                    value = resp.headers[header]
                    if not re.match(match, value):
                        result.error = u'Mismatch in header: %s / %s' % (header, value)
                        return result

            # Mark it as success. phew!!
            result.succeeded = True

        return result

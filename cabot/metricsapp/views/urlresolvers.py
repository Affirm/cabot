from django.core.urlresolvers import reverse


def reverse_with_service(page, request, kwargs):
    """Like django reverse, but add in an optional service GET variable."""
    url = reverse(page, kwargs=kwargs)
    service = request.GET.get('service')
    if service:
        url = '{}?service={}'.format(url, service)

    return url

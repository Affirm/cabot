from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from models import UserProfile


class TimezoneMiddleware(object):
    def process_request(self, request):
        if request.user and not isinstance(request.user, AnonymousUser):
            try:
                tz = UserProfile.objects.values('timezone').get(user=request.user)['timezone'] or timezone.utc
                timezone.activate(tz)
            except UserProfile.DoesNotExist:
                pass

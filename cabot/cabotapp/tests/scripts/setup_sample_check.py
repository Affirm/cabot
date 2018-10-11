#!/usr/bin/env python
#
# Create a sample check to be used by test_concurrent_activity_counters.sh

from cabot.cabotapp.models import (ActivityCounter, HttpStatusCheck)

check = HttpStatusCheck.objects.get_or_create(id=1000, name='Http Check 1000')[0]
counter = ActivityCounter.objects.get_or_create(status_check=check)[0]
counter.count = 0
counter.save()

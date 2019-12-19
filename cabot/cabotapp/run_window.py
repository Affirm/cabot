import json
from datetime import time
from dateutil import rrule
from django.utils import timezone


class CheckRunWindow:
    class Window:
        start_time = None  # type: time
        end_time = None  # type: time
        recurrence = None  # type: rrule.rrule

        def __init__(self, start_time, end_time, recurrence):
            # type: (time, time, rrule.rrule) -> None
            # guard against passing in a datetime or serialized rrule by accident
            if not isinstance(start_time, time):
                raise TypeError("start_time must be a time")
            if not isinstance(end_time, time):
                raise TypeError("end_time must be a time")
            if not isinstance(recurrence, rrule.rrule):
                raise TypeError("recurrence must be an rrule")

            self.start_time = start_time
            self.end_time = end_time
            self.recurrence = recurrence

        def active(self, now=timezone.now()):
            # type: (timezone.datetime) -> bool
            if now.tzinfo != timezone.utc:
                raise TypeError("only UTC datetimes are supported")

            # calculate a dtstart for recurrence that's just before now, since we don't set dtstart in the JS layer
            # rrule.str sets it to 'now' if it's not specified, but that might be after today's start time. example:
            #   1. at 10am, we create a check that should run from 8am-5pm daily
            #   2. during serialization, dtstart will be set to now (~10am)
            #   3. next(iter(recurrence)) (the first instance) wil be tomorrow at 8am (since dtstart > 8am today),
            #      so the check won't start running until tomorrow (even though it should be running now!)
            # to get around this, we could set dtstart to today at 8am, but this won't work quite right for overnights
            #   1. at 3am, we create a check that should run from 5pm-8am daily (I guess we are insomniacs)
            #   2. we override dtstart to be "now.replace(hour=start_time.hour, minute=start_time.minute)" (today, 5pm)
            #   3. next(iter(recurrence)) will be 5pm today, so the check won't start running until tonight at 5pm
            #      (even though it should be running now!)
            # no bueno. to get around *this*, we also subtract a day from dtstart.
            # (recurrence.before() will find the last instance before now, so it's okay if there are multiple events.)
            # note that recurrence does not schedule an event at dtstart; it waits until the first time >= dtstart that
            # fits the recurrence criteria, so we don't have to worry about yesterday not being an enabled day
            dtstart = (now.replace(hour=self.start_time.hour, minute=self.start_time.minute, second=0, microsecond=0)
                       - timezone.timedelta(days=1))
            recurrence = self.recurrence.replace(dtstart=dtstart)

            # grab the most recent date before or including today
            start = recurrence.before(now, inc=True)  # type: Optional[timezone.datetime]
            if start is None:
                return False

            # calc end time
            end = start.replace(hour=self.end_time.hour, minute=self.end_time.minute)
            # if start_time > end_time, assume time range is overnight and add one day to end time
            if self.start_time > self.end_time:
                end += timezone.timedelta(days=1)

            return start <= now <= end

        def __str__(self):
            return '{} to {}, {}'.format(self.start_time.strftime('%H:%M'), self.end_time.strftime('%H:%M'),
                                         self.recurrence)

        def __eq__(self, other):
            return (isinstance(other, CheckRunWindow.Window) and
                    self.start_time == other.start_time and
                    self.end_time == other.end_time and
                    str(self.recurrence.replace(dtstart=None)) == str(other.recurrence.replace(dtstart=None)))

        def __ne__(self, other):
            return not (self == other)

    def __init__(self, windows):
        # type: (List[Window]) -> None
        self.windows = windows

    def active(self, now=timezone.now()):
        return len(self.windows) == 0 or any([w.active(now) for w in self.windows])

    _TIME_FMT = '%H:%M'

    def serialize(self):
        # type: () -> unicode
        if len(self.windows) == 0:
            return u''
        data = [{
            'start_time': window.start_time.strftime(self._TIME_FMT),
            'end_time': window.end_time.strftime(self._TIME_FMT),
            'rrule': str(window.recurrence),
        } for window in self.windows]
        return json.dumps(data)

    @classmethod
    def deserialize(cls, data):
        # type: (unicode) -> CheckRunWindow
        if data is None:
            return cls([])

        if data == u'':
            return cls([])

        data = json.loads(data)
        return cls([cls.Window(
            timezone.datetime.strptime(w['start_time'], cls._TIME_FMT).time(),
            timezone.datetime.strptime(w['end_time'], cls._TIME_FMT).time(),
            rrule.rrulestr(w['rrule'])
        ) for w in data])

    @classmethod
    def validate(cls, value):
        # type: (unicode) -> List[str]
        """Returns a list of errors if value is not a valid serialized run window."""

        data = json.loads(value)
        if not isinstance(data, list):
            return ["Serialized run window should be list."]

        errors = []
        for w in data:
            try:
                timezone.datetime.strptime(w['start_time'], CheckRunWindow._TIME_FMT)
                timezone.datetime.strptime(w['end_time'], CheckRunWindow._TIME_FMT)
            except ValueError:
                errors.append("Invalid start/end time.")

            # ensure all windows have a valid recurrence rule
            try:
                rrule.rrulestr(w['rrule'])
            except ValueError as e:
                errors.append("You must select at least one day to run on. (" + str(e) + ").")
        return errors

    def __str__(self):
        return self.serialize()

    def __eq__(self, other):
        return isinstance(other, CheckRunWindow) and self.windows == other.windows

    def __ne__(self, other):
        return not (self == other)

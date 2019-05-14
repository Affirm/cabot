from django.db import models
from django.forms import Select
from django.utils import timezone


class PositiveIntegerMaxField(models.PositiveIntegerField):

    def __init__(self, verbose_name=None, name=None, max_value=None, **kwargs):
        self.max_value = max_value
        models.PositiveIntegerField.__init__(self, verbose_name, name, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'max_value': self.max_value}
        defaults.update(kwargs)
        return super(PositiveIntegerMaxField, self).formfield(**defaults)

    def deconstruct(self):
        name, path, args, kwargs = super(PositiveIntegerMaxField, self).deconstruct()
        kwargs["max_value"] = self.max_value
        return name, path, args, kwargs


class TimeFromNowField(Select):
    """DateTime field that lets the user choose from a predetermined set of times from now()"""
    def __init__(self, times, message_format=None, choices=None, *args, **kwargs):
        message_format = message_format or (lambda t: '{} hour{} from now'.format(t, 's' if t != 1 else ''))
        choices = choices or []
        choices += [(t, message_format(t)) for t in times]
        kwargs['choices'] = choices
        super(TimeFromNowField, self).__init__(*args, **kwargs)

    def value_from_datadict(self, data, files, name):
        value = data.get(name, '')
        choice_values = [c[0] for c in self.choices]
        if value in choice_values:
            return value

        try:
            hours = int(value)
        except ValueError:
            return 'invalid-datetime'

        if hours not in choice_values:
            return 'invalid-datetime'
        return timezone.now() + timezone.timedelta(hours=hours)

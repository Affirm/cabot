from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from cabot.cabotapp.run_window import CheckRunWindow


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


class CheckRunWindowWidget(forms.Widget):
    template_name = 'runwindow_form.html'

    def get_context(self, name, value, attrs):
        ctx = super(CheckRunWindowWidget, self).get_context(name, value, attrs)
        ctx['widget']['days_of_week'] = ['SU', 'MO', 'TU', 'WE', 'TH', 'FR', 'SA']
        return ctx

    def format_value(self, value):
        # type: (Optional[unicode]) -> unicode
        if value is None:
            return u''
        elif isinstance(value, unicode) or isinstance(value, str):
            return value
        elif isinstance(value, CheckRunWindow):
            return value.serialize()
        # django docs suck, not sure if this can even happen
        raise Exception('unknown value type ' + str(type(value)) + ' (' + repr(value) + ')')


class CheckRunWindowForm(forms.Field):
    widget = CheckRunWindowWidget

    def to_python(self, value):
        # type: (unicode) -> CheckRunWindow
        if isinstance(value, CheckRunWindow):
            return value
        if value:
            errors = CheckRunWindow.validate(value)
            if errors:
                raise ValidationError(errors)
        return CheckRunWindow.deserialize(value)

    def from_db_value(self, value, *args, **kwargs):
        # type: (Optional[unicode]) -> Optional[CheckRunWindow]
        if value is None:
            return None
        return self.to_python(value)


class CheckRunWindowField(models.Field):
    def __init__(self, *args, **kwargs):
        kwargs['blank'] = True
        kwargs['default'] = CheckRunWindow([])
        super(CheckRunWindowField, self).__init__(*args, **kwargs)

    def get_internal_type(self):
        return "TextField"

    def from_db_value(self, value, expression, connection, context):
        return self.to_python(value)

    def to_python(self, value):
        # type: (Union[None, unicode, CheckRunWindow]) -> Optional[CheckRunWindow]
        if value is None or isinstance(value, CheckRunWindow):
            return value
        return CheckRunWindow.deserialize(value)

    def get_prep_value(self, value):
        # type: (Optional[CheckRunWindow]) -> Optional[unicode]
        if value is None or isinstance(value, unicode) or isinstance(value, str):
            return value
        return value.serialize()

    def formfield(self, **kwargs):
        defaults = {
            'form_class': CheckRunWindowForm,
        }
        defaults.update(kwargs)
        return super(CheckRunWindowField, self).formfield(**defaults)


class TimeFromNowField(forms.Select):
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

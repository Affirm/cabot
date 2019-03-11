from django.db import models


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

import reversion
from django.contrib import admin
from .models import (
    UserProfile,
    Service,
    Shift,
    ServiceStatusSnapshot,
    StatusCheck,
    StatusCheckResult,
    ActivityCounter,
    Schedule,
    HipchatInstance,
    MatterMostInstance,
)
from .alert import AlertPluginUserData, AlertPlugin


class ServiceAdmin(reversion.VersionAdmin):
    pass


class StatusCheckAdmin(reversion.VersionAdmin):
    pass


admin.site.register(UserProfile)
admin.site.register(Shift)
admin.site.register(Service, ServiceAdmin)
admin.site.register(ServiceStatusSnapshot)
admin.site.register(StatusCheck, StatusCheckAdmin)
admin.site.register(StatusCheckResult)
admin.site.register(ActivityCounter)
admin.site.register(AlertPlugin)
admin.site.register(AlertPluginUserData)
admin.site.register(Schedule)
admin.site.register(HipchatInstance)
admin.site.register(MatterMostInstance)

from django.contrib import admin
from .models import *

@admin.register(AdSession)
class AdSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'ad', 'started_at', 'is_completed')
    list_filter = ('is_completed', 'started_at')
    search_fields = ('user__username', 'ad__title')
    readonly_fields = ('started_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'ad')

admin.site.register(Ad)
admin.site.register(AdView)
admin.site.register(UserEarning)
admin.site.register(AdProgress)
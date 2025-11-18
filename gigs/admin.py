from django.contrib import admin
from .models import *
# Register your models here.
admin.site.register(JobCategory)
admin.site.register(Job)
admin.site.register(ProofRequirement)
admin.site.register(JobSubmission)
admin.site.register(ProofSubmission)
admin.site.register(Transaction)

from django.db import models
import uuid
from django.utils import timezone
from django.conf import settings
from ckeditor.fields import RichTextField

class JobCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name_plural = "Job Categories"

    def __str__(self):
        return self.name

class Job(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(JobCategory, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    task_description = RichTextField(null=True, blank=True)
    note = RichTextField(blank=True, null=True)
    freelancers_needed = models.IntegerField(default=1)
    freelancers_completed = models.IntegerField(default=0)
    earning_per_task = models.DecimalField(max_digits=10, decimal_places=2)
    timeout_minutes = models.IntegerField(default=30)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_jobs')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    @property
    def is_available(self):
        return self.status == 'active' and self.freelancers_completed < self.freelancers_needed

class ProofRequirement(models.Model):
    PROOF_TYPE_CHOICES = (
        ('text', 'Text'),
        ('image', 'Image'),
    )

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='proof_requirements')
    title = models.CharField(max_length=255)
    proof_type = models.CharField(max_length=10, choices=PROOF_TYPE_CHOICES)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.job.title} - {self.title}"

class JobSubmission(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='submissions')
    freelancer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='job_submissions')
    partner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='partner_submissions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(blank=True)
    partner_earning = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    freelancer_earning = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        unique_together = ('job', 'freelancer')

    def __str__(self):
        return f"{self.job.title} - {self.freelancer.username}"

class ProofSubmission(models.Model):
    submission = models.ForeignKey(JobSubmission, on_delete=models.CASCADE, related_name='proofs')
    proof_requirement = models.ForeignKey(ProofRequirement, on_delete=models.CASCADE)
    text_content = models.TextField(blank=True)
    image = models.ImageField(upload_to='proof_images/', blank=True, null=True)

    def __str__(self):
        return f"{self.submission.id} - {self.proof_requirement.title}"

class Transaction(models.Model):
    TRANSACTION_TYPE_CHOICES = (
        ('earning', 'Earning'),
        ('withdrawal', 'Withdrawal'),
        ('commission', 'Commission'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255)
    job_submission = models.ForeignKey(JobSubmission, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} - {self.amount}"
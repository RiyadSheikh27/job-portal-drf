from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class Ad(models.Model):
    CATEGORY_CHOICES = (
        ("visit", "Visit Ad"),
        ("short", "Short Link"),
        ("video", "Video Ad"),
        ("offerwalla", "Offerwalls"),
        ("cpi", "CPI/CPS/CPL"),
    )
    TYPE_CHOICES = (
        ("url", "URL/LINK"),
        ("banner", "Banner/Image"),
        ("script", "Script/Code"),
        ("yt_link", "Youtube Embeded Link"),
    )
    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
    )

    title = models.CharField(max_length=255)
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=4)
    duration = models.PositiveIntegerField(help_text="Ad Duration in Seconds")
    max_show = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    note = models.TextField(blank=True, null=True)

    ad_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    ad_input_url = models.URLField(blank=True, null=True)
    ad_input_image = models.ImageField(upload_to="ads/image_ads", blank=True, null=True)
    ad_input_script = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Show title, category, status, and amount in admin
        return f"{self.title} | {self.category} | {self.status} | ${self.amount}"


class AdView(models.Model):
    """Final record after a user has completed viewing an ad."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ad = models.ForeignKey(Ad, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)  # store full datetime
    earned_amount = models.DecimalField(max_digits=10, decimal_places=4, default=0.0)

    def can_view_again(self):
        return self.viewed_at + timedelta(hours=24) < timezone.now()

    def __str__(self):
        # Show user, ad title, date, and earned amount
        return f"{self.user.username} | {self.ad.title} | Viewed: {self.viewed_at.strftime('%Y-%m-%d %H:%M')} | Earned: ${self.earned_amount}"


class AdProgress(models.Model):
    """Track when a user starts viewing an ad (used for duration validation)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ad = models.ForeignKey(Ad, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)

    def time_spent(self):
        return (timezone.now() - self.started_at).total_seconds()

    def __str__(self):
        # Show user, ad title, start time, and completion status
        status = "Completed" if self.completed else "In Progress"
        return f"{self.user.username} | {self.ad.title} | Started: {self.started_at.strftime('%Y-%m-%d %H:%M')} | {status}"


class UserEarning(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    total_earned = models.DecimalField(max_digits=12, decimal_places=4, default=0.0)
    today_earned = models.DecimalField(max_digits=12, decimal_places=4, default=0.0)
    last_updated = models.DateField(auto_now=True)

    def add_earning(self, amount):
        today = timezone.now().date()
        if self.last_updated != today:
            self.today_earned = 0.0
        self.total_earned += amount
        self.today_earned += amount
        self.save()

    def __str__(self):
        # Show username, total earned, and today earned
        return f"{self.user.username} | Total Earned: ${self.total_earned} | Today: ${self.today_earned}"

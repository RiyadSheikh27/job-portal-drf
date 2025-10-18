# views.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from rest_framework.permissions import AllowAny, IsAuthenticated
from accounts.models import User

from accounts import models
from .models import *
from .serializers import *
from accounts.permissions import IsAdmin, IsUser


class AdViewSet(viewsets.ModelViewSet):
    queryset = Ad.objects.all()
    serializer_class = AdSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdmin()]
        return []

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def user_ads(self, request):
        # ← CHANGED: Filter out ads that user has viewed in the last 24 hours
        # Get all active ads
        ads = Ad.objects.filter(status="active")

        # Get ads that the user viewed within the last 24 hours
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        recently_viewed_ad_ids = AdView.objects.filter(
            user=request.user, viewed_at__gte=twenty_four_hours_ago
        ).values_list("ad_id", flat=True)

        # Exclude recently viewed ads from the response
        ads = ads.exclude(id__in=recently_viewed_ad_ids)

        serializer = self.get_serializer(ads, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], permission_classes=[IsAdmin])
    def admin_stats(self, request):
        total_ads = Ad.objects.count()
        total_amount_allocated = Ad.objects.aggregate(total=Sum("amount"))["total"] or 0
        total_views = AdView.objects.count()
        total_amount_paid = (
            AdView.objects.aggregate(total=Sum("earned_amount"))["total"] or 0
        )
        return Response(
            {
                "total_ads": total_ads,
                "total_amount_allocated": total_amount_allocated,
                "total_views": total_views,
                "total_amount_paid": total_amount_paid,
            }
        )


class AdWatchingViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=True, methods=["post"])
    def start_view(self, request, pk=None):
        try:
            ad = Ad.objects.get(pk=pk, status="active")
        except Ad.DoesNotExist:
            return Response(
                {"success": "false", "error": "Ad not found or inactive"}, status=404
            )

        # ← CHANGED: Check if user has viewed this ad in the last 24 hours
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        recent_view = AdView.objects.filter(
            user=request.user, ad=ad, viewed_at__gte=twenty_four_hours_ago
        ).first()

        if recent_view:
            # Calculate remaining time until user can view this ad again
            can_view_at = recent_view.viewed_at + timedelta(hours=24)
            remaining_seconds = (can_view_at - timezone.now()).total_seconds()
            remaining_hours = int(remaining_seconds // 3600)
            remaining_minutes = int((remaining_seconds % 3600) // 60)
            return Response(
                {
                    "success": "false",
                    "error": f"You can view this ad again after {remaining_hours}h {remaining_minutes}m.",
                },
                status=400,
            )

        # Check 30-minute rate limit (10 ads per 30 minutes)
        thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
        recent_views = AdView.objects.filter(
            user=request.user, viewed_at__gte=thirty_minutes_ago
        ).count()

        if recent_views >= 10:
            oldest_recent = (
                AdView.objects.filter(
                    user=request.user, viewed_at__gte=thirty_minutes_ago
                )
                .order_by("viewed_at")
                .first()
            )
            if oldest_recent:
                next_available_time = oldest_recent.viewed_at + timedelta(minutes=30)
                remaining_seconds = (
                    next_available_time - timezone.now()
                ).total_seconds()
                remaining_minutes = int(remaining_seconds // 60)
                remaining_secs = int(remaining_seconds % 60)
                return Response(
                    {
                        "success": "false",
                        "error": f"You can watch more ads after {remaining_minutes}m {remaining_secs}s.",
                    },
                    status=400,
                )

        # ← REMOVED: Duplicate 24-hour check (already done above)
        # Store start time in session
        request.session[f"ad_{ad.id}_start"] = timezone.now().isoformat()
        return Response(
            {
                "success": "true",
                "message": "Ad view started. Please wait full duration.",
                "started_at": ad.created_at,
                "Duration": ad.duration,
            }
        )

    @action(detail=True, methods=["post"])
    def complete_view(self, request, pk=None):
        try:
            ad = Ad.objects.get(pk=pk, status="active")
        except Ad.DoesNotExist:
            return Response(
                {"success": "false", "error": "Ad not found or inactive"}, status=404
            )

        start_time = request.session.get(f"ad_{ad.id}_start")
        if not start_time:
            return Response(
                {"success": "false", "error": "You must start viewing first"},
                status=400,
            )

        start_time = timezone.datetime.fromisoformat(start_time)
        elapsed = (timezone.now() - start_time).total_seconds()

        if elapsed < ad.duration:
            return Response(
                {"success": "false", "error": "You must view the full duration"},
                status=400,
            )

        # ← CHANGED: Create AdView record (this automatically hides the ad for 24 hours)
        # When user completes viewing, create an AdView record
        # This record will be used to filter out this ad from user_ads endpoint for 24 hours
        ad_view = AdView.objects.create(
            user=request.user, ad=ad, earned_amount=ad.amount
        )

        earning, _ = UserEarning.objects.get_or_create(user=request.user)
        earning.add_earning(ad.amount)

        # Clear session data
        del request.session[f"ad_{ad.id}_start"]

        return Response(
            {
                "success": "true",
                "message": f"You earned {ad.amount} USD",
                "earned": ad.amount,
            }
        )


class UserEarningViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserEarningSerializer
    permission_classes = [IsUser]

    def get_queryset(self):
        return UserEarning.objects.filter(user=self.request.user)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("id")
    serializer_class = UserListSerializer
    permission_classes = [IsAdmin]

    @action(detail=False, methods=["get"], url_path="user-list")
    def user_list(self, request):
        users = self.get_queryset()
        serializer = self.get_serializer(users, many=True)
        return Response({"status": "success", "body": serializer.data})

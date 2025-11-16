#Project-1
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
from rest_framework.authentication import TokenAuthentication


class AdViewSet(viewsets.ModelViewSet):
    queryset = Ad.objects.all()
    serializer_class = AdSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [AllowAny()]
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
        return Response({
            "status": "success",
            "message": "User Ads fetched successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

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

        # ← CHANGED: Delete any incomplete sessions for this user and ad
        AdSession.objects.filter(
            user=request.user,
            ad=ad,
            is_completed=False
        ).delete()

        # ← CHANGED: Create new session in database (not in session storage)
        ad_session = AdSession.objects.create(
            user=request.user,
            ad=ad
        )

        return Response(
            {
                "success": "true",
                "message": "Ad view started. Please wait full duration.",
                "started_at": ad_session.started_at.isoformat(),
                "Duration": ad.duration,
                "session_id": ad_session.id  # ← Added for reference
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

        # ← CHANGED: Get session from database instead of Django session
        try:
            ad_session = AdSession.objects.get(
                user=request.user,
                ad=ad,
                is_completed=False
            )
        except AdSession.DoesNotExist:
            return Response(
                {"success": "false", "error": "You must start viewing first"},
                status=400,
            )

        # ← CHANGED: Calculate elapsed time from database record
        elapsed = ad_session.time_elapsed()

        if elapsed < ad.duration:
            return Response(
                {"success": "false", "error": "You must view the full duration"},
                status=400,
            )

        # Mark session as completed
        ad_session.is_completed = True
        ad_session.save()

        # Create AdView record (this automatically hides the ad for 24 hours)
        ad_view = AdView.objects.create(
            user=request.user, ad=ad, earned_amount=ad.amount
        )

        earning, _ = UserEarning.objects.get_or_create(user=request.user)
        earning.add_earning(ad.amount)

        return Response(
            {
                "success": "true",
                "message": f"You earned {ad.amount} USD",
                "earned": ad.amount,
            }
        )

    # Keep your api_complete method as is for third-party platforms
    @action(
        detail=True,
        methods=["post"],
        url_path="api_complete",
        authentication_classes=[TokenAuthentication],
        permission_classes=[IsAuthenticated]
    )
    def api_complete(self, request, pk=None):
        """
        Complete ad view via API (for third-party platforms like Project 2)
        This doesn't require session, uses token authentication
        """
        try:
            ad = Ad.objects.get(pk=pk, status="active")
        except Ad.DoesNotExist:
            return Response(
                {"success": "false", "error": "Ad not found or inactive"},
                status=404
            )

        # Get validation data from request body
        started_at_str = request.data.get('started_at')
        duration_watched = request.data.get('duration_watched', 0)

        if not started_at_str:
            return Response(
                {"success": "false", "error": "started_at timestamp is required"},
                status=400
            )

        # Validate the timestamp format
        try:
            started_at = timezone.datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return Response(
                {"success": "false", "error": "Invalid started_at format. Use ISO format."},
                status=400
            )

        # Calculate elapsed time
        elapsed = (timezone.now() - started_at).total_seconds()

        # Validate duration (use provided duration_watched or calculated elapsed)
        actual_duration = max(duration_watched, elapsed)

        if actual_duration < ad.duration:
            return Response(
                {
                    "success": "false",
                    "error": f"You must view the ad for at least {ad.duration} seconds. Watched: {int(actual_duration)}s"
                },
                status=400
            )

        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        recent_view = AdView.objects.filter(
            user=request.user,
            ad=ad,
            viewed_at__gte=twenty_four_hours_ago
        ).first()

        if recent_view:
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

        thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
        recent_views = AdView.objects.filter(
            user=request.user,
            viewed_at__gte=thirty_minutes_ago
        ).count()

        if recent_views >= 10:
            oldest_recent = (
                AdView.objects.filter(
                    user=request.user,
                    viewed_at__gte=thirty_minutes_ago
                )
                .order_by("viewed_at")
                .first()
            )
            if oldest_recent:
                next_available_time = oldest_recent.viewed_at + timedelta(minutes=30)
                remaining_seconds = (next_available_time - timezone.now()).total_seconds()
                remaining_minutes = int(remaining_seconds // 60)
                remaining_secs = int(remaining_seconds % 60)
                return Response(
                    {
                        "success": "false",
                        "error": f"You can watch more ads after {remaining_minutes}m {remaining_secs}s.",
                    },
                    status=400,
                )

        # All validations passed - Create AdView record
        ad_view = AdView.objects.create(
            user=request.user,
            ad=ad,
            earned_amount=ad.amount
        )

        # Credit user's earnings
        earning, _ = UserEarning.objects.get_or_create(user=request.user)
        earning.add_earning(ad.amount)

        return Response({
            "success": "true",
            "message": f"You earned {ad.amount} USD",
            "earned": str(ad.amount),
            "ad_title": ad.title,
            "ad_id": ad.id
        })


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


#===================================================================================
                                # """ Third Party """
#===================================================================================
class ThirdPartyAdWatchingViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=True, methods=["post"])
    def start_view(self, request, pk=None):
        try:
            ad = Ad.objects.get(pk=pk, status="active")
        except Ad.DoesNotExist:
            return Response(
                {"success": "false", "error": "Ad not found or inactive"}, status=404
            )

        # ← CHANGED: Delete any incomplete sessions for this user and ad
        AdSession.objects.filter(
            user=request.user,
            ad=ad,
            is_completed=False
        ).delete()

        # ← CHANGED: Create new session in database (not in session storage)
        ad_session = AdSession.objects.create(
            user=request.user,
            ad=ad
        )

        return Response(
            {
                "success": "true",
                "message": "Ad view started. Please wait full duration.",
                "started_at": ad_session.started_at.isoformat(),
                "Duration": ad.duration,
                "session_id": ad_session.id
            }
        )

    def api_complete(self, request, pk=None):
        """
        Complete ad view via API (for third-party platforms like Project 2)
        This doesn't require session, uses token authentication
        """
        try:
            ad = Ad.objects.get(pk=pk, status="active")
        except Ad.DoesNotExist:
            return Response(
                {"success": "false", "error": "Ad not found or inactive"},
                status=404
            )

        # Get validation data from request body
        started_at_str = request.data.get('started_at')
        duration_watched = request.data.get('duration_watched', 0)

        if not started_at_str:
            return Response(
                {"success": "false", "error": "started_at timestamp is required"},
                status=400
            )

        # Validate the timestamp format
        try:
            started_at = timezone.datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return Response(
                {"success": "false", "error": "Invalid started_at format. Use ISO format."},
                status=400
            )

        # Calculate elapsed time
        elapsed = (timezone.now() - started_at).total_seconds()

        # Validate duration (use provided duration_watched or calculated elapsed)
        actual_duration = max(duration_watched, elapsed)

        if actual_duration < ad.duration:
            return Response(
                {
                    "success": "false",
                    "error": f"You must view the ad for at least {ad.duration} seconds. Watched: {int(actual_duration)}s"
                },
                status=400
            )
        
        ad_view = AdView.objects.create(
            user=request.user,
            ad=ad,
            earned_amount=ad.amount
        )

        # Credit user's earnings
        earning, _ = UserEarning.objects.get_or_create(user=request.user)
        earning.add_earning(ad.amount)

        return Response({
            "success": "true",
            "message": f"You earned {ad.amount} USD",
            "earned": str(ad.amount),
            "ad_title": ad.title,
            "ad_id": ad.id
        })


class ThirdPartyAdViewSet(viewsets.ModelViewSet):
    queryset = Ad.objects.all()
    serializer_class = AdSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [AllowAny()]
        return []

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def user_ads(self, request):
        ads = Ad.objects.filter(status="active")

        serializer = self.get_serializer(ads, many=True)
        return Response({
            "status": "success",
            "message": "User Ads fetched successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

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
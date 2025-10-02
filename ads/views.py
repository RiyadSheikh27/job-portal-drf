from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from rest_framework.permissions import AllowAny, IsAuthenticated

from accounts import models
from .models import Ad, AdView, UserEarning
from .serializers import AdSerializer, AdViewSerializer, UserEarningSerializer
from accounts.permissions import IsAdmin, IsUser


class AdViewSet(viewsets.ModelViewSet):
    queryset = Ad.objects.all()
    serializer_class = AdSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdmin()]
        return []

    # User dashboard: only active ads
    @action(detail=False, methods=["get"], permission_classes=[IsUser])
    def user_ads(self, request):
        ads = Ad.objects.filter(status="active")
        serializer = self.get_serializer(ads, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAdmin])
    def admin_stats(self, request):
        total_ads = Ad.objects.count()
        total_amount_allocated = Ad.objects.aggregate(total=Sum('amount'))['total'] or 0
        total_views = AdView.objects.count()
        total_amount_paid = AdView.objects.aggregate(total=Sum('earned_amount'))['total'] or 0

        return Response({
            "total_ads": total_ads,
            "total_amount_allocated": total_amount_allocated,
            "total_views": total_views,
            "total_amount_paid": total_amount_paid
        })


class AdWatchingViewSet(viewsets.ViewSet):
    """
    Handles watching ads and rewarding users
    """

    permission_classes = [AllowAny]

    @action(detail=True, methods=["post"])
    def start_view(self, request, pk=None):
        try:
            ad = Ad.objects.get(pk=pk, status="active")
        except Ad.DoesNotExist:
            return Response({"error": "Ad not found or inactive"}, status=404)

        # check if user already viewed in last 24h
        last_view = (
            AdView.objects.filter(user=request.user, ad=ad)
            .order_by("-viewed_at")
            .first()
        )
        if last_view and not last_view.can_view_again():
            return Response(
                {"error": "You can view this ad again after 24 hours"}, status=400
            )

        # start session
        request.session[f"ad_{ad.id}_start"] = timezone.now().isoformat()
        return Response({"message": "Ad view started. Please wait full duration."})

    @action(detail=True, methods=["post"])
    def complete_view(self, request, pk=None):
        try:
            ad = Ad.objects.get(pk=pk, status="active")
        except Ad.DoesNotExist:
            return Response({"error": "Ad not found or inactive"}, status=404)

        start_time = request.session.get(f"ad_{ad.id}_start")
        if not start_time:
            return Response({"error": "You must start viewing first"}, status=400)

        start_time = timezone.datetime.fromisoformat(start_time)
        elapsed = (timezone.now() - start_time).total_seconds()

        if elapsed < ad.duration:
            return Response({"error": "You must view the full duration"}, status=400)

        # Save AdView
        ad_view = AdView.objects.create(
            user=request.user, ad=ad, earned_amount=ad.amount
        )

        # Update UserEarning
        earning, _ = UserEarning.objects.get_or_create(user=request.user)
        earning.add_earning(ad.amount)

        return Response({"message": f"You earned {ad.amount} USD", "earned": ad.amount})


class UserEarningViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserEarningSerializer
    permission_classes = [IsUser]

    def get_queryset(self):
        return UserEarning.objects.filter(user=self.request.user)

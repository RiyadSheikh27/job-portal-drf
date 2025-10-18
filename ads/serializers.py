# serializers.py (No changes needed)
from rest_framework import serializers
from .models import *
from accounts.models import *

class AdSerializer(serializers.ModelSerializer):
      class Meta:
            model = Ad
            fields = "__all__"

class AdViewSerializer(serializers.ModelSerializer):
      ad = AdSerializer(read_only = True)

      class Meta:
            model = AdView
            fields = ["id", "ad", "viewed_at", "earned_amount"]

class UserEarningSerializer(serializers.ModelSerializer):
      class Meta:
            model = UserEarning
            fields = ["total_earned", "today_earned", "last_updated"]


class UserListSerializer(serializers.ModelSerializer):
    today_earned = serializers.SerializerMethodField()
    total_earned = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'today_earned', 'total_earned']

    def get_today_earned(self, obj):
        earning = UserEarning.objects.filter(user=obj).first()
        return earning.today_earned if earning else 0.0

    def get_total_earned(self, obj):
        earning = UserEarning.objects.filter(user=obj).first()
        return earning.total_earned if earning else 0.0
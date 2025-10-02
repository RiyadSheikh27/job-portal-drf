from rest_framework import serializers
from .models import *

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


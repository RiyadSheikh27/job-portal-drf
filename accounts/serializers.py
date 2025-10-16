from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from .models import User

class RegisterSerializer(serializers.ModelSerializer):
    password1 = serializers.CharField(write_only=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']  # ❌ role বাদ
        extra_kwargs = {
            "username": {"required": True},
            "email": {"required": True}
        }

    def validate(self, attrs):
        if attrs['password1'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Passwords must match."})
        return attrs

    def create(self, validated_data):
        # role এখানে view থেকে আসবে
        role = self.context.get("role", "user")
        username = validated_data['username']
        email = validated_data['email']
        password = validated_data['password1']

        user = User.objects.create_user(
            email=email,
            username=username,
            role=role,
            password=password
        )
        Token.objects.create(user=user)
        return user



class LoginSerializer(serializers.Serializer):
    role = serializers.CharField(write_only=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")
        role = data.get("role")

        user = authenticate(email=email, password=password)

        if user and user.is_active:
            if user.role != role:   # 🚨 role check
                raise serializers.ValidationError("Role does not match this account.")
            return user
        raise serializers.ValidationError("Invalid Credentials")


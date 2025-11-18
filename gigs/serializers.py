from rest_framework import serializers
from .models import *
from django.conf import settings
from accounts.models import User

class ProofRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProofRequirement
        fields = ['id', 'title', 'proof_type', 'order']


class JobCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = JobCategory
        fields = ['id', 'name', 'slug', 'created_at']


class JobSerializer(serializers.ModelSerializer):
    proof_requirements = ProofRequirementSerializer(many=True, read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Job
        fields = [
            'id', 'category', 'category_name', 'title', 'task_description',
            'note', 'freelancers_needed', 'freelancers_completed',
            'earning_per_task', 'timeout_minutes', 'status',
            'proof_requirements', 'created_at', 'is_available'
        ]
        read_only_fields = ['id', 'freelancers_completed', 'created_at']


class JobCreateSerializer(serializers.ModelSerializer):
    proof_requirements = serializers.ListField(
        child=serializers.DictField(), write_only=True
    )

    class Meta:
        model = Job
        fields = [
            'category', 'title', 'task_description', 'note',
            'freelancers_needed', 'earning_per_task', 'timeout_minutes',
            'proof_requirements'
        ]

    def create(self, validated_data):
        proof_requirements_data = validated_data.pop('proof_requirements', [])
        job = Job.objects.create(**validated_data)

        for idx, proof_data in enumerate(proof_requirements_data):
            ProofRequirement.objects.create(
                job=job,
                title=proof_data['title'],
                proof_type=proof_data['proof_type'],
                order=idx
            )

        return job


class ProofSubmissionSerializer(serializers.ModelSerializer):
    proof_requirement_title = serializers.CharField(source='proof_requirement.title', read_only=True)
    proof_requirement_type = serializers.CharField(source='proof_requirement.proof_type', read_only=True)

    class Meta:
        model = ProofSubmission
        fields = ['id', 'proof_requirement', 'proof_requirement_title', 'proof_requirement_type', 'text_content', 'image']


class JobSubmissionSerializer(serializers.ModelSerializer):
    proofs = ProofSubmissionSerializer(many=True, read_only=True)
    job_title = serializers.CharField(source='job.title', read_only=True)
    freelancer_username = serializers.CharField(source='freelancer.username', read_only=True)

    class Meta:
        model = JobSubmission
        fields = [
            'id', 'job', 'job_title', 'freelancer', 'freelancer_username',
            'status', 'submitted_at', 'reviewed_at', 'admin_note',
            'partner_earning', 'freelancer_earning', 'proofs'
        ]
        read_only_fields = ['id', 'submitted_at', 'reviewed_at']


class JobSubmissionCreateSerializer(serializers.ModelSerializer):
    proofs = serializers.ListField(child=serializers.DictField(), write_only=True)

    class Meta:
        model = JobSubmission
        fields = ['job', 'proofs']

    def validate_job(self, value):
        if not value.is_available:
            raise serializers.ValidationError("This job is no longer available.")
        return value

    def validate(self, data):
        job = data['job']
        freelancer = self.context['request'].user

        if JobSubmission.objects.filter(job=job, freelancer=freelancer).exists():
            raise serializers.ValidationError("You have already submitted this job.")

        return data

    def create(self, validated_data):
        proofs_data = validated_data.pop('proofs')
        request = self.context['request']

        # Get partner from API token if exists
        partner = None
        api_token = request.headers.get('X-API-Token')
        if api_token:
            partner = settings.AUTH_USER_MODEL.objects.filter(api_token=api_token, user_type='partner').first()

        # Calculate earnings
        job = validated_data['job']
        if partner:
            partner_earning = job.earning_per_task
            freelancer_earning = job.earning_per_task / 2
        else:
            partner_earning = 0
            freelancer_earning = job.earning_per_task

        submission = JobSubmission.objects.create(
            job=job,
            freelancer=request.user,
            partner=partner,
            partner_earning=partner_earning,
            freelancer_earning=freelancer_earning,
            **validated_data
        )

        for proof_data in proofs_data:
            ProofSubmission.objects.create(
                submission=submission,
                proof_requirement_id=proof_data['proof_requirement_id'],
                text_content=proof_data.get('text_content', ''),
                image=proof_data.get('image')
            )

        return submission


class UserSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()
    api_token = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'balance', 'api_token']
        read_only_fields = ['id', 'api_token']


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'transaction_type', 'amount', 'description', 'created_at']
        read_only_fields = ['id', 'created_at']

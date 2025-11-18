from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from accounts.permissions import IsUser, IsAdmin
from django.utils import timezone
from django.db import transaction as db_transaction
from django.conf import settings
from .models import *
from .serializers import *

class StandardResponse:
    @staticmethod
    def success(message, data=None):
        return Response({
            'success': True,
            'message': message,
            'data': data
        }, status=status.HTTP_200_OK)

    @staticmethod
    def created(message, data=None):
        return Response({
            'success': True,
            'message': message,
            'data': data
        }, status=status.HTTP_201_CREATED)

    @staticmethod
    def error(message, data=None, status_code=status.HTTP_400_BAD_REQUEST):
        return Response({
            'success': False,
            'message': message,
            'data': data
        }, status=status_code)


class JobCategoryViewSet(viewsets.ModelViewSet):
    queryset = JobCategory.objects.all()
    serializer_class = JobCategorySerializer
    permission_classes = [IsAuthenticated]

    def list(self, request):
        categories = self.get_queryset()
        serializer = self.get_serializer(categories, many=True)
        return StandardResponse.success("Categories retrieved successfully", serializer.data)

    def create(self, request):
        if not request.user.is_staff:
            return StandardResponse.error("Only admin can create categories", status_code=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return StandardResponse.created("Category created successfully", serializer.data)
        return StandardResponse.error("Validation failed", serializer.errors)


class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return JobCreateSerializer
        return JobSerializer

    def get_queryset(self):
        queryset = Job.objects.select_related('category').prefetch_related('proof_requirements')

        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        # For partners, show only active and available jobs
        api_token = self.request.headers.get('X-API-Token')
        if api_token:
            queryset = queryset.filter(status='active', freelancers_completed__lt=models.F('freelancers_needed'))

        return queryset

    def list(self, request):
        jobs = self.get_queryset()
        serializer = self.get_serializer(jobs, many=True)
        return StandardResponse.success("Jobs retrieved successfully", serializer.data)

    def retrieve(self, request, pk=None):
        try:
            job = self.get_queryset().get(pk=pk)
            serializer = self.get_serializer(job)
            return StandardResponse.success("Job details retrieved successfully", serializer.data)
        except Job.DoesNotExist:
            return StandardResponse.error("Job not found", status_code=status.HTTP_404_NOT_FOUND)

    def create(self, request):
        if not request.user.is_staff:
            return StandardResponse.error("Only admin can create jobs", status_code=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return StandardResponse.created("Job created successfully", serializer.data)
        return StandardResponse.error("Validation failed", serializer.errors)

    def update(self, request, pk=None):
        if not request.user.is_staff:
            return StandardResponse.error("Only admin can update jobs", status_code=status.HTTP_403_FORBIDDEN)

        try:
            job = self.get_queryset().get(pk=pk)
        except Job.DoesNotExist:
            return StandardResponse.error("Job not found", status_code=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(job, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return StandardResponse.success("Job updated successfully", serializer.data)
        return StandardResponse.error("Validation failed", serializer.errors)

    def destroy(self, request, pk=None):
        if not request.user.is_staff:
            return StandardResponse.error("Only admin can delete jobs", status_code=status.HTTP_403_FORBIDDEN)

        try:
            job = self.get_queryset().get(pk=pk)
            job.delete()
            return StandardResponse.success("Job deleted successfully")
        except Job.DoesNotExist:
            return StandardResponse.error("Job not found", status_code=status.HTTP_404_NOT_FOUND)


class JobSubmissionViewSet(viewsets.ModelViewSet):
    queryset = JobSubmission.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return JobSubmissionCreateSerializer
        return JobSubmissionSerializer

    def get_queryset(self):
        queryset = JobSubmission.objects.select_related('job', 'freelancer', 'partner').prefetch_related('proofs')

        if self.request.user.is_staff:
            return queryset

        # Partners see submissions from their users
        if self.request.user.user_type == 'partner':
            return queryset.filter(partner=self.request.user)

        # Freelancers see only their submissions
        return queryset.filter(freelancer=self.request.user)

    def list(self, request):
        submissions = self.get_queryset()

        # Filter by status
        status_param = request.query_params.get('status')
        if status_param:
            submissions = submissions.filter(status=status_param)

        serializer = self.get_serializer(submissions, many=True)
        return StandardResponse.success("Submissions retrieved successfully", serializer.data)

    def retrieve(self, request, pk=None):
        try:
            submission = self.get_queryset().get(pk=pk)
            serializer = self.get_serializer(submission)
            return StandardResponse.success("Submission details retrieved successfully", serializer.data)
        except JobSubmission.DoesNotExist:
            return StandardResponse.error("Submission not found", status_code=status.HTTP_404_NOT_FOUND)

    def create(self, request):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return StandardResponse.created("Job submitted successfully. Waiting for admin approval.", serializer.data)
        return StandardResponse.error("Validation failed", serializer.errors)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        try:
            submission = self.get_queryset().get(pk=pk)
        except JobSubmission.DoesNotExist:
            return StandardResponse.error("Submission not found", status_code=status.HTTP_404_NOT_FOUND)

        if submission.status != 'pending':
            return StandardResponse.error("Submission already reviewed")

        with db_transaction.atomic():
            submission.status = 'approved'
            submission.reviewed_at = timezone.now()
            submission.save()

            # Update job completed count
            job = submission.job
            job.freelancers_completed += 1
            if job.freelancers_completed >= job.freelancers_needed:
                job.status = 'completed'
            job.save()

            # Add earnings to freelancer
            freelancer = submission.freelancer
            freelancer.balance += submission.freelancer_earning
            freelancer.save()

            Transaction.objects.create(
                user=freelancer,
                transaction_type='earning',
                amount=submission.freelancer_earning,
                description=f"Earning from job: {job.title}",
                job_submission=submission
            )

            # Add commission to partner if exists
            if submission.partner:
                partner = submission.partner
                partner.balance += submission.partner_earning
                partner.save()

                Transaction.objects.create(
                    user=partner,
                    transaction_type='commission',
                    amount=submission.partner_earning,
                    description=f"Commission from job: {job.title}",
                    job_submission=submission
                )

        serializer = self.get_serializer(submission)
        return StandardResponse.success("Submission approved successfully", serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        try:
            submission = self.get_queryset().get(pk=pk)
        except JobSubmission.DoesNotExist:
            return StandardResponse.error("Submission not found", status_code=status.HTTP_404_NOT_FOUND)

        if submission.status != 'pending':
            return StandardResponse.error("Submission already reviewed")

        submission.status = 'rejected'
        submission.reviewed_at = timezone.now()
        submission.admin_note = request.data.get('admin_note', '')
        submission.save()

        serializer = self.get_serializer(submission)
        return StandardResponse.success("Submission rejected successfully", serializer.data)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return StandardResponse.success("User profile retrieved successfully", serializer.data)

    @action(detail=False, methods=['post'])
    def register_partner(self, request):
        """Allow admins to register partner accounts"""
        if not request.user.is_staff:
            return StandardResponse.error("Only admin can register partners", status_code=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        data['user_type'] = 'partner'

        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            user.set_password(data.get('password'))
            user.save()
            return StandardResponse.created("Partner registered successfully", serializer.data)
        return StandardResponse.error("Validation failed", serializer.errors)


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user).order_by('-created_at')

    def list(self, request):
        transactions = self.get_queryset()
        serializer = self.get_serializer(transactions, many=True)
        return StandardResponse.success("Transactions retrieved successfully", serializer.data)


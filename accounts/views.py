from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import filters, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from accounts.models import User
from accounts.serializers import CustomUserSerializer



from rest_framework import generics, status, views
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.db import transaction
from .models import User, OTP
from .serializers import UserSerializer
from hotel.permissions import IsHotelAdmin
import re
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken


class CustomTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            user = User.objects.get(email=request.data['email'])
            response.data['user'] = UserSerializer(user).data
        return response

class LogoutView(views.APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        try:
            refresh_token = request.data["refresh_token"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class UsernameSuggestionView(views.APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        hotel_name = request.query_params.get('hotel_name', '')
        if not hotel_name:
            return Response({'error': 'hotel_name query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Generate base usernames
        base_name = re.sub(r'[^a-zA-Z0-9]', '', hotel_name).lower()
        suggestions = [
            f"{base_name}",
            f"{base_name}admin",
            f"{base_name}_admin",
        ]

        # Generate additional suggestions with random numbers
        while len(suggestions) < 5:
            random_suffix = get_random_string(length=3, allowed_chars='1234567890')
            new_suggestion = f"{base_name}{random_suffix}"
            if new_suggestion not in suggestions:
                suggestions.append(new_suggestion)

        # Check for uniqueness and add more if needed
        final_suggestions = []
        for username in suggestions:
            if not User.objects.filter(username=username).exists():
                final_suggestions.append(username)

        while len(final_suggestions) < 5:
            random_suffix = get_random_string(length=4, allowed_chars='1234567890')
            new_suggestion = f"{base_name}{random_suffix}"
            if new_suggestion not in final_suggestions and not User.objects.filter(username=new_suggestion).exists():
                final_suggestions.append(new_suggestion)

        return Response({'suggestions': final_suggestions[:5]}, status=status.HTTP_200_OK)


class HotelRegistrationView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        request.data['user_type'] = 'hotel_admin'
        hotel_name = request.data.get('hotel_name')
        if not hotel_name:
            return Response({'error': 'Hotel name is required.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                user = serializer.save()

                # Send OTP
                otp_code = get_random_string(length=6, allowed_chars='1234567890')
                otp = OTP.objects.create(user=user, otp=otp_code)

                send_mail(
                    'Your OTP for LobbyBee',
                    f'Your OTP is: {otp.otp}',
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
        except Exception as e:
            print(f"Failed during hotel registration: {e}")
            return Response(
                {'error': 'An unexpected error occurred during registration. Could not send verification email.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({'message': 'Hotel registration initiated. Please verify your email.'}, status=status.HTTP_201_CREATED)

class HotelStaffRegistrationView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated, IsHotelAdmin]
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        # Set the hotel and created_by fields
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save(
            hotel=request.user.hotel,
            created_by=request.user,
            is_verified=True  # No email verification needed for staff
        )
        return Response({'message': 'Staff user created successfully'}, status=status.HTTP_201_CREATED)

class VerifyOTPView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        otp_code = request.data.get('otp')

        try:
            user = User.objects.get(email=email)
            otp = OTP.objects.get(user=user, otp=otp_code)

            if otp.is_expired():
                return Response({'error': 'OTP has expired.'}, status=status.HTTP_400_BAD_REQUEST)

            user.is_verified = True
            user.save()
            otp.delete()

            return Response({'message': 'Email verified successfully.','data':user.email}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        except OTP.DoesNotExist:
            return Response({'error': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)

class ResendOTPView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            otp = OTP.objects.get(user=user)

            if otp.resend_attempts >= 5:
                return Response({'error': 'You have reached the maximum number of OTP resend attempts.'}, status=status.HTTP_400_BAD_REQUEST)

            # Generate a new OTP
            new_otp_code = get_random_string(length=6, allowed_chars='1234567890')
            otp.otp = new_otp_code
            otp.resend_attempts += 1
            otp.created_at = timezone.now()
            otp.save()

            # Send the new OTP
            send_mail(
                'Your New OTP for LobbyBee',
                f'Your new OTP is: {new_otp_code}',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )

            return Response({'message': 'A new OTP has been sent to your email.'}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        except OTP.DoesNotExist:
            return Response({'error': 'No OTP found for this user. Please register first.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Failed to resend OTP: {e}")
            return Response(
                {'error': 'An unexpected error occurred. Could not resend OTP.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

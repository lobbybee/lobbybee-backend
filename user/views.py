from rest_framework import generics, status, views, viewsets, serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from lobbybee.utils.responses import success_response, error_response, created_response, not_found_response, forbidden_response
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, OTP
from .serializers import UserSerializer
from hotel.permissions import IsHotelAdmin, CanCreateReceptionist
from .permissions import IsSuperUser, IsPlatformAdmin, IsPlatformStaff
from hotel.models import Hotel
from hotel.serializers import UserHotelSerializer
import re
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import MyTokenObtainPairSerializer, ChangePasswordSerializer


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

class PlatformUserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer

    def get_queryset(self):
        return User.objects.filter(user_type__in=['platform_admin', 'platform_staff'])

    def get_permissions(self):
        if self.action == 'create':
            self.permission_classes = [IsSuperUser | IsPlatformAdmin]
        else:
            self.permission_classes = [IsAuthenticated, IsSuperUser | IsPlatformAdmin]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        print(f"DEBUG: PlatformUserViewSet.create called")
        print(f"DEBUG: Request user: {request.user.username}")
        print(f"DEBUG: Request user is_superuser: {request.user.is_superuser}")
        print(f"DEBUG: Request user user_type: {request.user.user_type}")
        print(f"DEBUG: Request data: {request.data}")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        user_type = serializer.validated_data.get('user_type')
        request_user = self.request.user

        # Debug logging
        print(f"DEBUG: Request user: {request_user.username}")
        print(f"DEBUG: Request user is_superuser: {request_user.is_superuser}")
        print(f"DEBUG: Request user user_type: {request_user.user_type}")
        print(f"DEBUG: Creating user_type: {user_type}")

        # Superusers can create both platform_admin and platform_staff
        if request_user.is_superuser and user_type in ['platform_admin', 'platform_staff']:
            serializer.save(is_staff=True, is_verified=True, created_by=request_user)
        # Platform admins can only create platform_staff
        elif request_user.user_type == 'platform_admin' and user_type == 'platform_staff':
            serializer.save(is_staff=True, is_verified=True, created_by=request_user)
        else:
            raise serializers.ValidationError("You do not have permission to create this type of user.")

class LogoutView(views.APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return error_response(
                "Refresh token is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return success_response(message="Successfully logged out", status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return error_response(
                "Invalid refresh token",
                status=status.HTTP_400_BAD_REQUEST
            )


class UsernameSuggestionView(views.APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        try:
            hotel_name = request.query_params.get('hotel_name', '')
            if not hotel_name:
                return error_response('hotel_name query parameter is required.', status=status.HTTP_400_BAD_REQUEST)

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

            return success_response(data={'suggestions': final_suggestions[:5]})
        except Exception as e:
            return error_response(f"Failed to generate username suggestions: {str(e)}", status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class HotelRegistrationView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        request.data['user_type'] = 'hotel_admin'
        hotel_name = request.data.get('hotel_name')
        if not hotel_name:
            return error_response('Hotel name is required.', status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                hotel = Hotel.objects.create(
                    name=hotel_name,
                    email=request.data.get('email'),
                    phone=request.data.get('phone_number', '')
                )
                user = serializer.save(hotel=hotel)

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
            return error_response(
                'An unexpected error occurred during registration. Could not send verification email.',
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return created_response(message='Hotel registration initiated. Please verify your email.')

class PlatformCreateHotelView(generics.CreateAPIView):
    """
    An endpoint for platform users to create a new hotel and its admin user.
    The hotel is created with is_verified=True but status='pending'.
    The admin user is created as verified, skipping OTP.
    """
    permission_classes = [IsAuthenticated, IsSuperUser | IsPlatformAdmin | IsPlatformStaff]
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        request.data['user_type'] = 'hotel_admin'
        hotel_name = request.data.get('hotel_name')
        if not hotel_name:
            return error_response('Hotel name is required.', status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                # Create the hotel with is_verified=True but status='pending'
                hotel = Hotel.objects.create(
                    name=hotel_name,
                    email=request.data.get('email'),
                    phone=request.data.get('phone_number', ''),
                    is_verified=True,
                    status='pending'
                )
                # Create the user and mark them as verified, skipping OTP
                user = serializer.save(hotel=hotel, is_verified=True, created_by=request.user)

        except Exception as e:
            # It's good practice to log the exception
            print(f"Failed during platform hotel creation: {e}")
            return error_response(
                'An unexpected error occurred during hotel creation.',
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        user_data = serializer.data
        user_data['hotel_id'] = hotel.id
        user_data['hotel_name'] = hotel.name

        return created_response(data={
            'message': 'Hotel and admin user created successfully.',
            'data': user_data
        })

class HotelStaffRegistrationView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated, IsHotelAdmin]
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        data = request.data
        
        try:
            # Check if incoming data is a list for bulk creation
            if isinstance(data, list):
                serializer = self.get_serializer(data=data, many=True)
                serializer.is_valid(raise_exception=True)
                
                # Create all staff members with hotel, created_by, and is_verified=True
                created_staff = []
                for item in serializer.validated_data:
                    user = serializer.Meta.model.objects.create_user(
                        username=item['username'],
                        email=item['email'],
                        password=item['password'],
                        user_type=item['user_type'],
                        phone_number=item.get('phone_number', ''),
                        department=item.get('department'),
                        hotel=request.user.hotel,
                        created_by=request.user,
                        is_verified=True,
                        is_active_hotel_user=True
                    )
                    created_staff.append(user)
                
                return created_response(
                    message=f'{len(created_staff)} staff users created successfully'
                )
            
            # Single staff creation (old format)
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            user = serializer.save(
                hotel=request.user.hotel,
                created_by=request.user,
                is_verified=True  # No email verification needed for staff
            )
            return created_response(message='Staff user created successfully')
        except Exception as e:
            return error_response(f"Failed to create hotel staff: {str(e)}", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VerifyOTPView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        otp_code = request.data.get('otp')

        try:
            user = User.objects.get(email=email)
            otp = OTP.objects.get(user=user, otp=otp_code)

            if otp.is_expired():
                return error_response('OTP has expired.', status=status.HTTP_400_BAD_REQUEST)

            user.is_verified = True
            user.save()
            otp.delete()

            return success_response(message='Email verified successfully.', data={'email': user.email})

        except User.DoesNotExist:
            return not_found_response('User not found.')
        except OTP.DoesNotExist:
            return error_response('Invalid OTP.', status=status.HTTP_400_BAD_REQUEST)

class ResendOTPView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        if not email:
            return error_response('Email is required.', status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            otp = OTP.objects.get(user=user)

            if otp.resend_attempts >= 5:
                return error_response('You have reached the maximum number of OTP resend attempts.', status=status.HTTP_400_BAD_REQUEST)

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

            return success_response(message='A new OTP has been sent to your email.')

        except User.DoesNotExist:
            return not_found_response('User not found.')
        except OTP.DoesNotExist:
            return not_found_response('No OTP found for this user. Please register first.')
        except Exception as e:
            print(f"Failed to resend OTP: {e}")
            return error_response(
                'An unexpected error occurred. Could not resend OTP.',
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PasswordResetRequestView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        if not email:
            return error_response('Email is required.', status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal that the user doesn't exist to prevent user enumeration attacks
            return success_response(message='If an account with that email exists, a password reset OTP has been sent.')

        otp_code = get_random_string(length=6, allowed_chars='1234567890')
        
        # Use update_or_create to handle existing OTP for a user
        otp, created = OTP.objects.update_or_create(
            user=user,
            defaults={'otp': otp_code, 'created_at': timezone.now(), 'resend_attempts': 0}
        )

        try:
            send_mail(
                'Your Password Reset OTP for LobbyBee',
                f'Your password reset OTP is: {otp_code}',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Failed to send password reset OTP: {e}")
            return error_response(
                'An unexpected error occurred. Could not send OTP.',
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return success_response(message='If an account with that email exists, a password reset OTP has been sent.')


class PasswordResetConfirmView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        otp_code = request.data.get('otp')
        new_password = request.data.get('new_password')

        if not all([email, otp_code, new_password]):
            return error_response('Email, OTP, and new password are required.', status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            otp = OTP.objects.get(user=user, otp=otp_code)

            if otp.is_expired():
                return error_response('OTP has expired.', status=status.HTTP_400_BAD_REQUEST)
            
            try:
                validate_password(new_password, user)
            except ValidationError as e:
                return error_response(errors=list(e.messages), status=status.HTTP_400_BAD_REQUEST)

            user.set_password(new_password)
            user.save()
            otp.delete()

            return success_response(message='Password has been reset successfully.')

        except User.DoesNotExist:
            return error_response('Invalid email or OTP.', status=status.HTTP_400_BAD_REQUEST)
        except OTP.DoesNotExist:
            return error_response('Invalid email or OTP.', status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(views.APIView):
    permission_classes = [IsAuthenticated, IsHotelAdmin]

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        return success_response(message="Password updated successfully")


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'hotel_admin':
            return User.objects.filter(hotel=user.hotel)
        return User.objects.none() # Superadmins can see all users, but for now, only hotel admins can see their hotel's users.

    def perform_create(self, serializer):
        serializer.save(
            hotel=self.request.user.hotel,
            created_by=self.request.user,
            is_verified=True
        )

    def create(self, request, *args, **kwargs):
        data = request.data
        
        # Check if incoming data is a list for bulk creation
        if isinstance(data, list):
            try:
                serializer = self.get_serializer(data=data, many=True)
                serializer.is_valid(raise_exception=True)
                
                # Create all users with hotel, created_by, and is_verified=True
                created_users = []
                for item in serializer.validated_data:
                    user = User.objects.create_user(
                        username=item['username'],
                        email=item['email'],
                        password=item['password'],
                        user_type=item['user_type'],
                        phone_number=item.get('phone_number', ''),
                        department=item.get('department'),
                        hotel=request.user.hotel,
                        created_by=request.user,
                        is_verified=True,
                        is_active_hotel_user=item.get('is_active_hotel_user', True)
                    )
                    created_users.append(user)
                
                # Serialize the created users for the response
                response_serializer = self.get_serializer(created_users, many=True)
                headers = self.get_success_headers(response_serializer.data)
                return created_response(data=response_serializer.data)
            except Exception as e:
                return error_response(f"Failed to bulk create users: {str(e)}", status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Default behavior for single user creation
        return super().create(request, *args, **kwargs)

    def get_permissions(self):
        if self.action == 'create':
            # Check if the request is to create a 'receptionist'
            # Handle both single object and list (bulk creation)
            data = self.request.data
            if isinstance(data, list):
                # Check if any item in the bulk creation is a receptionist
                is_receptionist_creation = any(item.get('user_type') == 'receptionist' for item in data)
            else:
                is_receptionist_creation = data.get('user_type') == 'receptionist'
            
            if is_receptionist_creation:
                permission_classes = [IsAuthenticated, CanCreateReceptionist]
            else:
                # For creating other user types, only hotel_admin is allowed
                permission_classes = [IsAuthenticated, IsHotelAdmin]
        elif self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated, IsHotelAdmin]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsHotelAdmin]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

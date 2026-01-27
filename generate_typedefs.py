
import os
import django
import sys
import inspect
import json
from rest_framework.permissions import AllowAny, IsAuthenticated

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lobbybee.settings')
django.setup()

from django.conf import settings
from django.urls import URLPattern, URLResolver
from django.apps import apps
from rest_framework.views import APIView
from rest_framework.serializers import Serializer, ListSerializer
from rest_framework.fields import (
    CharField, IntegerField, BooleanField, FloatField, 
    DateField, DateTimeField, ChoiceField, FileField, 
    SerializerMethodField, JSONField
)

# Try to import custom permissions to map them
try:
    from user.permissions import (
        IsSuperUser, IsPlatformAdmin, IsPlatformStaff, 
        IsHotelAdmin, IsSuperUserOrPlatformStaff, 
        IsHotelManagerOrAdmin, IsHotelStaffOrAdmin
    )
    from hotel.permissions import CanCreateReceptionist, CanManagePaymentQRCode
except ImportError:
    # Fallback if imports fail
    IsSuperUser = 'IsSuperUser'
    IsPlatformAdmin = 'IsPlatformAdmin'
    IsPlatformStaff = 'IsPlatformStaff'
    IsHotelAdmin = 'IsHotelAdmin'
    IsSuperUserOrPlatformStaff = 'IsSuperUserOrPlatformStaff'
    IsHotelManagerOrAdmin = 'IsHotelManagerOrAdmin'
    IsHotelStaffOrAdmin = 'IsHotelStaffOrAdmin'
    CanCreateReceptionist = 'CanCreateReceptionist'
    CanManagePaymentQRCode = 'CanManagePaymentQRCode'


TYPE_MAPPING = {
    CharField: 'string',
    IntegerField: 'integer',
    BooleanField: 'boolean',
    FloatField: 'float',
    DateField: 'date (ISO 8601)',
    DateTimeField: 'datetime (ISO 8601)',
    ChoiceField: 'enum',
    FileField: 'file',
    JSONField: 'json/object',
}

PERMISSION_MAPPING = {
    AllowAny: "Public",
    IsAuthenticated: "Authenticated Users",
    IsSuperUser: "Super User",
    IsPlatformAdmin: "Platform Admin",
    IsPlatformStaff: "Platform Staff",
    IsHotelAdmin: "Hotel Admin",
    IsSuperUserOrPlatformStaff: "Super User | Platform Staff",
    IsHotelManagerOrAdmin: "Hotel Admin | Manager",
    IsHotelStaffOrAdmin: "Hotel Admin | Manager | Receptionist",
    CanCreateReceptionist: "Can Create Receptionist",
    CanManagePaymentQRCode: "Can Manage Payment QRCode"
}

def get_field_type(field):
    if isinstance(field, ListSerializer):
        return f"Array[{get_serializer_structure(field.child)}]"
    if isinstance(field, Serializer):
        return get_serializer_structure(field)
    
    for field_class, type_name in TYPE_MAPPING.items():
        if isinstance(field, field_class):
            return type_name
    return 'string' # Default fallback

def get_serializer_structure(serializer):
    structure = {}
    if not hasattr(serializer, 'get_fields'):
        return str(serializer)
    
    for name, field in serializer.get_fields().items():
        field_type = get_field_type(field)
        required = getattr(field, 'required', False)
        help_text = getattr(field, 'help_text', '')
        
        structure[name] = {
            'type': field_type,
            'required': required,
        }
        if help_text:
            structure[name]['description'] = str(help_text)
            
    return structure

def format_structure(structure, indent=0):
    output = ""
    prefix = "  " * indent
    if isinstance(structure, dict):
        output += "{\n"
        for key, value in structure.items():
            if isinstance(value, dict) and 'type' in value:
                # Leaf node
                req = "*" if value.get('required') else ""
                desc = f" // {value['description']}" if 'description' in value else ""
                val_type = value['type']
                if isinstance(val_type, dict):
                     # Nested serializer
                     nested = format_structure(val_type, indent + 1)
                     output += f"{prefix}  {key}{req}: {nested.strip()}{desc}\n"
                else:
                    output += f"{prefix}  {key}{req}: {val_type}{desc}\n"
            else:
                 # Should not happen really with get_serializer_structure logic but for safety
                 output += f"{prefix}  {key}: {value}\n"
        output += f"{prefix}}}"
    else:
        output += str(structure)
    return output

def get_permissions_info(view_class):
    permissions = getattr(view_class, 'permission_classes', [])
    if not permissions:
         return "Unknown / Default"
    
    perm_names = []
    for perm in permissions:
        # Handle OR/AND composition (simple heuristic)
        # DRF 3.9+ supports | and & operators which create OperandHolder
        
        name = PERMISSION_MAPPING.get(perm, getattr(perm, '__name__', str(perm)))
        perm_names.append(name)
        
    return ", ".join(perm_names)
    


# Manual overrides for views that don't user serializer_class or use it dynamically
MANUAL_DEFINITIONS = {
    'VerifyOTPView': {
        'POST': {
            'email': {'type': 'string', 'required': True},
            'otp': {'type': 'string', 'required': True}
        }
    },
    'ResendOTPView': {
        'POST': {
            'email': {'type': 'string', 'required': True}
        }
    },
    'UsernameSuggestionView': {
        'GET': {
            'hotel_name': {'type': 'string', 'required': True, 'description': 'Query Parameter'}
        }
    },
    'LogoutView': {
        'POST': {
            'refresh': {'type': 'string', 'required': True}
        }
    },
    'PasswordResetRequestView': {
        'POST': {
            'email': {'type': 'string', 'required': True}
        }
    },
    'PasswordResetConfirmView': {
        'POST': {
            'email': {'type': 'string', 'required': True},
            'otp': {'type': 'string', 'required': True},
            'new_password': {'type': 'string', 'required': True}
        }
    },
    'ChangePasswordView': {
        'POST': {
            'old_password': {'type': 'string', 'required': True},
            'new_password': {'type': 'string', 'required': True}
        }
    },
    'TokenRefreshView': {
        'POST': {
            'refresh': {'type': 'string', 'required': True}
        }
    },
    'HotelStatsViewSet': {
        'list': {
            'type': 'array',
            'items': {
                'id': {'type': 'string'},
                'name': {'type': 'string'},
                'city': {'type': 'string'},
                'status': {'type': 'string'}
            }
        },
        'retrieve': {
            'type': 'object',
            'description': 'Returns stats based on stat_type param (overview, occupancy, guests, rooms, staff, performance)'
        }
    },
    'HotelUserStatsViewSet': {
        'list': {
             'description': 'Overview stats for user hotel',
             'type': 'object'
        },
        'occupancy': {
             'description': 'Occupancy stats',
             'type': 'object'
        },
        'guests': {
             'description': 'Guest stats',
             'type': 'object'
        },
        'rooms': {
             'description': 'Room stats',
             'type': 'object'
        },
        'staff': {
             'description': 'Staff stats',
             'type': 'object'
        },
        'performance': {
             'description': 'Performance stats',
             'type': 'object'
        },
        'guest_history': {
             'description': 'Guest history',
             'type': 'object'
        },
        'room_history': {
             'description': 'Room history',
             'type': 'object'
        },
        'conversation_history': {
             'description': 'Conversation history',
             'type': 'object'
        }
    },

    'PlatformStatsViewSet': {
         'list': {
             'description': 'Platform overview stats',
             'type': 'object'
         }
    },
    'HotelComparisonView': {
         'GET': {
             'description': 'Compare hotels',
             'type': 'object'
         }
    },
    'send_typing_indicator': {
         'POST': {
             'conversation_id': {'type': 'integer', 'required': True}
         }
    },
    'template_types_view': {
         'GET': {
             'type': 'array',
             'description': 'List of available template types'
         }
    },
    'render_template_preview': {
         'GET': {
             'description': 'Preview rendered template with variables',
             'type': 'object'
         }
    },
    'template_variables_view': {
         'GET': {
             'description': 'List of available template variables',
             'type': 'object'
         }
    }
}

# Mapping for ViewSets that use get_serializer_class or dynamic serializers
# Format: 'ViewName': {'METHOD': SerializerClass} or 'ViewName': SerializerClass (applies to all methods)
# If mapping to a dict, keys can be METHOD (GET, POST etc) or Action Name (create, list etc)
VIEW_SERIALIZER_MAPPING = {}

try:
    from hotel.serializers import (
        HotelSerializer, UserHotelSerializer, AdminHotelUpdateSerializer, 
        AdminHotelDocumentUpdateSerializer, RoomSerializer, RoomStatusUpdateSerializer,
        HotelDocumentSerializer
    )
    from guest.serializers import (
        CreateGuestSerializer, GuestResponseSerializer, BookingListSerializer,
        CheckinOfflineSerializer, VerifyCheckinSerializer, StayListSerializer,
        CheckoutSerializer, ExtendStaySerializer
    )
    from notifications.serializers import NotificationSerializer, NotificationCreateSerializer
    
    VIEW_SERIALIZER_MAPPING.update({
        'HotelViewSet': {
            'list': UserHotelSerializer,
            'retrieve': UserHotelSerializer, 
            'create': HotelSerializer, 
            'update': HotelSerializer,
            'partial_update': HotelSerializer
        },
        'AdminHotelViewSet': {
             'list': HotelSerializer,
             'retrieve': HotelSerializer,
             'create': HotelSerializer,
             'update': AdminHotelUpdateSerializer,
             'partial_update': AdminHotelUpdateSerializer
        },
        'AdminHotelDocumentViewSet': {
            'list': HotelDocumentSerializer,
            'retrieve': HotelDocumentSerializer,
            'create': HotelDocumentSerializer,
            'update': AdminHotelDocumentUpdateSerializer,
            'partial_update': AdminHotelDocumentUpdateSerializer
        },
        'RoomViewSet': {
             'GET': RoomSerializer,
             'POST': RoomSerializer,
             'PATCH': RoomStatusUpdateSerializer, 
             'PUT': RoomSerializer
        },
        'GuestManagementViewSet': {
             'create_guest': CreateGuestSerializer,
             'list_guests': GuestResponseSerializer,
             'list_bookings': BookingListSerializer,
        },
        'StayManagementViewSet': {
             'checkin_offline': CheckinOfflineSerializer,
             'verify_checkin': VerifyCheckinSerializer,
             'pending_stays': StayListSerializer, 
             'checked_in_users': StayListSerializer,
             'checkout_user': CheckoutSerializer,
             'extend_stay': ExtendStaySerializer
        },
        'NotificationViewSet': {
            'GET': NotificationSerializer,
            'POST': NotificationCreateSerializer,
            'PUT': NotificationSerializer,
            'PATCH': NotificationSerializer
        },
        # Manual mapped in MANUAL_DEFINITIONS but need to ensure they are picked up
        'HotelStatsViewSet': {},
        'HotelUserStatsViewSet': {},
        'PlatformStatsViewSet': {},
        'HotelComparisonView': {},
        # FBVs needs to be present here too to be picked up if they appear as patterns
        'send_typing_indicator': {},
        'template_types_view': {},
        'render_template_preview': {},
        'template_variables_view': {}
    })
except ImportError:
    pass

def inspect_urlpatterns(urlpatterns, prefix=''):
    endpoints = []
    for pattern in urlpatterns:
        if isinstance(pattern, URLResolver):
            # Recurse
            endpoints.extend(inspect_urlpatterns(pattern.url_patterns, prefix + str(pattern.pattern)))
        elif isinstance(pattern, URLPattern):
            full_path = prefix + str(pattern.pattern)
            callback = pattern.callback
            
            # Handle Class-based views
            if hasattr(callback, 'cls'): 
                view_class = callback.cls
                view_name = view_class.__name__
                actions = getattr(callback, 'actions', None) # For ViewSets
                
                # Check for serializer_class
                serializer_class = getattr(view_class, 'serializer_class', None)
                permissions_info = get_permissions_info(view_class)

                method_serializers = {}
                allowed_methods = view_class.http_method_names
                
                if actions:
                    # ViewSet
                    for method, action in actions.items():
                        mapping_found = False
                        # Check MANUAL mapping first
                        if view_name in VIEW_SERIALIZER_MAPPING:
                            mapping = VIEW_SERIALIZER_MAPPING[view_name]
                            if(view_name == 'GuestManagementViewSet' or view_name == 'StayManagementViewSet'):
                                print(f"DEBUG: Mapping found for {view_name}. Action: {action}")
                            
                            if isinstance(mapping, dict):
                                # Try to match by action name first, then method
                                if action in mapping:
                                    method_serializers[method.upper()] = mapping[action]
                                    mapping_found = True
                                    if(view_name == 'GuestManagementViewSet'): print(f"DEBUG: Mapped {action} to {mapping[action]}")
                                elif method.upper() in mapping:
                                    method_serializers[method.upper()] = mapping[method.upper()]
                                    mapping_found = True
                            else:
                                method_serializers[method.upper()] = mapping
                                mapping_found = True
                        
                        if not mapping_found:
                             method_serializers[method.upper()] = serializer_class
                else:
                    # APIView / GenericAPIView
                    for method in allowed_methods:
                        if method.upper() in ['GET', 'POST', 'PUT', 'PATCH']:
                             # Check MANUAL mapping
                            mapping_found = False
                            if view_name in VIEW_SERIALIZER_MAPPING:
                                mapping = VIEW_SERIALIZER_MAPPING[view_name]
                                if isinstance(mapping, dict) and method.upper() in mapping:
                                     method_serializers[method.upper()] = mapping[method.upper()]
                                     mapping_found = True
                                elif not isinstance(mapping, dict):
                                     method_serializers[method.upper()] = mapping
                                     mapping_found = True
                            
                            if not mapping_found:
                                method_serializers[method.upper()] = serializer_class

                endpoints.append({
                    'path': full_path,
                    'view': view_name,
                    'serializers': method_serializers,
                    'permissions': permissions_info,
                    'manual_def': MANUAL_DEFINITIONS.get(view_name)
                })
            # Handle Function-based views (FBVs)
            elif callable(callback) and hasattr(callback, '__name__'):
                view_name = callback.__name__
                # Check if we have a manual definition for this FBV
                if view_name in MANUAL_DEFINITIONS:
                    endpoints.append({
                        'path': full_path,
                        'view': view_name,
                        'serializers': {method: None for method in MANUAL_DEFINITIONS[view_name].keys()}, # Placeholder
                        'permissions': 'Unknown / Manual',
                        'manual_def': MANUAL_DEFINITIONS.get(view_name)
                    })
               
    return endpoints

def generate_markdown():
    from django.urls import get_resolver
    resolver = get_resolver()
    endpoints = inspect_urlpatterns(resolver.url_patterns)
    
    general_file = open('TypeDef.md', 'w')
    platform_file = open('PlatformTypeDef.md', 'w')
    hotel_file = open('HotelTypeDef.md', 'w')
    
    general_file.write("# General API Type Definitions\n\nAuto-generated definitions for Public/Unknown routes.\n\n")
    platform_file.write("# Platform API Type Definitions\n\nAuto-generated definitions for Platform Admin/Staff routes.\n\n")
    hotel_file.write("# Hotel API Type Definitions\n\nAuto-generated definitions for Hotel Admin/Staff routes.\n\n")
    
    # Permission keywords
    platform_keywords = [
        'Super User', 'Platform Admin', 'Platform Staff'
    ]
    
    hotel_keywords = [
        'Hotel Admin', 'Manager', 'Receptionist', 'Can Create Receptionist', 'Can Manage Payment QRCode', 'IsHotelStaff', 'IsSameHotelUser'
    ]

    for endpoint in endpoints:
        
        # Prepare definitions map: definition_string -> [list of methods]
        definitions_map = {}
        undefined_methods = []
        
        manual_defs = endpoint.get('manual_def', {})
        
        has_any_definition = False
        
        for method, serializer_class in endpoint['serializers'].items():
            definition_content = None
            def_source = ""
            
            if manual_defs and method in manual_defs:
                definition_content = format_structure(manual_defs[method])
                def_source = "Manual Definition"
            elif serializer_class:
                try:
                    serializer_instance = serializer_class()
                    structure = get_serializer_structure(serializer_instance)
                    definition_content = format_structure(structure)
                    def_source = f"Serializer: `{serializer_class.__name__}`"
                except Exception:
                    # Failed to instantiate, treat as undefined
                    pass

            if definition_content:
                has_any_definition = True
                key = (def_source, definition_content)
                if key not in definitions_map:
                    definitions_map[key] = []
                definitions_map[key].append(method)
            else:
                undefined_methods.append(method)
        
        if not has_any_definition:
            continue

        permissions = endpoint['permissions']
        path = endpoint['path']
        
        # Categorize
        is_platform = '/admin/' in path or '/admin_stat/' in path or any(keyword in permissions for keyword in platform_keywords)
        is_hotel = any(keyword in permissions for keyword in hotel_keywords)
        is_general_auth = 'Authenticated Users' in permissions and not is_platform
        is_public = 'Public' in permissions or 'Unknown' in permissions or 'Default' in permissions
        
        if is_platform:
            target_file = platform_file
        elif is_hotel or is_general_auth:
            target_file = hotel_file
        else:
            target_file = general_file
        
        target_file.write(f"## Endpoint: `/{endpoint['path']}`\n")
        target_file.write(f"**View**: `{endpoint['view']}`\n")
        target_file.write(f"**Permissions**: {endpoint['permissions']}\n\n")
        
        # Print grouped definitions
        for (source, content), methods in definitions_map.items():
            methods_str = ", ".join(sorted(methods))
            target_file.write(f"### {methods_str}\n")
            if "Serializer" in source:
                 target_file.write(f"**{source}**\n")
            else:
                 target_file.write(f"**{source}**\n")
            
            target_file.write("```json\n")
            target_file.write(content + "\n")
            target_file.write("```\n\n")
            
        target_file.write("---\n\n")

    general_file.close()
    platform_file.close()
    hotel_file.close()

if __name__ == "__main__":
    generate_markdown()

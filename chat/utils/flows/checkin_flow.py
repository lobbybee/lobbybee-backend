from typing import Dict, Any, Optional, Tuple, List, Union
from enum import Enum
import json
import re
from datetime import datetime
from guest.models import Guest, Stay, GuestIdentityDocument
from ..adhaar import decode_aadhaar_qr_from_image

class ResponseType(Enum):
    TEXT = "text"
    BUTTONS = "buttons"
    LIST = "list"

class CheckinResponse:
    """Represents a check-in flow response with different types"""
    def __init__(self, response_type: ResponseType, text: str, options: List[str] = None):
        self.response_type = response_type
        self.text = text
        self.options = options or []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary format"""
        result = {
            "response_type": self.response_type.value,
            "text": self.text
        }
        if self.options:
            result["options"] = self.options
        return result

class CheckinFlow:
    def __init__(self):
        self.flow_id = None
        self.current_step = None
        self.flow_data = {}
        self.document_types = {
            'aadhar_id': 'AADHAR ID',
            'pan_id': 'PAN ID',  # Not in model but commonly requested
            'driving_license': 'Driving License',
            'national_id': 'National ID',
            'voter_id': 'Voter ID'
        }
    
    def get_phone_number_message(self) -> CheckinResponse:
        """Get message for phone number collection"""
        return CheckinResponse(
            response_type=ResponseType.TEXT,
            text="🏨 Welcome to our hotel check-in service! To get started, please provide your phone number."
        )
    
    def validate_phone_number(self, phone_input: str) -> Tuple[bool, str, Optional[Guest]]:
        """Validate phone number and check if guest exists"""
        # Clean phone number
        phone_clean = re.sub(r'[^\d+]', '', phone_input.strip())
        
        # Basic validation
        if len(phone_clean) < 10:
            return False, "Please provide a valid phone number (at least 10 digits)", None
        
        # Try to find existing guest
        try:
            guest = Guest.objects.filter(whatsapp_number=phone_clean).first()
            return True, "Phone number received", guest
        except Exception as e:
            return True, "Phone number received", None
    
    def get_existing_customer_confirmation(self, guest: Guest) -> CheckinResponse:
        """Get confirmation message for existing customer with their data"""
        # Get guest's active stay if any
        active_stay = Stay.objects.filter(guest=guest, status='pending').first()
        
        guest_info = f"📋 **Your Information:**\n"
        guest_info += f"• Name: {guest.full_name or 'Not provided'}\n"
        guest_info += f"• Email: {guest.email or 'Not provided'}\n"
        guest_info += f"• Phone: {guest.whatsapp_number}\n"
        
        if active_stay:
            guest_info += f"• Room: {active_stay.room.room_number}\n"
            guest_info += f"• Check-in: {active_stay.check_in_date.strftime('%Y-%m-%d %H:%M')}\n"
            guest_info += f"• Check-out: {active_stay.check_out_date.strftime('%Y-%m-%d %H:%M')}\n"
        
        guest_info += f"\nIs this information correct?"
        
        return CheckinResponse(
            response_type=ResponseType.BUTTONS,
            text=guest_info,
            options=["Yes, this is correct", "No, I need to update information"]
        )
    
    def get_id_type_selection(self) -> CheckinResponse:
        """Get message for ID document type selection"""
        return CheckinResponse(
            response_type=ResponseType.LIST,
            text="📄 To complete your check-in, I need to verify your identity. Please select the type of ID document you'd like to upload:",
            options=list(self.document_types.values())
        )
    
    def get_id_upload_instructions(self, doc_type: str) -> CheckinResponse:
        """Get instructions for uploading ID document"""
        if doc_type == "AADHAR ID":
            return CheckinResponse(
                response_type=ResponseType.TEXT,
                text=f"📸 Please upload a clear photo of your {doc_type}.\n\nFor best results:\n• Ensure good lighting\n• Place on a flat surface\n• All text should be clearly visible\n• Avoid glare and shadows\n• 📱 **IMPORTANT: Keep the QR code portion clear and visible**\n• Make sure the QR code is not blurry or cut off\n\nPlease upload the front side first (the side with the QR code)."
            )
        else:
            return CheckinResponse(
                response_type=ResponseType.TEXT,
                text=f"📸 Please upload a clear photo of your {doc_type}.\n\nFor best results:\n• Ensure good lighting\n• Place on a flat surface\n• All text should be clearly visible\n• Avoid glare and shadows\n\nPlease upload the front side first."
            )
    
    def get_id_back_upload_instructions(self, doc_type: str) -> CheckinResponse:
        """Get instructions for uploading back side of ID"""
        if doc_type == "AADHAR ID":
            return CheckinResponse(
                response_type=ResponseType.TEXT,
                text=f"📸 Now please upload the back side of your {doc_type}.\n\nNote: Some AADHAR cards have QR codes on both sides - please ensure the QR code is clear and visible on this side too.\n\nIf your AADHAR doesn't have a QR code on the back, please upload the back side anyway for complete verification."
            )
        else:
            return CheckinResponse(
                response_type=ResponseType.TEXT,
                text=f"📸 Now please upload the back side of your {doc_type}.\n\nNote: For PAN ID, just upload the same image again as it doesn't have a back side."
            )
    
    def get_additional_info_request(self, doc_type: str) -> CheckinResponse:
        """Get message for additional information collection (non-AADHAR)"""
        return CheckinResponse(
            response_type=ResponseType.TEXT,
            text=f"📝 For {doc_type} verification, I need some additional information.\n\nPlease provide:\n1. Your full name as shown on ID\n2. Date of birth (DD/MM/YYYY)\n3. Complete address\n\nYou can send this information in one message, separated by commas or new lines."
        )
    
    def get_aadhar_confirmation(self, extracted_data: Dict[str, Any]) -> CheckinResponse:
        """Get confirmation message for AADHAR verification"""
        confirmation_text = f"📋 **AADHAR Information Extracted:**\n"
        confirmation_text += f"• Name: {extracted_data.get('name', 'Not detected')}\n"
        confirmation_text += f"• DOB: {extracted_data.get('dob', 'Not detected')}\n"
        confirmation_text += f"• Address: {extracted_data.get('address', 'Not detected')}\n\n"
        confirmation_text += "Is this information correct?"
        
        return CheckinResponse(
            response_type=ResponseType.BUTTONS,
            text=confirmation_text,
            options=["Yes, this is correct", "No, I need to correct it"]
        )
    
    def get_new_customer_welcome(self) -> CheckinResponse:
        """Get welcome message for new customer"""
        return CheckinResponse(
            response_type=ResponseType.TEXT,
            text="Welcome! I don't see any existing reservation with this phone number. Let's help you check in. What's your full name?"
        )
    
    def process_phone_input(self, phone_input: str) -> Tuple[bool, str, str, Dict[str, Any]]:
        """Process phone number input and determine next step"""
        is_valid, message, guest = self.validate_phone_number(phone_input)
        
        if not is_valid:
            return False, message, "phone_validation", {}
        
        # Store phone in flow data
        flow_data = {"phone": phone_input}
        
        if guest:
            # Existing customer
            flow_data["guest_id"] = guest.id
            flow_data["is_existing_customer"] = True
            return True, message, "existing_customer_confirmation", flow_data
        else:
            # New customer - start ID verification process
            flow_data["is_existing_customer"] = False
            return True, message, "id_type_selection", flow_data
    
    def process_existing_customer_response(self, response: str, flow_data: Dict[str, Any]) -> Tuple[bool, str, str, Dict[str, Any]]:
        """Process existing customer confirmation response"""
        response_lower = response.strip().lower()
        
        if response_lower in ["yes", "1", "correct", "confirm"]:
            # Confirm existing data - proceed with check-in
            guest_id = flow_data.get("guest_id")
            if guest_id:
                try:
                    guest = Guest.objects.get(id=guest_id)
                    # Here you would typically trigger the actual check-in process
                    return True, "✅ Perfect! Your check-in is confirmed. Welcome to our hotel!", "checkin_complete", flow_data
                except Guest.DoesNotExist:
                    return False, "❌ Error: Guest record not found. Please start over.", "phone_validation", {}
            else:
                return False, "❌ Error: Guest information not found. Please start over.", "phone_validation", {}
        else:
            # Need to update information
            return True, "Let's update your information. What's your full name?", "update_name", flow_data
    
    def process_id_type_selection(self, user_input: str, flow_data: Dict[str, Any]) -> Tuple[bool, str, str, Dict[str, Any]]:
        """Process ID type selection"""
        # Map user input to document type key
        selected_type = None
        for key, value in self.document_types.items():
            if user_input.strip().lower() == value.lower():
                selected_type = key
                break
        
        if not selected_type:
            # Try partial matching
            user_lower = user_input.strip().lower()
            for key, value in self.document_types.items():
                if user_lower in value.lower() or value.lower() in user_lower:
                    selected_type = key
                    break
        
        if not selected_type:
            return False, "Please select a valid ID type from the list provided.", "id_type_selection", flow_data
        
        # Store selected document type
        flow_data["selected_document_type"] = selected_type
        flow_data["selected_document_name"] = self.document_types[selected_type]
        
        return True, f"ID type selected: {self.document_types[selected_type]}", "id_front_upload", flow_data
    
    def process_additional_info(self, user_input: str, flow_data: Dict[str, Any]) -> Tuple[bool, str, str, Dict[str, Any]]:
        """Process additional information for non-AADHAR IDs"""
        try:
            # Parse user input for name, DOB, address
            parts = user_input.split(',')
            if len(parts) < 3:
                # Try new lines as separators
                parts = user_input.split('\n')
            
            if len(parts) < 3:
                return False, "Please provide all three pieces of information: name, date of birth (DD/MM/YYYY), and address. Separate with commas or new lines.", "additional_info_collection", flow_data
            
            name = parts[0].strip()
            dob = parts[1].strip()
            address = parts[2].strip()
            
            # Validate DOB format
            if not re.match(r'^\d{2}/\d{2}/\d{4}$', dob):
                return False, "Please provide date of birth in DD/MM/YYYY format.", "additional_info_collection", flow_data
            
            # Store parsed information
            flow_data["name"] = name
            flow_data["date_of_birth"] = dob
            flow_data["address"] = address
            
            # Generate confirmation message
            confirmation_text = f"📋 **Information Provided:**\n"
            confirmation_text += f"• Name: {name}\n"
            confirmation_text += f"• Date of Birth: {dob}\n"
            confirmation_text += f"• Address: {address}\n\n"
            confirmation_text += "Is this information correct?"
            
            return True, "Information received successfully", "additional_info_confirmation", flow_data
            
        except Exception as e:
            return False, "Error processing your information. Please try again with the format: Name, DD/MM/YYYY, Address", "additional_info_collection", flow_data
    
    def process_aadhar_qr_extraction(self, front_image_data: bytes, back_image_data: bytes) -> Dict[str, Any]:
        """Process AADHAR QR extraction using both sides of the ID"""
        # Try front side first
        front_result = decode_aadhaar_qr_from_image(front_image_data)
        if front_result:
            return {
                "success": True,
                "data": front_result,
                "source": "front"
            }
        
        # Try back side
        back_result = decode_aadhaar_qr_from_image(back_image_data)
        if back_result:
            return {
                "success": True,
                "data": back_result,
                "source": "back"
            }
        
        # Both sides failed
        return {
            "success": False,
            "data": None,
            "source": None
        }
    
    def format_aadhar_data_for_display(self, aadhar_data: dict) -> Dict[str, Any]:
        """Format AADHAR data for user confirmation"""
        formatted_data = {}
        
        # Map AADHAR fields to display format
        if "name" in aadhar_data:
            formatted_data["name"] = aadhar_data["name"].title()
        else:
            formatted_data["name"] = aadhar_data.get("full_name", "Not detected").title()
        
        if "dob" in aadhar_data:
            formatted_data["dob"] = aadhar_data["dob"]
        else:
            formatted_data["dob"] = aadhar_data.get("date_of_birth", "Not detected")
        
        if "address" in aadhar_data:
            formatted_data["address"] = aadhar_data["address"]
        elif "care_of" in aadhar_data and "house" in aadhar_data:
            # Format address from individual components
            address_parts = []
            if aadhar_data.get("house"):
                address_parts.append(aadhar_data["house"])
            if aadhar_data.get("street"):
                address_parts.append(aadhar_data["street"])
            if aadhar_data.get("landmark"):
                address_parts.append(aadhar_data["landmark"])
            if aadhar_data.get("post_office"):
                address_parts.append(aadhar_data["post_office"])
            if aadhar_data.get("dist"):
                address_parts.append(aadhar_data["dist"])
            if aadhar_data.get("state"):
                address_parts.append(aadhar_data["state"])
            if aadhar_data.get("pc"):
                address_parts.append(f"PIN: {aadhar_data['pc']}")
            
            formatted_data["address"] = ", ".join(address_parts) if address_parts else "Not detected"
        else:
            formatted_data["address"] = "Not detected"
        
        return formatted_data
    
    def process_aadhar_verification(self, flow_data: Dict[str, Any]) -> Tuple[bool, str, str, Dict[str, Any]]:
        """Process AADHAR verification after both sides are uploaded"""
        front_image_data = flow_data.get("id_front_image")
        back_image_data = flow_data.get("id_back_image")
        
        if not front_image_data or not back_image_data:
            return False, "Both sides of AADHAR ID are required for verification.", "id_back_upload", flow_data
        
        # Try to extract QR data from both sides
        extraction_result = self.process_aadhar_qr_extraction(front_image_data, back_image_data)
        
        if extraction_result["success"]:
            # QR extraction successful
            formatted_data = self.format_aadhar_data_for_display(extraction_result["data"])
            flow_data["extracted_aadhar_info"] = formatted_data
            
            return True, f"AADHAR information extracted successfully from {extraction_result['source']} side", "aadhar_confirmation", flow_data
        else:
            # QR extraction failed - ask for manual input
            return True, "Couldn't extract AADHAR information from QR code. Please provide your details manually.", "aadhar_manual_input", flow_data
    
    def get_step_response(self, step_id: str, flow_data: Dict[str, Any] = None) -> CheckinResponse:
        """Get the response for a specific step"""
        if step_id == "phone_validation":
            return self.get_phone_number_message()
        
        elif step_id == "existing_customer_confirmation":
            guest_id = flow_data.get("guest_id")
            if guest_id:
                try:
                    guest = Guest.objects.get(id=guest_id)
                    return self.get_existing_customer_confirmation(guest)
                except Guest.DoesNotExist:
                    return CheckinResponse(
                        response_type=ResponseType.TEXT,
                        text="❌ Error: Guest record not found. Please provide your phone number again."
                    )
            else:
                return CheckinResponse(
                    response_type=ResponseType.TEXT,
                    text="❌ Error: Guest information not found. Please provide your phone number again."
                )
        
        elif step_id == "new_customer_welcome":
            return self.get_new_customer_welcome()
        
        elif step_id == "checkin_complete":
            return CheckinResponse(
                response_type=ResponseType.TEXT,
                text="🎉 Check-in completed! Your room key will be available at the front desk. Enjoy your stay!"
            )
        
        elif step_id == "update_name":
            return CheckinResponse(
                response_type=ResponseType.TEXT,
                text="Please provide your full name as it appears on your ID."
            )
        
        elif step_id == "id_type_selection":
            return self.get_id_type_selection()
        
        elif step_id == "id_front_upload":
            doc_type = flow_data.get("selected_document_name", "ID document")
            return self.get_id_upload_instructions(doc_type)
        
        elif step_id == "id_back_upload":
            doc_type = flow_data.get("selected_document_name", "ID document")
            return self.get_id_back_upload_instructions(doc_type)
        
        elif step_id == "additional_info_collection":
            doc_type = flow_data.get("selected_document_name", "ID document")
            return self.get_additional_info_request(doc_type)
        
        elif step_id == "additional_info_confirmation":
            info = flow_data.get("name", "")
            if info:
                confirmation_text = f"📋 **Information Provided:**\n"
                confirmation_text += f"• Name: {flow_data.get('name', '')}\n"
                confirmation_text += f"• Date of Birth: {flow_data.get('date_of_birth', '')}\n"
                confirmation_text += f"• Address: {flow_data.get('address', '')}\n\n"
                confirmation_text += "Is this information correct?"
                
                return CheckinResponse(
                    response_type=ResponseType.BUTTONS,
                    text=confirmation_text,
                    options=["Yes, this is correct", "No, I need to correct it"]
                )
            else:
                return CheckinResponse(
                    response_type=ResponseType.TEXT,
                    text="Please provide your information in the format: Name, DD/MM/YYYY, Address"
                )
        
        elif step_id == "aadhar_confirmation":
            extracted_info = flow_data.get("extracted_aadhar_info", {})
            return self.get_aadhar_confirmation(extracted_info)
        
        elif step_id == "aadhar_manual_input":
            return CheckinResponse(
                response_type=ResponseType.TEXT,
                text="📝 We couldn't read the QR code from your AADHAR images. This could be due to:\n• QR code not being clear or visible\n• Blurry or cut-off QR code\n• Poor lighting conditions\n\nPlease provide your AADHAR details manually:\n\n1. Full name as shown on AADHAR\n2. Date of birth (DD/MM/YYYY)\n3. Complete address\n\nSend all information in one message, separated by commas or new lines.\n\n💡 For future uploads, try to capture the QR code portion more clearly!"
            )
        
        # Default case
        return CheckinResponse(
            response_type=ResponseType.TEXT,
            text="Let's continue with your check-in process."
        )


def check_in_flow(flow_id: str, incoming_data: Dict[str, Any], 
                 previous_flow_message: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Main check-in flow function
    
    Args:
        flow_id: Unique identifier for this check-in flow
        incoming_data: Contains user input and metadata
        previous_flow_message: Contains previous step info (step_id, message, etc.)
    
    Returns:
        Dict containing:
        - flow_id: The flow identifier
        - step_id: Current step identifier
        - response: CheckinResponse object as dict
        - status: Current status of the flow
        - next_action: What to do next
        - flow_data: Collected data so far
    """
    
    # Initialize or retrieve flow
    if not previous_flow_message:
        # New flow - start with phone validation
        flow = CheckinFlow()
        flow.flow_id = flow_id
        flow.current_step = "phone_validation"
        flow.flow_data = {}
        
        response = flow.get_step_response("phone_validation")
        
        return {
            "flow_id": flow_id,
            "step_id": "phone_validation",
            "response": response.to_dict(),
            "status": "in_progress",
            "next_action": "await_user_input",
            "flow_data": {}
        }
    
    # Continuing existing flow
    current_step_id = previous_flow_message.get("step_id")
    flow_data = previous_flow_message.get("flow_data", {})
    user_input = incoming_data.get("message", "")
    
    # Validate required fields
    if not current_step_id:
        return {
            "flow_id": flow_id,
            "step_id": None,
            "response": CheckinResponse(
                response_type=ResponseType.TEXT,
                text="❌ Error: Unable to determine current step. Please restart check-in."
            ).to_dict(),
            "status": "error",
            "next_action": "restart_flow",
            "flow_data": {}
        }
    
    # Create flow instance
    flow = CheckinFlow()
    flow.flow_data = flow_data
    
    # Process based on current step
    if current_step_id == "phone_validation":
        # Process phone number input
        is_valid, message, next_step_id, updated_flow_data = flow.process_phone_input(user_input)
        
        if not is_valid:
            # Validation failed - stay on current step
            response = CheckinResponse(response_type=ResponseType.TEXT, text=message)
            return {
                "flow_id": flow_id,
                "step_id": current_step_id,
                "response": response.to_dict(),
                "status": "validation_failed",
                "next_action": "retry_input",
                "flow_data": flow_data
            }
        
        # Move to next step
        next_response = flow.get_step_response(next_step_id, updated_flow_data)
        return {
            "flow_id": flow_id,
            "step_id": next_step_id,
            "response": next_response.to_dict(),
            "status": "in_progress",
            "next_action": "await_user_input",
            "flow_data": updated_flow_data
        }
    
    elif current_step_id == "existing_customer_confirmation":
        # Process existing customer confirmation
        is_valid, message, next_step_id, updated_flow_data = flow.process_existing_customer_response(user_input, flow_data)
        
        if not is_valid:
            response = CheckinResponse(response_type=ResponseType.TEXT, text=message)
            return {
                "flow_id": flow_id,
                "step_id": current_step_id,
                "response": response.to_dict(),
                "status": "validation_failed",
                "next_action": "retry_input",
                "flow_data": flow_data
            }
        
        # Get response for next step
        next_response = flow.get_step_response(next_step_id, updated_flow_data)
        next_action = "end_flow" if next_step_id == "checkin_complete" else "await_user_input"
        
        return {
            "flow_id": flow_id,
            "step_id": next_step_id,
            "response": next_response.to_dict(),
            "status": "completed" if next_step_id == "checkin_complete" else "in_progress",
            "next_action": next_action,
            "flow_data": updated_flow_data
        }
    
    elif current_step_id == "id_type_selection":
        # Process ID type selection
        is_valid, message, next_step_id, updated_flow_data = flow.process_id_type_selection(user_input, flow_data)
        
        if not is_valid:
            response = CheckinResponse(response_type=ResponseType.TEXT, text=message)
            return {
                "flow_id": flow_id,
                "step_id": current_step_id,
                "response": response.to_dict(),
                "status": "validation_failed",
                "next_action": "retry_input",
                "flow_data": flow_data
            }
        
        next_response = flow.get_step_response(next_step_id, updated_flow_data)
        return {
            "flow_id": flow_id,
            "step_id": next_step_id,
            "response": next_response.to_dict(),
            "status": "in_progress",
            "next_action": "await_media_upload",
            "flow_data": updated_flow_data
        }
    
    elif current_step_id == "id_front_upload":
        # Handle front ID upload - store the media data
        media_data = incoming_data.get("media_data")
        if not media_data:
            response = CheckinResponse(
                response_type=ResponseType.TEXT,
                text="Please upload an image of your ID document."
            )
            return {
                "flow_id": flow_id,
                "step_id": current_step_id,
                "response": response.to_dict(),
                "status": "awaiting_media",
                "next_action": "await_media_upload",
                "flow_data": flow_data
            }
        
        flow_data["id_front_image"] = media_data
        next_response = flow.get_step_response("id_back_upload", flow_data)
        return {
            "flow_id": flow_id,
            "step_id": "id_back_upload",
            "response": next_response.to_dict(),
            "status": "in_progress",
            "next_action": "await_media_upload",
            "flow_data": flow_data
        }
    
    elif current_step_id == "id_back_upload":
        # Handle back ID upload and process based on document type
        media_data = incoming_data.get("media_data")
        if not media_data:
            response = CheckinResponse(
                response_type=ResponseType.TEXT,
                text="Please upload the back side of your ID document."
            )
            return {
                "flow_id": flow_id,
                "step_id": current_step_id,
                "response": response.to_dict(),
                "status": "awaiting_media",
                "next_action": "await_media_upload",
                "flow_data": flow_data
            }
        
        flow_data["id_back_image"] = media_data
        doc_type = flow_data.get("selected_document_type")
        
        if doc_type == "aadhar_id":
            # Process AADHAR verification
            is_valid, message, next_step_id, updated_flow_data = flow.process_aadhar_verification(flow_data)
            next_response = flow.get_step_response(next_step_id, updated_flow_data)
        else:
            # For other IDs, ask for additional information
            is_valid = True
            message = "ID documents uploaded successfully"
            next_step_id = "additional_info_collection"
            updated_flow_data = flow_data
            next_response = flow.get_step_response(next_step_id, updated_flow_data)
        
        return {
            "flow_id": flow_id,
            "step_id": next_step_id,
            "response": next_response.to_dict(),
            "status": "in_progress",
            "next_action": "await_user_input",
            "flow_data": updated_flow_data
        }
    
    elif current_step_id == "additional_info_collection":
        # Process additional information for non-AADHAR IDs
        is_valid, message, next_step_id, updated_flow_data = flow.process_additional_info(user_input, flow_data)
        
        if not is_valid:
            response = CheckinResponse(response_type=ResponseType.TEXT, text=message)
            return {
                "flow_id": flow_id,
                "step_id": current_step_id,
                "response": response.to_dict(),
                "status": "validation_failed",
                "next_action": "retry_input",
                "flow_data": flow_data
            }
        
        next_response = flow.get_step_response(next_step_id, updated_flow_data)
        return {
            "flow_id": flow_id,
            "step_id": next_step_id,
            "response": next_response.to_dict(),
            "status": "in_progress",
            "next_action": "await_user_input",
            "flow_data": updated_flow_data
        }
    
    elif current_step_id in ["additional_info_confirmation", "aadhar_confirmation"]:
        # Process confirmation responses
        response_lower = user_input.strip().lower()
        if response_lower in ["yes", "1", "correct", "confirm"]:
            # Create guest record and complete check-in
            return {
                "flow_id": flow_id,
                "step_id": "checkin_complete",
                "response": flow.get_step_response("checkin_complete").to_dict(),
                "status": "completed",
                "next_action": "end_flow",
                "flow_data": flow_data
            }
        else:
            # Ask to correct information
            if current_step_id == "aadhar_confirmation":
                next_step = "aadhar_manual_input"
            else:
                next_step = "additional_info_collection"
            
            next_response = flow.get_step_response(next_step, flow_data)
            return {
                "flow_id": flow_id,
                "step_id": next_step,
                "response": next_response.to_dict(),
                "status": "in_progress", 
                "next_action": "await_user_input",
                "flow_data": flow_data
            }
    
    elif current_step_id == "aadhar_manual_input":
        # Process manual AADHAR input
        is_valid, message, next_step_id, updated_flow_data = flow.process_additional_info(user_input, flow_data)
        
        if not is_valid:
            response = CheckinResponse(response_type=ResponseType.TEXT, text=message)
            return {
                "flow_id": flow_id,
                "step_id": current_step_id,
                "response": response.to_dict(),
                "status": "validation_failed",
                "next_action": "retry_input",
                "flow_data": flow_data
            }
        
        # Show confirmation for manually entered data
        flow_data["manual_aadhar_info"] = {
            "name": updated_flow_data.get("name"),
            "dob": updated_flow_data.get("date_of_birth"),
            "address": updated_flow_data.get("address")
        }
        next_response = flow.get_step_response("additional_info_confirmation", updated_flow_data)
        return {
            "flow_id": flow_id,
            "step_id": "additional_info_confirmation",
            "response": next_response.to_dict(),
            "status": "in_progress",
            "next_action": "await_user_input",
            "flow_data": updated_flow_data
        }
    
    # Handle other steps (for future implementation)
    response = flow.get_step_response(current_step_id, flow_data)
    return {
        "flow_id": flow_id,
        "step_id": current_step_id,
        "response": response.to_dict(),
        "status": "in_progress",
        "next_action": "await_user_input",
        "flow_data": flow_data
    }


# Example usage and test cases
if __name__ == "__main__":
    print("=== Testing New Flow Start ===")
    result = check_in_flow("test_flow_1", {"message": "start checkin"}, None)
    print(json.dumps(result, indent=2))
    
    print("\n=== Testing Phone Input ===")
    # Test with existing customer (you'll need to have a guest in your database)
    result = check_in_flow("test_flow_1", {"message": "+1234567890"}, result)
    print(json.dumps(result, indent=2))
    
    print("\n=== Testing Existing Customer Confirmation ===")
    result = check_in_flow("test_flow_1", {"message": "Yes, this is correct"}, result)
    print(json.dumps(result, indent=2))
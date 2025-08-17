from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..services import (
    process_webhook_message,
    handle_initial_message,
    get_active_context,
)
from ..models import WebhookLog
from django.db import utils as db_utils
import logging

logger = logging.getLogger(__name__)

class WhatsAppWebhookView(APIView):
    """
    View to handle incoming WhatsApp messages from the WhatsApp Business API.
    This view is the single entry point for all guest interactions.
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """
        Handle incoming POST requests from the WhatsApp API.
        """
        webhook_log = None
        try:
            webhook_log = WebhookLog.objects.create(
                payload=request.data,
                processed_successfully=False
            )
            # 1. Extract data from the webhook payload
            # This handles various formats, e.g., Twilio, generic
            if 'From' in request.data and 'Body' in request.data:
                from_no = request.data.get('From', '').replace('whatsapp:', '')
                message_body = request.data.get('Body', '')
            else:
                from_no = request.data.get('from_no')
                message_body = request.data.get('message', '')

            if not from_no or not message_body:
                raise ValueError("Missing 'from_no' or 'message' in payload")

            # 2. Determine if there's an active conversation context.
            context = get_active_context(from_no)

            if not context:
                # No active context, treat as an initial message.
                result = handle_initial_message(from_no, message_body)
            else:
                # Active context exists, process as part of an ongoing conversation.
                result = process_webhook_message(from_no, message_body)

            # 3. Log success and return the response
            if webhook_log:
                webhook_log.processed_successfully = True
                webhook_log.save()

            logger.info(f"Processed message from {from_no}: {result}")
            return Response(result, status=status.HTTP_200_OK)

        except ValueError as ve:
            error_message = str(ve)
            logger.warning(f"Bad request processing webhook: {error_message}")
            if webhook_log:
                webhook_log.error_message = error_message
                webhook_log.save()
            return Response({
                'status': 'error',
                'message': error_message
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error processing webhook: {error_message}", exc_info=True)
            if webhook_log:
                webhook_log.error_message = error_message
                webhook_log.save()

            # Customize response for database errors to guide the developer.
            if isinstance(e, db_utils.ProgrammingError):
                message = "Database schema error. Please ensure migrations are applied."
            else:
                message = "An internal error occurred while processing the webhook."

            return Response({
                'status': 'error',
                'message': message
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

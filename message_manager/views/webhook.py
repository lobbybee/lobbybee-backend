from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import json
import logging
# Process message
from ..services.message_handler import MessageHandler
logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppWebhookView(View):
    def post(self, request):
        try:
            print("Received webhook request")
            data = json.loads(request.body)

            # Extract WhatsApp message details
            phone_number = self.extract_phone_number(data)
            message_content = self.extract_message_content(data)
            department = self.extract_department(data)

            if not phone_number or not message_content:
                return JsonResponse({'status': 'ignored'})


            handler = MessageHandler()
            print("Processing message")
            response = handler.process_message(phone_number, message_content, department)

            # Send response back to WhatsApp (implement WhatsApp API call)
            # if response.get('message'):
            #     self.send_whatsapp_message(phone_number, response['message'])

            return JsonResponse({'status': 'processed'})

        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            return JsonResponse({'status': 'error'})

    def extract_phone_number(self, data):
        return data.get('phone_number')

    def extract_message_content(self, data):
        return data.get('message_content')

    def extract_department(self, data):
        return data.get('department')

    def send_whatsapp_message(self, phone_number, message):
        # Implement WhatsApp API call
        # This is a placeholder - in a real implementation, you would call the WhatsApp Business API
        logger.info(f"Sending WhatsApp message to {phone_number}: {message}")
        pass

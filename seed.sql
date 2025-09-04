TRUNCATE TABLE hotel_hotel CASCADE;
TRUNCATE TABLE context_manager_conversationmessage CASCADE;
TRUNCATE TABLE context_manager_conversationcontext CASCADE;
TRUNCATE TABLE context_manager_messagequeue CASCADE;
TRUNCATE TABLE context_manager_webhooklog CASCADE;
TRUNCATE TABLE context_manager_flowstep CASCADE;
TRUNCATE TABLE context_manager_hotelflowconfiguration CASCADE;
TRUNCATE TABLE context_manager_flowsteptemplate CASCADE;
TRUNCATE TABLE context_manager_flowaction CASCADE;
TRUNCATE TABLE context_manager_flowtemplate CASCADE;
TRUNCATE TABLE context_manager_placeholder CASCADE;
TRUNCATE TABLE context_manager_scheduledmessagetemplate CASCADE;

INSERT INTO hotel_hotel (id, name, description, address, city, state, country, pincode, phone, email, license_document_url, registration_document_url, additional_documents, latitude, longitude, qr_code_url, unique_qr_code, wifi_password, check_in_time, time_zone, status, is_verified, is_active, is_demo, registration_date, verified_at, updated_at) VALUES
('00000000000000000000000000000001', 'LobbyBee Demo', 'A demonstration hotel to showcase the features of LobbyBee.', '123 Demo Street', 'Metropolis', 'Demo State', 'DEMO', '12345', '+10000000000', 'demo@lobbybee.com', NULL, NULL, '[]', NULL, NULL, '', 'lobbybee_demo_seed', '', '14:00:00', 'UTC', 'verified', true, true, true, NOW(), NOW(), NOW());

INSERT INTO context_manager_placeholder (name, description, resolving_logic) VALUES
('hotel_name', 'Name of the hotel', 'hotel.name'),
('hotel_phone', 'Hotel contact phone number', 'hotel.phone'),
('hotel_email', 'Hotel email address', 'hotel.email'),
('hotel_address', 'Hotel address', 'hotel.address'),
('guest_name', 'Guest full name', 'guest.full_name'),
('guest_phone', 'Guest WhatsApp number', 'guest.whatsapp_number'),
('room_number', 'Assigned room number', 'stay.room_number'),
('wifi_password', 'Hotel WiFi password', 'hotel.wifi_password'),
('selected_id_type', 'Selected ID type', 'selected_id_type'),
('selected_item', 'Selected menu item', 'selected_item'),
('selected_service', 'Selected room service', 'selected_service'),
('food_category', 'Selected food category', 'food_category'),
('item_price', 'Price of selected item', 'item_price');

INSERT INTO context_manager_flowtemplate (name, description, category, is_active) VALUES
('Random Guest Flow', 'Flow for random website visitors and demo users', 'random_guest', true),
('Hotel Check-in Flow', 'Complete check-in process for hotel guests', 'hotel_checkin', true),
('Hotel Services Flow', 'In-stay services and amenities', 'hotel_services', true),
('Checkout Flow', 'Guest checkout and feedback collection', 'checkout', true),
('Returning Guest Flow', 'Flow for guests who have stayed before but are not currently checked in', 'returning_guest', true);

INSERT INTO context_manager_flowaction (name, action_type, configuration) VALUES
('Notify Reception', 'SEND_NOTIFICATION', '{"department": "reception", "priority": "normal"}'),
('Notify Room Service', 'SEND_NOTIFICATION', '{"department": "room_service", "priority": "normal"}'),
('Notify Kitchen', 'SEND_NOTIFICATION', '{"department": "kitchen", "priority": "normal"}'),
('Notify Management', 'SEND_NOTIFICATION', '{"department": "management", "priority": "high"}'),
('Log Check-in Request', 'LOG_REQUEST', '{"type": "checkin", "status": "pending"}'),
('Create Order', 'CREATE_ORDER', '{"type": "food", "status": "pending"}'),
('Send Confirmation SMS', 'SEND_SMS', '{"template": "confirmation"}');

INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, "order", message_template, message_type, options, quick_reply_navigation) VALUES
((SELECT id FROM context_manager_flowtemplate WHERE category = 'random_guest'), 'Welcome Message', 0, '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Welcome! How can we assist you today?"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "demo", "title": "View Demo"}}, {"type": "reply", "reply": {"id": "contact", "title": "Contact Us"}}]}}}', 'quick-reply', '{"demo": "View Demo", "contact": "Contact Us"}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'random_guest'), 'Demo Services', 1, '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Here is a demo of our premium services. You can explore:"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "explore_services", "title": "Explore Hotel Services"}}, {"type": "reply", "reply": {"id": "back", "title": "Back"}}, {"type": "reply", "reply": {"id": "main_menu", "title": "Main Menu"}}]}}}', 'quick-reply', '{"explore_services": "Explore Hotel Services"}', '{"Back": "back", "Main Menu": "main_menu"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'random_guest'), 'Contact Details', 2, '{"text": "🏢 Platform: Lobbybee\n📞 Phone: +917736600773\n📧 Email: hello@lobbybee.com\n\nFeel free to contact us for any CRM related query!"}', 'text', '{}', '{"Back": "back", "Main Menu": "main_menu"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Checkin Welcome', 0, '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Welcome to {hotel_name}! Ready to begin your check-in process?"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "proceed", "title": "Proceed with Check-in"}}]}}}', 'quick-reply', '{"proceed": "Proceed with Check-in"}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Guest Verification', 1, '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Let me verify your details:\n\nName: {guest_name}\nPhone: {guest_phone}\n\nAre these details correct?"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "confirm", "title": "Confirm Details"}}, {"type": "reply", "reply": {"id": "update", "title": "Update Details"}}]}}}', 'quick-reply', '{"confirm": "Confirm Details", "update": "Update Details"}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Details Update', 2, '{"text": "Let me help you update your details."}' , 'text', '{}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Collect Full Name', 3, '{"text": "What is your full name?"}', 'text', '{}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'ID Type Selection', 4, '{"type": "interactive", "interactive": {"type": "list", "body": {"text": "Please select your ID type:"}, "action": {"button": "Select ID Type", "sections": [{"title": "ID Documents", "rows": [{"id": "pan", "title": "PAN Card"}, {"id": "aadhaar", "title": "Aadhaar Card"}, {"id": "driving_license", "title": "Driving License"}]}]}}}', 'list-picker', '{"pan": "PAN Card", "aadhaar": "Aadhaar Card", "driving_license": "Driving License"}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'ID Photo Upload', 5, '{"text": "Please upload a clear photo of your selected ID document."}' , 'media', '{}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Room Request Placed', 6, '{"text": "Your room request has been placed and is being processed by our reception team."}' , 'text', '{}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Checkin Success', 7, '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Check-in successful! 🎉\n\nRoom: {room_number}\nWiFi: {wifi_password}\n\nHow can we assist you today?"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "services", "title": "Explore Hotel Services"}}]}}}', 'quick-reply', '{"services": "Explore Hotel Services"}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Services Menu', 0, '{"type": "interactive", "interactive": {"type": "list", "body": {"text": "How can we assist you today?"}, "action": {"button": "Select Service", "sections": [{"title": "Hotel Services", "rows": [{"id": "reception", "title": "Reception"}, {"id": "room_service", "title": "Room Service"}, {"id": "restaurant", "title": "Cafe/Restaurant"}, {"id": "management", "title": "Management"}]}]}}}', 'list-picker', '{"reception": "Reception", "room_service": "Room Service", "restaurant": "Cafe/Restaurant", "management": "Management"}', '{"Main Menu": "main_menu"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Reception Request', 1, '{"text": "What would you like to check with Reception?"}', 'text', '{}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Reception Confirmation', 2, '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Your request has been forwarded to reception. They will assist you shortly."}, "action": {"buttons": [{"type": "reply", "reply": {"id": "services", "title": "Back to Hotel Services"}}]}}}', 'quick-reply', '{"services": "Back to Hotel Services"}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Room Service Options', 3, '{"type": "interactive", "interactive": {"type": "list", "body": {"text": "Select a room service option:"}, "action": {"button": "Select Option", "sections": [{"title": "Room Services", "rows": [{"id": "clean_room", "title": "Clean Room"}, {"id": "maintenance", "title": "Room Maintenance Request"}, {"id": "accessory", "title": "Accessory Request"}]}]}}}', 'list-picker', '{"clean_room": "Clean Room", "maintenance": "Room Maintenance Request", "accessory": "Accessory Request"}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Room Service Details', 4, '{"text": "Please describe your service request in detail:"}', 'text', '{}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Room Service Confirmation', 5, '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Your service request has been submitted and will be deployed to your room shortly."}, "action": {"buttons": [{"type": "reply", "reply": {"id": "services", "title": "Back to Hotel Services"}}]}}}', 'quick-reply', '{"services": "Back to Hotel Services"}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Restaurant Categories', 6, '{"type": "interactive", "interactive": {"type": "list", "body": {"text": "Available dining options (Timings: 07:00 AM - 11:00 PM):"}, "action": {"button": "Select Category", "sections": [{"title": "Dining Options", "rows": [{"id": "breakfast", "title": "Breakfast"}, {"id": "dessert", "title": "Dessert"}, {"id": "chinese", "title": "Chinese"}]}]}}}', 'list-picker', '{"breakfast": "Breakfast", "dessert": "Dessert", "chinese": "Chinese"}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Breakfast Menu', 7, '{"type": "interactive", "interactive": {"type": "list", "body": {"text": "Here are our breakfast options:"}, "action": {"button": "Select Item", "sections": [{"title": "Breakfast Menu", "rows": [{"id": "continental", "title": "Continental Breakfast - $18"}, {"id": "american", "title": "American Breakfast - $22"}, {"id": "healthy", "title": "Healthy Bowl - $16"}]}]}}}', 'list-picker', '{"continental": "Continental Breakfast - $18", "american": "American Breakfast - $22", "healthy": "Healthy Bowl - $16"}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Dessert Menu', 8, '{"type": "interactive", "interactive": {"type": "list", "body": {"text": "Here are our dessert options:"}, "action": {"button": "Select Item", "sections": [{"title": "Dessert Menu", "rows": [{"id": "chocolate_cake", "title": "Chocolate Cake - $12"}, {"id": "ice_cream", "title": "Premium Ice Cream - $8"}, {"id": "fruit_platter", "title": "Fresh Fruit Platter - $10"}]}]}}}', 'list-picker', '{"chocolate_cake": "Chocolate Cake - $12", "ice_cream": "Premium Ice Cream - $8", "fruit_platter": "Fresh Fruit Platter - $10"}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Chinese Menu', 9, '{"type": "interactive", "interactive": {"type": "list", "body": {"text": "Here are our Chinese options:"}, "action": {"button": "Select Item", "sections": [{"title": "Chinese Menu", "rows": [{"id": "sweet_sour", "title": "Sweet & Sour Chicken - $24"}, {"id": "beef_broccoli", "title": "Beef with Broccoli - $26"}, {"id": "kung_pao", "title": "Kung Pao Chicken - $25"}]}]}}}', 'list-picker', '{"sweet_sour": "Sweet & Sour Chicken - $24", "beef_broccoli": "Beef with Broccoli - $26", "kung_pao": "Kung Pao Chicken - $25"}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Order Confirmation', 10, '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Confirm your order for {selected_item}?"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "confirm", "title": "Confirm Order"}}, {"type": "reply", "reply": {"id": "cancel", "title": "Cancel"}}]}}}', 'quick-reply', '{"confirm": "Confirm Order", "cancel": "Cancel"}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Order Success', 11, '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Your order has been placed successfully and will be delivered to your room!"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "services", "title": "Back to Hotel Services"}}]}}}', 'quick-reply', '{"services": "Back to Hotel Services"}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Management Options', 12, '{"type": "interactive", "interactive": {"type": "list", "body": {"text": "Management Services:"}, "action": {"button": "Select Option", "sections": [{"title": "Management", "rows": [{"id": "complaint", "title": "Raise a Complaint"}, {"id": "feedback", "title": "General Feedback"}]}]}}}', 'list-picker', '{"complaint": "Raise a Complaint", "feedback": "General Feedback"}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Complaint Details', 13, '{"text": "Please describe your complaint in detail. We take all feedback seriously:"}', 'text', '{}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Feedback Input', 14, '{"text": "Please share your feedback about our services:"}', 'text', '{}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Management Response', 15, '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Thank you for your feedback. Our management team will review this and get back to you within 24 hours."}, "action": {"buttons": [{"type": "reply", "reply": {"id": "services", "title": "Back to Hotel Services"}}]}}}', 'quick-reply', '{"services": "Back to Hotel Services"}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout'), 'Checkout Initiation', 0, '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Ready to check out? We hope you had a wonderful stay with us!"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "proceed", "title": "Proceed with Checkout"}}]}}}', 'quick-reply', '{"proceed": "Proceed with Checkout"}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout'), 'Feedback Request', 1, '{"text": "Please share your feedback about your stay with us. Your opinion matters:"}', 'text', '{}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout'), 'Feedback Thank You', 2, '{"text": "Thank you for your valuable feedback! We hope to welcome you back soon. Have a safe journey!"}', 'text', '{}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest'), 'Welcome Returning Guest', 0, '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Welcome back! How can we assist you today?"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "hotel_checkin", "title": "Check-in for New Stay"}}, {"type": "reply", "reply": {"id": "random_guest", "title": "Other Inquiries"}}]}}}', 'quick-reply', '{"hotel_checkin": "Check-in for New Stay", "random_guest": "Other Inquiries"}', '{}');

DO $$
DECLARE
   checkin_flow_id INT := (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin');
   services_flow_id INT := (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services');
   checkout_flow_id INT := (SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout');
BEGIN
   UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = checkin_flow_id AND step_name = 'ID Type Selection') WHERE flow_template_id = checkin_flow_id AND step_name = 'Collect Full Name';
   UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = checkin_flow_id AND step_name = 'ID Photo Upload') WHERE flow_template_id = checkin_flow_id AND step_name = 'ID Type Selection';
   UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = checkin_flow_id AND step_name = 'Room Request Placed') WHERE flow_template_id = checkin_flow_id AND step_name = 'ID Photo Upload';
   UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = checkin_flow_id AND step_name = 'Checkin Success') WHERE flow_template_id = checkin_flow_id AND step_name = 'Room Request Placed';
   UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Reception Confirmation') WHERE flow_template_id = services_flow_id AND step_name = 'Reception Request';
   UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Room Service Confirmation') WHERE flow_template_id = services_flow_id AND step_name = 'Room Service Details';
   UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Management Response') WHERE flow_template_id = services_flow_id AND step_name = 'Complaint Details';
   UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Management Response') WHERE flow_template_id = services_flow_id AND step_name = 'Feedback Input';
   UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = checkout_flow_id AND step_name = 'Feedback Request') WHERE flow_template_id = checkout_flow_id AND step_name = 'Checkout Initiation';
   UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = checkout_flow_id AND step_name = 'Feedback Thank You') WHERE flow_template_id = checkout_flow_id AND step_name = 'Feedback Request';
END $$;

DO $$
DECLARE
   random_guest_flow_id INT := (SELECT id FROM context_manager_flowtemplate WHERE category = 'random_guest');
   checkin_flow_id INT := (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin');
   services_flow_id INT := (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services');
BEGIN
   UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('demo', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = random_guest_flow_id AND step_name = 'Demo Services'), 'contact', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = random_guest_flow_id AND step_name = 'Contact Details')) WHERE flow_template_id = random_guest_flow_id AND step_name = 'Welcome Message';
   UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('explore_services', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Services Menu')) WHERE flow_template_id = random_guest_flow_id AND step_name = 'Demo Services';
   UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('proceed', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = checkin_flow_id AND step_name = 'Collect Full Name')) WHERE flow_template_id = checkin_flow_id AND step_name = 'Checkin Welcome';
   UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('confirm', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = checkin_flow_id AND step_name = 'ID Type Selection'), 'update', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = checkin_flow_id AND step_name = 'Details Update')) WHERE flow_template_id = checkin_flow_id AND step_name = 'Guest Verification';
   UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('services', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Services Menu')) WHERE flow_template_id = checkin_flow_id AND step_name = 'Checkin Success';
   UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('reception', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Reception Request'), 'room_service', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Room Service Options'), 'restaurant', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Restaurant Categories'), 'management', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Management Options')) WHERE flow_template_id = services_flow_id AND step_name = 'Services Menu';
   UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('services', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Services Menu')) WHERE flow_template_id = services_flow_id AND step_name IN ('Reception Confirmation', 'Room Service Confirmation', 'Order Success', 'Management Response');
   UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('clean_room', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Room Service Details'), 'maintenance', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Room Service Details'), 'accessory', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Room Service Details')) WHERE flow_template_id = services_flow_id AND step_name = 'Room Service Options';
   UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('breakfast', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Breakfast Menu'), 'dessert', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Dessert Menu'), 'chinese', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Chinese Menu')) WHERE flow_template_id = services_flow_id AND step_name = 'Restaurant Categories';
   UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('continental', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation'), 'american', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation'), 'healthy', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation')) WHERE flow_template_id = services_flow_id AND step_name = 'Breakfast Menu';
   UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('chocolate_cake', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation'), 'ice_cream', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation'), 'fruit_platter', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation')) WHERE flow_template_id = services_flow_id AND step_name = 'Dessert Menu';
   UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('sweet_sour', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation'), 'beef_broccoli', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation'), 'kung_pao', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation')) WHERE flow_template_id = services_flow_id AND step_name = 'Chinese Menu';
   UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('confirm', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Success'), 'cancel', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Restaurant Categories')) WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation';
   UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('complaint', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Complaint Details'), 'feedback', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Feedback Input')) WHERE flow_template_id = services_flow_id AND step_name = 'Management Options';
   UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('proceed', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout') AND step_name = 'Feedback Request')) WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout') AND step_name = 'Checkout Initiation';
END $$;

INSERT INTO context_manager_hotelflowconfiguration (hotel_id, flow_template_id, is_enabled, customization_data) VALUES
('00000000000000000000000000000001', (SELECT id FROM context_manager_flowtemplate WHERE category = 'random_guest'), true, '{}'),
('00000000000000000000000000000001', (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), true, '{}'),
('00000000000000000000000000000001', (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), true, '{}'),
('00000000000000000000000000000001', (SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout'), true, '{}'),
('00000000000000000000000000000001', (SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest'), true, '{}');

INSERT INTO context_manager_scheduledmessagetemplate (hotel_id, message_type, trigger_condition, message_template, is_active) VALUES
('00000000000000000000000000000001', 'checkout_reminder', '{"hours_before_checkout": 2}', 'Dear {guest_name}, this is a reminder that your checkout is at 11:00 AM. Would you like to extend your stay or provide feedback?', true),
('00000000000000000000000000000001', 'welcome', '{"trigger": "checkin_complete"}', 'Welcome to {hotel_name}, {guest_name}! Your check-in is complete. How can we make your stay memorable?', true),
('00000000000000000000000000000001', 'promo', '{"days_after_checkout": 30}', 'We miss you at {hotel_name}, {guest_name}! Book your next stay with us and get 20% off.', true);

SELECT 'Applied: ' || COUNT(*) || ' flow templates' FROM context_manager_flowtemplate;
SELECT 'Applied: ' || COUNT(*) || ' flow steps' FROM context_manager_flowsteptemplate;
SELECT 'Applied: ' || COUNT(*) || ' placeholders' FROM context_manager_placeholder;
SELECT 'Applied: ' || COUNT(*) || ' actions' FROM context_manager_flowaction;
SELECT 'Applied: ' || COUNT(*) || ' hotel configs' FROM context_manager_hotelflowconfiguration;
SELECT 'Applied: ' || COUNT(*) || ' scheduled templates' FROM context_manager_scheduledmessagetemplate;
SELECT 'DONE APPLYING SEED DATA';

-- Fix button texts that are too long
UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Welcome to {hotel_name}! Ready to begin your check-in process?"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "proceed", "title": "Start Check-in"}}]}}}',
options = '{"proceed": "Start Check-in"}'
WHERE step_name = 'Checkin Welcome';

UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Let me verify your details:\n\nName: {guest_name}\nPhone: {guest_phone}\n\nAre these details correct?"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "confirm", "title": "Confirm"}}, {"type": "reply", "reply": {"id": "update", "title": "Update"}}]}}}',
options = '{"confirm": "Confirm", "update": "Update"}'
WHERE step_name = 'Guest Verification';

UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Check-in successful! 🎉\n\nRoom: {room_number}\nWiFi: {wifi_password}\n\nHow can we assist you today?"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "services", "title": "Hotel Services"}}]}}}',
options = '{"services": "Hotel Services"}'
WHERE step_name = 'Checkin Success';

UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Your request has been forwarded to reception. They will assist you shortly."}, "action": {"buttons": [{"type": "reply", "reply": {"id": "services", "title": "Back to Services"}}]}}}',
options = '{"services": "Back to Services"}'
WHERE step_name = 'Reception Confirmation';

UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Your service request has been submitted and will be deployed to your room shortly."}, "action": {"buttons": [{"type": "reply", "reply": {"id": "services", "title": "Back to Services"}}]}}}',
options = '{"services": "Back to Services"}'
WHERE step_name = 'Room Service Confirmation';

UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Your order has been placed successfully and will be delivered to your room!"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "services", "title": "Back to Services"}}]}}}',
options = '{"services": "Back to Services"}'
WHERE step_name = 'Order Success';

UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Thank you for your feedback. Our management team will review this and get back to you within 24 hours."}, "action": {"buttons": [{"type": "reply", "reply": {"id": "services", "title": "Back to Services"}}]}}}',
options = '{"services": "Back to Services"}'
WHERE step_name = 'Management Response';

UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Ready to check out? We hope you had a wonderful stay with us!"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "proceed", "title": "Start Checkout"}}]}}}',
options = '{"proceed": "Start Checkout"}'
WHERE step_name = 'Checkout Initiation';

UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Welcome back! How can we assist you today?"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "hotel_checkin", "title": "New Check-in"}}, {"type": "reply", "reply": {"id": "random_guest", "title": "Other Inquiries"}}]}}}',
options = '{"hotel_checkin": "New Check-in", "random_guest": "Other Inquiries"}'
WHERE step_name = 'Welcome Returning Guest';

-- Update Interactive Lists with title + description structure
UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "list", "body": {"text": "How can we assist you today?"}, "action": {"button": "Select Service", "sections": [{"title": "Hotel Services", "rows": [{"id": "reception", "title": "Reception", "description": "Front desk assistance"}, {"id": "room_service", "title": "Room Service", "description": "Housekeeping & maintenance"}, {"id": "restaurant", "title": "Restaurant", "description": "Food & dining options"}, {"id": "management", "title": "Management", "description": "Feedback & complaints"}]}]}}}',
options = '{"reception": "Reception", "room_service": "Room Service", "restaurant": "Restaurant", "management": "Management"}'
WHERE step_name = 'Services Menu';

UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "list", "body": {"text": "Select a room service option:"}, "action": {"button": "Select Option", "sections": [{"title": "Room Services", "rows": [{"id": "clean_room", "title": "Clean Room", "description": "Housekeeping service"}, {"id": "maintenance", "title": "Maintenance", "description": "Fix room issues"}, {"id": "accessory", "title": "Accessories", "description": "Extra pillows, towels etc"}]}]}}}',
options = '{"clean_room": "Clean Room", "maintenance": "Maintenance", "accessory": "Accessories"}'
WHERE step_name = 'Room Service Options';

UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "list", "body": {"text": "Available dining options (Timings: 07:00 AM - 11:00 PM):"}, "action": {"button": "Select Category", "sections": [{"title": "Dining Options", "rows": [{"id": "breakfast", "title": "Breakfast", "description": "Morning delights"}, {"id": "dessert", "title": "Desserts", "description": "Sweet treats"}, {"id": "chinese", "title": "Chinese", "description": "Asian cuisine"}]}]}}}',
options = '{"breakfast": "Breakfast", "dessert": "Desserts", "chinese": "Chinese"}'
WHERE step_name = 'Restaurant Categories';

UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "list", "body": {"text": "Here are our breakfast options:"}, "action": {"button": "Select Item", "sections": [{"title": "Breakfast Menu", "rows": [{"id": "continental", "title": "Continental", "description": "Toast, fruits, coffee - $18"}, {"id": "american", "title": "American", "description": "Eggs, bacon, pancakes - $22"}, {"id": "healthy", "title": "Healthy Bowl", "description": "Granola, yogurt, berries - $16"}]}]}}}',
options = '{"continental": "Continental", "american": "American", "healthy": "Healthy Bowl"}'
WHERE step_name = 'Breakfast Menu';

UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "list", "body": {"text": "Here are our dessert options:"}, "action": {"button": "Select Item", "sections": [{"title": "Dessert Menu", "rows": [{"id": "chocolate_cake", "title": "Chocolate Cake", "description": "Rich dark chocolate - $12"}, {"id": "ice_cream", "title": "Ice Cream", "description": "Premium vanilla/chocolate - $8"}, {"id": "fruit_platter", "title": "Fruit Platter", "description": "Fresh seasonal fruits - $10"}]}]}}}',
options = '{"chocolate_cake": "Chocolate Cake", "ice_cream": "Ice Cream", "fruit_platter": "Fruit Platter"}'
WHERE step_name = 'Dessert Menu';

UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "list", "body": {"text": "Here are our Chinese options:"}, "action": {"button": "Select Item", "sections": [{"title": "Chinese Menu", "rows": [{"id": "sweet_sour", "title": "Sweet & Sour", "description": "Chicken with pineapple - $24"}, {"id": "beef_broccoli", "title": "Beef Broccoli", "description": "Tender beef with broccoli - $26"}, {"id": "kung_pao", "title": "Kung Pao", "description": "Spicy chicken with peanuts - $25"}]}]}}}',
options = '{"sweet_sour": "Sweet & Sour", "beef_broccoli": "Beef Broccoli", "kung_pao": "Kung Pao"}'
WHERE step_name = 'Chinese Menu';

UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Confirm your order for {selected_item}?"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "confirm", "title": "Confirm Order"}}, {"type": "reply", "reply": {"id": "cancel", "title": "Cancel"}}]}}}',
options = '{"confirm": "Confirm Order", "cancel": "Cancel"}'
WHERE step_name = 'Order Confirmation';

UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "list", "body": {"text": "Management Services:"}, "action": {"button": "Select Option", "sections": [{"title": "Management", "rows": [{"id": "complaint", "title": "Complaint", "description": "Report an issue or problem"}, {"id": "feedback", "title": "Feedback", "description": "Share your experience"}]}]}}}',
options = '{"complaint": "Complaint", "feedback": "Feedback"}'
WHERE step_name = 'Management Options';

UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "list", "body": {"text": "Please select your ID type:"}, "action": {"button": "Select ID Type", "sections": [{"title": "ID Documents", "rows": [{"id": "pan", "title": "PAN Card", "description": "Permanent Account Number"}, {"id": "aadhaar", "title": "Aadhaar Card", "description": "Unique Identification"}, {"id": "driving_license", "title": "Driving License", "description": "Government issued DL"}]}]}}}',
options = '{"pan": "PAN Card", "aadhaar": "Aadhaar Card", "driving_license": "Driving License"}'
WHERE step_name = 'ID Type Selection';

-- Update Demo Services step
UPDATE context_manager_flowsteptemplate SET 
message_template = '{"type": "interactive", "interactive": {"type": "button", "body": {"text": "Here is a demo of our premium services. You can explore:"}, "action": {"buttons": [{"type": "reply", "reply": {"id": "explore_services", "title": "Hotel Services"}}, {"type": "reply", "reply": {"id": "back", "title": "Back"}}, {"type": "reply", "reply": {"id": "main_menu", "title": "Main Menu"}}]}}}',
options = '{"explore_services": "Hotel Services"}'
WHERE step_name = 'Demo Services';

-- Fix quick_reply_navigation texts - using JSONB contains operator
UPDATE context_manager_flowsteptemplate SET 
quick_reply_navigation = '{"Back": "back", "Services": "main_menu"}'
WHERE quick_reply_navigation ? 'Main Menu' 
   OR quick_reply_navigation::text ILIKE '%"Main Menu"%';

-- Alternative approach for quick_reply_navigation - target specific steps that have "Main Menu"
UPDATE context_manager_flowsteptemplate SET 
quick_reply_navigation = '{"Back": "back", "Services": "main_menu"}'
WHERE step_name IN ('Demo Services', 'Contact Details');

-- Update conditional next steps to use the correct service flow references
DO $$
DECLARE
   services_flow_id INT := (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services');
   random_guest_flow_id INT := (SELECT id FROM context_manager_flowtemplate WHERE category = 'random_guest');
   checkin_flow_id INT := (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin');
BEGIN
   -- Update Demo Services navigation
   UPDATE context_manager_flowsteptemplate SET 
   conditional_next_steps = jsonb_build_object('explore_services', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Services Menu')) 
   WHERE step_name = 'Demo Services';

   -- Update Checkin Success navigation
   UPDATE context_manager_flowsteptemplate SET 
   conditional_next_steps = jsonb_build_object('services', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Services Menu')) 
   WHERE step_name = 'Checkin Success';

   -- Update service confirmation steps navigation
   UPDATE context_manager_flowsteptemplate SET 
   conditional_next_steps = jsonb_build_object('services', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Services Menu')) 
   WHERE step_name IN ('Reception Confirmation', 'Room Service Confirmation', 'Order Success', 'Management Response');
END $$;

-- Verification queries to check the changes
SELECT step_name, 
       message_type,
       CASE 
         WHEN options IS NOT NULL THEN 
           (SELECT MAX(LENGTH(value::text)) FROM jsonb_each_text(options))
         ELSE NULL
       END as max_option_length,
       options
FROM context_manager_flowsteptemplate 
WHERE message_type IN ('quick-reply', 'list-picker')
ORDER BY step_name;

SELECT 'Update completed successfully. All interactive elements now comply with 20-character limit.' as status;

-- Enable media storage for ID Photo Upload step
UPDATE context_manager_flowsteptemplate SET should_store_media = true WHERE step_name = 'ID Photo Upload';
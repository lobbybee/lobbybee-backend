-- ============================================
-- COMPLETE HOTEL GUEST CRM FLOW SETUP (Django-Compatible Tables)
-- ============================================

-- First, truncate all relevant tables for a clean seed
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

-- ============================================-- DEMO HOTEL
-- ============================================
INSERT INTO hotel_hotel (id, name, description, address, city, state, country, pincode, phone, email, license_document_url, registration_document_url, additional_documents, latitude, longitude, qr_code_url, unique_qr_code, wifi_password, check_in_time, time_zone, status, is_verified, is_active, is_demo, registration_date, verified_at, updated_at) VALUES
('00000000000000000000000000000001', 'LobbyBee Demo', 'A demonstration hotel to showcase the features of LobbyBee.', '123 Demo Street', 'Metropolis', 'Demo State', 'DEMO', '12345', '+10000000000', 'demo@lobbybee.com', NULL, NULL, '[]', NULL, NULL, '', 'lobbybee_demo_seed', '', '14:00:00', 'UTC', 'verified', true, true, true, NOW(), NOW(), NOW());


-- ============================================-- PLACEHOLDERS
-- ============================================
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

-- ============================================-- FLOW TEMPLATES
-- ============================================
INSERT INTO context_manager_flowtemplate (name, description, category, is_active) VALUES
('Random Guest Flow', 'Flow for random website visitors and demo users', 'random_guest', true),
('Hotel Check-in Flow', 'Complete check-in process for hotel guests', 'hotel_checkin', true),
('Hotel Services Flow', 'In-stay services and amenities', 'hotel_services', true),
('Checkout Flow', 'Guest checkout and feedback collection', 'checkout', true),
('Returning Guest Flow', 'Flow for guests who have stayed before but are not currently checked in', 'returning_guest', true);

-- ============================================-- FLOW ACTIONS
-- ============================================
INSERT INTO context_manager_flowaction (name, action_type, configuration) VALUES
('Notify Reception', 'SEND_NOTIFICATION', '{"department": "reception", "priority": "normal"}'),
('Notify Room Service', 'SEND_NOTIFICATION', '{"department": "room_service", "priority": "normal"}'),
('Notify Kitchen', 'SEND_NOTIFICATION', '{"department": "kitchen", "priority": "normal"}'),
('Notify Management', 'SEND_NOTIFICATION', '{"department": "management", "priority": "high"}'),
('Log Check-in Request', 'LOG_REQUEST', '{"type": "checkin", "status": "pending"}'),
('Create Order', 'CREATE_ORDER', '{"type": "food", "status": "pending"}'),
('Send Confirmation SMS', 'SEND_SMS', '{"template": "confirmation"}');

-- ============================================
-- FLOW STEP TEMPLATES
-- Insert all steps first with order and without conditional/next step references.
-- These will be linked in the UPDATE section at the end.
-- ============================================

-- RANDOM GUEST FLOW
INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, "order", message_template, message_type, options, quick_reply_navigation) VALUES
((SELECT id FROM context_manager_flowtemplate WHERE category = 'random_guest'), 'Welcome Message', 0, 'Welcome! How can we assist you today?', 'quick-reply', '{"demo": "View Demo", "contact": "Contact Us"}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'random_guest'), 'Demo Services', 1, 'Here is a demo of our premium services. You can explore:', 'quick-reply', '{"explore_services": "Explore Hotel Services"}', '{"Back": "back", "Main Menu": "main_menu"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'random_guest'), 'Contact Details', 2, 'Contact Information:
📞 Phone: +1234567890
📧 Email: contact@grandpalace.com
📍 Address: 123 Palace Rd, Metropolis', 'text', '{}', '{"Back": "back", "Main Menu": "main_menu"}');

-- HOTEL CHECK-IN FLOW
INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, "order", message_template, message_type, options, quick_reply_navigation) VALUES
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Checkin Welcome', 0, 'Welcome to Grand Palace Hotel! Ready to begin your check-in process?', 'quick-reply', '{"proceed": "Proceed with Check-in"}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Guest Verification', 1, 'Let me verify your details:

Name: {guest_name}
Phone: {guest_phone}

Are these details correct?', 'quick-reply', '{"confirm": "Confirm Details", "update": "Update Details"}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Details Update', 2, 'Let me help you update your details.', 'text', '{}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Collect Full Name', 3, 'What is your full name?', 'text', '{}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'ID Type Selection', 4, 'Please select your ID type:', 'list-picker', '{"pan": "PAN Card", "aadhaar": "Aadhaar Card", "driving_license": "Driving License"}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'ID Photo Upload', 5, 'Please upload a clear photo of your selected ID document.', 'media', '{}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Room Request Placed', 6, 'Your room request has been placed and is being processed by our reception team.', 'text', '{}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Checkin Success', 7, 'Check-in successful! 🎉

Room: {room_number}
WiFi: {wifi_password}

How can we assist you today?', 'quick-reply', '{"services": "Explore Hotel Services"}', '{}');

-- HOTEL SERVICES FLOW
INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, "order", message_template, message_type, options, quick_reply_navigation) VALUES
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Services Menu', 0, 'How can we assist you today?', 'list-picker', '{"reception": "Reception", "room_service": "Room Service", "restaurant": "Cafe/Restaurant", "management": "Management"}', '{"Main Menu": "main_menu"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Reception Request', 1, 'What would you like to check with Reception?', 'text', '{}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Reception Confirmation', 2, 'Your request has been forwarded to reception. They will assist you shortly.', 'quick-reply', '{"services": "Back to Hotel Services"}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Room Service Options', 3, 'Select a room service option:', 'list-picker', '{"clean_room": "Clean Room", "maintenance": "Room Maintenance Request", "accessory": "Accessory Request"}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Room Service Details', 4, 'Please describe your service request in detail:', 'text', '{}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Room Service Confirmation', 5, 'Your service request has been submitted and will be deployed to your room shortly.', 'quick-reply', '{"services": "Back to Hotel Services"}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Restaurant Categories', 6, 'Available dining options (Timings: 07:00 AM - 11:00 PM):', 'list-picker', '{"breakfast": "Breakfast", "dessert": "Dessert", "chinese": "Chinese"}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Breakfast Menu', 7, 'Here are our breakfast options:', 'list-picker', '{"continental": "Continental Breakfast - $18", "american": "American Breakfast - $22", "healthy": "Healthy Bowl - $16"}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Dessert Menu', 8, 'Here are our dessert options:', 'list-picker', '{"chocolate_cake": "Chocolate Cake - $12", "ice_cream": "Premium Ice Cream - $8", "fruit_platter": "Fresh Fruit Platter - $10"}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Chinese Menu', 9, 'Here are our Chinese options:', 'list-picker', '{"sweet_sour": "Sweet & Sour Chicken - $24", "beef_broccoli": "Beef with Broccoli - $26", "kung_pao": "Kung Pao Chicken - $25"}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Order Confirmation', 10, 'Confirm your order for {selected_item}?', 'quick-reply', '{"confirm": "Confirm Order", "cancel": "Cancel"}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Order Success', 11, 'Your order has been placed successfully and will be delivered to your room!', 'quick-reply', '{"services": "Back to Hotel Services"}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Management Options', 12, 'Management Services:', 'list-picker', '{"complaint": "Raise a Complaint", "feedback": "General Feedback"}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Complaint Details', 13, 'Please describe your complaint in detail. We take all feedback seriously:', 'text', '{}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Feedback Input', 14, 'Please share your feedback about our services:', 'text', '{}', '{"Back": "back"}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Management Response', 15, 'Thank you for your feedback. Our management team will review this and get back to you within 24 hours.', 'quick-reply', '{"services": "Back to Hotel Services"}', '{}');

-- CHECKOUT FLOW
INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, "order", message_template, message_type, options, quick_reply_navigation) VALUES
((SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout'), 'Checkout Initiation', 0, 'Ready to check out? We hope you had a wonderful stay with us!', 'quick-reply', '{"proceed": "Proceed with Checkout"}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout'), 'Feedback Request', 1, 'Please share your feedback about your stay with us. Your opinion matters:', 'text', '{}', '{}'),
((SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout'), 'Feedback Thank You', 2, 'Thank you for your valuable feedback! We hope to welcome you back soon. Have a safe journey!', 'text', '{}', '{}');

-- RETURNING GUEST FLOW (SIMPLIFIED AND CORRECTED)
INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, "order", message_template, message_type, options, allowed_flow_categories, quick_reply_navigation) VALUES
((SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest'), 'Welcome Returning Guest', 0, 'Welcome back! How can we assist you today?', 'quick-reply', '{"hotel_checkin": "Check-in for New Stay", "random_guest": "Other Inquiries"}', '["hotel_checkin", "random_guest"]', '{}');


-- ============================================
-- UPDATE STEP REFERENCES
-- This section links all the steps together using their names,
-- making the script robust and independent of insertion order.
-- ============================================

-- Link linear (non-conditional) steps using next_step_template_id
-- ----------------------------------------------------------------
DO $$
DECLARE
    checkin_flow_id INT := (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin');
    services_flow_id INT := (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services');
    checkout_flow_id INT := (SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout');
BEGIN
    -- Hotel Check-in Flow
    UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = checkin_flow_id AND step_name = 'ID Type Selection') WHERE flow_template_id = checkin_flow_id AND step_name = 'Collect Full Name';
    UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = checkin_flow_id AND step_name = 'ID Photo Upload') WHERE flow_template_id = checkin_flow_id AND step_name = 'ID Type Selection';
    UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = checkin_flow_id AND step_name = 'Room Request Placed') WHERE flow_template_id = checkin_flow_id AND step_name = 'ID Photo Upload';
    UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = checkin_flow_id AND step_name = 'Checkin Success') WHERE flow_template_id = checkin_flow_id AND step_name = 'Room Request Placed';

    -- Hotel Services Flow
    UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Reception Confirmation') WHERE flow_template_id = services_flow_id AND step_name = 'Reception Request';
    UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Room Service Confirmation') WHERE flow_template_id = services_flow_id AND step_name = 'Room Service Details';
    UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Management Response') WHERE flow_template_id = services_flow_id AND step_name = 'Complaint Details';
    UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Management Response') WHERE flow_template_id = services_flow_id AND step_name = 'Feedback Input';

    -- Checkout Flow
    UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = checkout_flow_id AND step_name = 'Feedback Request') WHERE flow_template_id = checkout_flow_id AND step_name = 'Checkout Initiation';
    UPDATE context_manager_flowsteptemplate SET next_step_template_id = (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = checkout_flow_id AND step_name = 'Feedback Thank You') WHERE flow_template_id = checkout_flow_id AND step_name = 'Feedback Request';
END $$;

-- Link conditional steps using conditional_next_steps
-- ----------------------------------------------------
DO $$
DECLARE
    random_guest_flow_id INT := (SELECT id FROM context_manager_flowtemplate WHERE category = 'random_guest');
    checkin_flow_id INT := (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin');
    services_flow_id INT := (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services');
BEGIN
    -- Random Guest Flow
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('demo', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = random_guest_flow_id AND step_name = 'Demo Services'), 'contact', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = random_guest_flow_id AND step_name = 'Contact Details')) WHERE flow_template_id = random_guest_flow_id AND step_name = 'Welcome Message';
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('explore_services', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Services Menu')) WHERE flow_template_id = random_guest_flow_id AND step_name = 'Demo Services';

    -- Hotel Check-in Flow
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('proceed', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = checkin_flow_id AND step_name = 'Collect Full Name')) WHERE flow_template_id = checkin_flow_id AND step_name = 'Checkin Welcome';
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('confirm', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = checkin_flow_id AND step_name = 'ID Type Selection'), 'update', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = checkin_flow_id AND step_name = 'Details Update')) WHERE flow_template_id = checkin_flow_id AND step_name = 'Guest Verification';
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('services', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Services Menu')) WHERE flow_template_id = checkin_flow_id AND step_name = 'Checkin Success';

    -- Hotel Services Flow
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('reception', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Reception Request'), 'room_service', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Room Service Options'), 'restaurant', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Restaurant Categories'), 'management', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Management Options')) WHERE flow_template_id = services_flow_id AND step_name = 'Services Menu';
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('services', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Services Menu')) WHERE flow_template_id = services_flow_id AND step_name IN ('Reception Confirmation', 'Room Service Confirmation', 'Order Success', 'Management Response');
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('clean_room', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Room Service Details'), 'maintenance', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Room Service Details'), 'accessory', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Room Service Details')) WHERE flow_template_id = services_flow_id AND step_name = 'Room Service Options';
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('breakfast', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Breakfast Menu'), 'dessert', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Dessert Menu'), 'chinese', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Chinese Menu')) WHERE flow_template_id = services_flow_id AND step_name = 'Restaurant Categories';
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('continental', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation'), 'american', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation'), 'healthy', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation')) WHERE flow_template_id = services_flow_id AND step_name = 'Breakfast Menu';
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('chocolate_cake', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation'), 'ice_cream', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation'), 'fruit_platter', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation')) WHERE flow_template_id = services_flow_id AND step_name = 'Dessert Menu';
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('sweet_sour', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation'), 'beef_broccoli', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation'), 'kung_pao', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation')) WHERE flow_template_id = services_flow_id AND step_name = 'Chinese Menu';
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('confirm', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Order Success'), 'cancel', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Restaurant Categories')) WHERE flow_template_id = services_flow_id AND step_name = 'Order Confirmation';
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('complaint', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Complaint Details'), 'feedback', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = services_flow_id AND step_name = 'Feedback Input')) WHERE flow_template_id = services_flow_id AND step_name = 'Management Options';

    -- Checkout Flow
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('proceed', (SELECT id FROM context_manager_flowsteptemplate WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout') AND step_name = 'Feedback Request')) WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout') AND step_name = 'Checkout Initiation';
END $$;


-- ============================================-- HOTEL FLOW CONFIGURATIONS
-- ============================================
INSERT INTO context_manager_hotelflowconfiguration (hotel_id, flow_template_id, is_enabled, customization_data) VALUES
('00000000000000000000000000000001', (SELECT id FROM context_manager_flowtemplate WHERE category = 'random_guest'), true, '{}'),
('00000000000000000000000000000001', (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), true, '{}'),
('00000000000000000000000000000001', (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), true, '{}'),
('00000000000000000000000000000001', (SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout'), true, '{}'),
('00000000000000000000000000000001', (SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest'), true, '{}');

-- ============================================-- SCHEDULED MESSAGE TEMPLATES
-- ============================================
INSERT INTO context_manager_scheduledmessagetemplate (hotel_id, message_type, trigger_condition, message_template, is_active) VALUES
('00000000000000000000000000000001', 'checkout_reminder', '{"hours_before_checkout": 2}', 'Dear {guest_name}, this is a reminder that your checkout is at 11:00 AM. Would you like to extend your stay or provide feedback?', true),
('00000000000000000000000000000001', 'welcome', '{"trigger": "checkin_complete"}', 'Welcome to {hotel_name}, {guest_name}! Your check-in is complete. How can we make your stay memorable?', true),
('00000000000000000000000000000001', 'promo', '{"days_after_checkout": 30}', 'We miss you at {hotel_name}, {guest_name}! Book your next stay with us and get 20% off.', true);

-- ============================================-- VERIFICATION QUERIES
-- ============================================

-- Verify all flow templates are created
SELECT 'Flow Templates:' as section, category, name, is_active
FROM context_manager_flowtemplate
ORDER BY category;

-- Verify all flow steps are created with proper linking
SELECT
    'Flow Steps:' as section,
    ft.category as flow_category,
    fst.id,
    fst.step_name,
    fst.message_type,
    CASE WHEN fst.next_step_template_id IS NOT NULL THEN 'Has Next' ELSE 'End Step' END as has_next,
    CASE WHEN fst.conditional_next_steps IS NOT NULL AND fst.conditional_next_steps::text != '{}'::text THEN 'Has Conditions' ELSE 'Linear' END as transition_type,
    fst.conditional_next_steps
FROM context_manager_flowsteptemplate fst
JOIN context_manager_flowtemplate ft ON fst.flow_template_id = ft.id
ORDER BY ft.category, fst.id;

-- Verify hotel configurations
SELECT 'Hotel Configs:' as section, hfc.is_enabled, ft.category
FROM context_manager_hotelflowconfiguration hfc
JOIN context_manager_flowtemplate ft ON hfc.flow_template_id = ft.id
WHERE hfc.hotel_id = '00000000000000000000000000000001'
ORDER BY ft.category;

-- Count totals
SELECT 'Totals:' as section,
       (SELECT COUNT(*) FROM context_manager_flowtemplate) as flow_templates,
       (SELECT COUNT(*) FROM context_manager_flowsteptemplate) as flow_steps,
       (SELECT COUNT(*) FROM context_manager_placeholder) as placeholders,
       (SELECT COUNT(*) FROM context_manager_flowaction) as actions;
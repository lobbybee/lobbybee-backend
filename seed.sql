-- ============================================
-- COMPLETE HOTEL GUEST CRM FLOW SETUP (Django-Compatible Tables)
-- ============================================

-- First, truncate all context-related tables
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

-- ============================================
-- PLACEHOLDERS
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

-- ============================================
-- FLOW TEMPLATES
-- ============================================
INSERT INTO context_manager_flowtemplate (name, description, category, is_active) VALUES
('Random Guest Flow', 'Flow for random website visitors and demo users', 'random_guest', true),
('Hotel Check-in Flow', 'Complete check-in process for hotel guests', 'hotel_checkin', true),
('Hotel Services Flow', 'In-stay services and amenities', 'hotel_services', true),
('Checkout Flow', 'Guest checkout and feedback collection', 'checkout', true),
('Returning Guest Flow', 'Flow for guests who have stayed before but are not currently checked in', 'returning_guest', true);

-- ============================================
-- FLOW ACTIONS
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
-- ============================================

-- RANDOM GUEST FLOW (Updated for platform-level generic messages)
INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options, conditional_next_steps, allowed_flow_categories, quick_reply_navigation) VALUES
-- Step 1: Welcome (Made Generic)
((SELECT id FROM context_manager_flowtemplate WHERE category = 'random_guest'), 'Welcome Message', 'Welcome! How can we assist you today?', 'quick-reply', '{"demo": "View Demo", "contact": "Contact Us"}', '{"demo": 2, "contact": 3}', '[]', '{}'),
-- Step 2: Demo
((SELECT id FROM context_manager_flowtemplate WHERE category = 'random_guest'), 'Demo Services', 'Here is a demo of our premium services. You can explore:', 'list-picker', '{"room_service": "Room Service Demo", "restaurant": "Restaurant Demo", "reception": "Reception Demo"}', '{}', '["hotel_services"]', '{"Back": "back", "Main Menu": "main_menu"}'),
-- Step 3: Contact
((SELECT id FROM context_manager_flowtemplate WHERE category = 'random_guest'), 'Contact Details', 'Contact Information:
📞 Phone: +1234567890
📧 Email: contact@grandpalace.com
📍 Address: 123 Palace Rd, Metropolis', 'text', '{}', '{}', '[]', '{"Back": "back", "Main Menu": "main_menu"}');

-- HOTEL CHECK-IN FLOW
INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options, conditional_next_steps, allowed_flow_categories, quick_reply_navigation) VALUES
-- Step 1: Check-in Welcome
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Checkin Welcome', 'Welcome to Grand Palace Hotel! Ready to begin your check-in process?', 'quick-reply', '{"proceed": "Proceed with Check-in"}', '{"proceed": 5}', '[]', '{}'),
-- Step 2: Guest Verification (for existing users)
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Guest Verification', 'Let me verify your details:

Name: John Smith
Phone: +1234567890
Email: john@example.com

Are these details correct?', 'quick-reply', '{"confirm": "Confirm Details", "update": "Update Details"}', '{"confirm": 10, "update": 6}', '[]', '{}'),
-- Step 3: Check-in Request Processing
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Checkin Request', 'Processing your check-in request...', 'text', '{}', '{}', '[]', '{}'),
-- Step 4: Details Update Initiation
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Details Update', 'Let me help you update your details.', 'text', '{}', '{}', '[]', '{}'),
-- Step 5: Collect Full Name (new guest)
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Collect Full Name', 'What is your full name?', 'text', '{}', '{}', '[]', '{}'),
-- Step 6: ID Type Selection
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'ID Type Selection', 'Please select your ID type:', 'list-picker', '{"pan": "PAN Card", "aadhaar": "Aadhaar Card", "driving_license": "Driving License"}', '{"pan": 8, "aadhaar": 8, "driving_license": 8}', '[]', '{"Back": "back"}'),
-- Step 7: ID Photo Upload
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'ID Photo Upload', 'Please upload a clear photo of your selected ID document.', 'media', '{}', '{}', '[]', '{"Back": "back"}'),
-- Step 8: Room Request Placed
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Room Request Placed', 'Your room request has been placed and is being processed by our reception team.', 'text', '{}', '{}', '[]', '{}'),
-- Step 9: Check-in Success
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), 'Checkin Success', 'Check-in successful! 🎉

Room: 205
WiFi: LobbyBeeGuestWiFi
Contact: +1234567890

How can we assist you today?', 'quick-reply', '{"services": "Hotel Services"}', '{}', '["hotel_services"]', '{}');

-- HOTEL SERVICES FLOW
INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options, conditional_next_steps, allowed_flow_categories, quick_reply_navigation) VALUES
-- Step 1: Services Menu
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Services Menu', 'How can we assist you today?', 'list-picker', '{"reception": "Reception", "room_service": "Room Service", "restaurant": "Cafe/Restaurant", "management": "Management"}', '{"reception": 11, "room_service": 13, "restaurant": 18, "management": 25}', '["checkout"]', '{}'),

-- RECEPTION FLOW
-- Step 2: Reception Request
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Reception Request', 'What would you like to check with Reception?', 'text', '{}', '{}', '[]', '{"Back": "back"}'),
-- Step 3: Reception Confirmation
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Reception Confirmation', 'Your request has been forwarded to reception. They will assist you shortly.', 'quick-reply', '{"services": "Back to Hotel Services"}', '{}', '["hotel_services"]', '{}'),

-- ROOM SERVICE FLOW
-- Step 4: Room Service Options
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Room Service Options', 'Select a room service option:', 'list-picker', '{"clean_room": "Clean Room", "maintenance": "Room Maintenance Request", "accessory": "Accessory Request"}', '{"clean_room": 15, "maintenance": 15, "accessory": 15}', '[]', '{"Back": "back"}'),
-- Step 5: Room Service Details
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Room Service Details', 'Please describe your service request in detail:', 'text', '{}', '{}', '[]', '{"Back": "back"}'),
-- Step 6: Room Service Confirmation
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Room Service Confirmation', 'Your service request has been submitted and will be deployed to your room shortly.', 'quick-reply', '{"services": "Back to Hotel Services"}', '{}', '["hotel_services"]', '{}'),

-- RESTAURANT FLOW
-- Step 7: Restaurant Categories
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Restaurant Categories', 'Available dining options (Timings: 07:00 AM - 11:00 PM):', 'list-picker', '{"breakfast": "Breakfast", "dessert": "Dessert", "chinese": "Chinese"}', '{"breakfast": 19, "dessert": 20, "chinese": 21}', '[]', '{"Back": "back"}'),
-- Step 8: Breakfast Menu
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Breakfast Menu', 'Here are our breakfast options:', 'list-picker', '{"continental": "Continental Breakfast - $18", "american": "American Breakfast - $22", "healthy": "Healthy Bowl - $16"}', '{"continental": 22, "american": 22, "healthy": 22}', '[]', '{"Back": "back"}'),
-- Step 9: Dessert Menu
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Dessert Menu', 'Here are our dessert options:', 'list-picker', '{"chocolate_cake": "Chocolate Cake - $12", "ice_cream": "Premium Ice Cream - $8", "fruit_platter": "Fresh Fruit Platter - $10"}', '{"chocolate_cake": 22, "ice_cream": 22, "fruit_platter": 22}', '[]', '{"Back": "back"}'),
-- Step 10: Chinese Menu
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Chinese Menu', 'Here are our Chinese options:', 'list-picker', '{"sweet_sour": "Sweet & Sour Chicken - $24", "beef_broccoli": "Beef with Broccoli - $26", "kung_pao": "Kung Pao Chicken - $25"}', '{"sweet_sour": 22, "beef_broccoli": 22, "kung_pao": 22}', '[]', '{"Back": "back"}'),
-- Step 11: Order Confirmation
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Order Confirmation', 'Confirm your order?', 'quick-reply', '{"confirm": "Confirm Order", "cancel": "Cancel"}', '{"confirm": 23, "cancel": 18}', '[]', '{}'),
-- Step 12: Order Success
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Order Success', 'Your order has been placed successfully and will be delivered to your room!', 'quick-reply', '{"services": "Back to Hotel Services"}', '{}', '["hotel_services"]', '{}'),

-- MANAGEMENT FLOW
-- Step 13: Management Options
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Management Options', 'Management Services:', 'list-picker', '{"complaint": "Raise a Complaint", "feedback": "General Feedback"}', '{"complaint": 25, "feedback": 26}', '[]', '{"Back": "back"}'),
-- Step 14: Complaint Details
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Complaint Details', 'Please describe your complaint in detail. We take all feedback seriously:', 'text', '{}', '{}', '[]', '{"Back": "back"}'),
-- Step 15: Feedback Input
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Feedback Input', 'Please share your feedback about our services:', 'text', '{}', '{}', '[]', '{"Back": "back"}'),
-- Step 16: Management Response
((SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), 'Management Response', 'Thank you for your feedback. Our management team will review this and get back to you within 24 hours.', 'quick-reply', '{"services": "Back to Hotel Services"}', '{}', '["hotel_services"]', '{}');

-- CHECKOUT FLOW
INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options, conditional_next_steps, allowed_flow_categories, quick_reply_navigation) VALUES
-- Step 1: Checkout Initiation
((SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout'), 'Checkout Initiation', 'Ready to check out? We hope you had a wonderful stay with us!', 'quick-reply', '{"proceed": "Proceed with Checkout"}', '{"proceed": 29}', '[]', '{}'),
-- Step 2: Feedback Request
((SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout'), 'Feedback Request', 'Please share your feedback about your stay with us. Your opinion matters:', 'text', '{}', '{}', '[]', '{}'),
-- Step 3: Feedback Thank You
((SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout'), 'Feedback Thank You', 'Thank you for your valuable feedback! We hope to welcome you back soon. Have a safe journey!', 'text', '{}', '{}', '[]', '{}');

-- RETURNING GUEST FLOW (Updated for platform-level generic messages)
INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options, conditional_next_steps, allowed_flow_categories, quick_reply_navigation) VALUES
-- Step 1: Welcome returning guest (Made Generic)
((SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest'), 'Welcome Returning Guest', 'Welcome back! How can we assist you today?', 'quick-reply', '{"checkin": "Check-in for New Stay", "services": "Inquire About Services"}', '{"checkin": 2, "services": 3}', '[]', '{}'),

-- Step 2: Proceed to check-in
((SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest'), 'Proceed to Check-in', 'Great! Let me help you check in for your new stay.', 'text', '{}', '{}', '["hotel_checkin"]', '{}'),

-- Step 3: Services inquiry
((SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest'), 'Services Inquiry', 'We offer a range of services for our guests. How would you like to proceed?', 'list-picker', '{"book_now": "Book a Room Now", "contact": "Contact Reception"}', '{"book_now": 4, "contact": 5}', '[]', '{"Back": "back"}'),

-- Step 4: Book a room
((SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest'), 'Book a Room', 'You can book a room directly through our website or mobile app. Would you like me to send you the link?', 'quick-reply', '{"yes": "Yes, please", "no": "No, thanks"}', '{"yes": 6, "no": 7}', '[]', '{"Back": "back"}'),

-- Step 5: Contact reception
((SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest'), 'Contact Reception', 'I will connect you with our reception team who can assist you with your inquiry.', 'text', '{}', '{}', '[]', '{}'),

-- Step 6: Send booking link
((SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest'), 'Send Booking Link', 'Here is the link to book your stay: https://grandpalacehotel.com/book

Is there anything else I can assist you with today?', 'quick-reply', '{"main_menu": "Main Menu"}', '{}', '[]', '{}'),

-- Step 7: End conversation
((SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest'), 'End Conversation', 'Thank you for reaching out. We look forward to welcoming you back soon!', 'text', '{}', '{}', '[]', '{}');

-- ============================================
-- UPDATE NEXT STEP REFERENCES
-- ============================================

-- Random Guest Flow
UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'random_guest')
      AND step_name = 'Demo Services'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'random_guest')
  AND step_name = 'Welcome Message';

-- Hotel Check-in Flow - set linear progression where not conditional
UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin')
      AND step_name = 'Guest Verification'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin')
  AND step_name = 'Checkin Welcome';

UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin')
      AND step_name = 'ID Type Selection'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin')
  AND step_name = 'Collect Full Name';

UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin')
      AND step_name = 'ID Photo Upload'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin')
  AND step_name = 'ID Type Selection';

UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin')
      AND step_name = 'Room Request Placed'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin')
  AND step_name = 'ID Photo Upload';

UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin')
      AND step_name = 'Checkin Success'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin')
  AND step_name = 'Room Request Placed';

-- Hotel Services Flow
UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services')
      AND step_name = 'Reception Confirmation'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services')
  AND step_name = 'Reception Request';

UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services')
      AND step_name = 'Room Service Details'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services')
  AND step_name = 'Room Service Options';

UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services')
      AND step_name = 'Room Service Confirmation'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services')
  AND step_name = 'Room Service Details';

UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services')
      AND step_name = 'Management Response'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services')
  AND step_name = 'Complaint Details';

UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services')
      AND step_name = 'Management Response'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services')
  AND step_name = 'Feedback Input';

-- Checkout Flow
UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout')
      AND step_name = 'Feedback Request'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout')
  AND step_name = 'Checkout Initiation';

UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout')
      AND step_name = 'Feedback Thank You'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout')
  AND step_name = 'Feedback Request';

-- Returning Guest Flow
UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest')
      AND step_name = 'Proceed to Check-in'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest')
  AND step_name = 'Welcome Returning Guest';

UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest')
      AND step_name = 'Services Inquiry'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest')
  AND step_name = 'Welcome Returning Guest';

UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest')
      AND step_name = 'Book a Room'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest')
  AND step_name = 'Services Inquiry';

UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest')
      AND step_name = 'Contact Reception'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest')
  AND step_name = 'Services Inquiry';

UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest')
      AND step_name = 'Send Booking Link'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest')
  AND step_name = 'Book a Room';

UPDATE context_manager_flowsteptemplate
SET next_step_template_id = (
    SELECT id FROM context_manager_flowsteptemplate
    WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest')
      AND step_name = 'End Conversation'
)
WHERE flow_template_id = (SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest')
  AND step_name = 'Book a Room';

-- ============================================
-- HOTEL FLOW CONFIGURATIONS
-- ============================================
INSERT INTO context_manager_hotelflowconfiguration (hotel_id, flow_template_id, is_enabled, customization_data) VALUES
('a8a8a8a8a8a848a8a8a8a8a8a8a8a8a8', (SELECT id FROM context_manager_flowtemplate WHERE category = 'random_guest'), true, '{}'),
('a8a8a8a8a8a848a8a8a8a8a8a8a8a8a8', (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_checkin'), true, '{}'),
('a8a8a8a8a8a848a8a8a8a8a8a8a8a8a8', (SELECT id FROM context_manager_flowtemplate WHERE category = 'hotel_services'), true, '{}'),
('a8a8a8a8a8a848a8a8a8a8a8a8a8a8a8', (SELECT id FROM context_manager_flowtemplate WHERE category = 'checkout'), true, '{}'),
('a8a8a8a8a8a848a8a8a8a8a8a8a8a8a8', (SELECT id FROM context_manager_flowtemplate WHERE category = 'returning_guest'), true, '{}');

-- ============================================
-- SCHEDULED MESSAGE TEMPLATES
-- ============================================
INSERT INTO context_manager_scheduledmessagetemplate (hotel_id, message_type, trigger_condition, message_template, is_active) VALUES
('a8a8a8a8a8a848a8a8a8a8a8a8a8a8a8', 'checkout_reminder', '{"hours_before_checkout": 2}', 'Dear guest, checkout is at 11:00 AM. Would you like to extend your stay or provide feedback?', true),
('a8a8a8a8a8a848a8a8a8a8a8a8a8a8a8', 'welcome', '{"trigger": "checkin_complete"}', 'Welcome to Grand Palace Hotel! Your check-in is complete. How can we make your stay memorable?', true),
('a8a8a8a8a8a848a8a8a8a8a8a8a8a8a8', 'promo', '{"days_after_checkout": 30}', 'We miss you at Grand Palace Hotel! Book your next stay with us and get 20% off.', true);

-- ============================================
-- VERIFICATION QUERIES
-- ============================================

-- Verify all flow templates are created
SELECT 'Flow Templates:' as section, category, name, is_active
FROM context_manager_flowtemplate
ORDER BY category;

-- Verify all flow steps are created with proper linking
SELECT
    'Flow Steps:' as section,
    ft.category as flow_category,
    fst.step_name,
    fst.message_type,
    CASE WHEN fst.next_step_template_id IS NOT NULL THEN 'Has Next' ELSE 'End Step' END as has_next,
    CASE WHEN fst.conditional_next_steps IS NOT NULL AND fst.conditional_next_steps != '{}' THEN 'Has Conditions' ELSE 'Linear' END as transition_type
FROM context_manager_flowsteptemplate fst
JOIN context_manager_flowtemplate ft ON fst.flow_template_id = ft.id
ORDER BY ft.category, fst.id;

-- Verify hotel configurations
SELECT 'Hotel Configs:' as section, hfc.is_enabled, ft.category
FROM context_manager_hotelflowconfiguration hfc
JOIN context_manager_flowtemplate ft ON hfc.flow_template_id = ft.id
WHERE hfc.hotel_id = 'a8a8a8a8a8a848a8a8a8a8a8a8a8a8a8'
ORDER BY ft.category;

-- Count totals
SELECT 'Totals:' as section,
       (SELECT COUNT(*) FROM context_manager_flowtemplate) as flow_templates,
       (SELECT COUNT(*) FROM context_manager_flowsteptemplate) as flow_steps,
       (SELECT COUNT(*) FROM context_manager_placeholder) as placeholders,
       (SELECT COUNT(*) FROM context_manager_flowaction) as actions;

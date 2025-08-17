-- PostgreSQL seed script for LobbyBee
-- This script populates the database with essential data for a standard hotel setup.

-- Clear existing data from all relevant tables in the correct order to avoid FK constraints.
TRUNCATE TABLE
    context_manager_conversationmessage,
    context_manager_conversationcontext,
    context_manager_webhooklog,
    context_manager_flowstep,
    context_manager_hotelflowconfiguration,
    context_manager_flowsteptemplate_actions,
    context_manager_flowsteptemplate,
    context_manager_flowaction,
    context_manager_flowtemplate,
    context_manager_messagequeue,
    context_manager_scheduledmessagetemplate,
    guest_stay,
    guest_guestidentitydocument,
    guest_guest,
    hotel_department,
    hotel_room,
    hotel_roomcategory,
    hotel_hoteldocument,
    user_otp,
    user_user_groups,
    user_user_user_permissions,
    user_user,
    hotel_hotel
RESTART IDENTITY CASCADE;

DO $$
DECLARE
    -- Declare variables for IDs to make linking easier
    hotel_id UUID := 'a8a8a8a8-a8a8-48a8-a8a8-a8a8a8a8a8a8';
    
    -- Flow Template IDs
    ft_new_guest_discovery_id INT;
    ft_guest_checkin_id INT;
    ft_in_stay_services_id INT;
    ft_returning_guest_id INT;
    ft_main_menu_id INT;

    -- Flow Step Template IDs
    fst_new_welcome_id INT;
    fst_new_collect_name_id INT;
    fst_new_collect_email_id INT;
    fst_new_collect_phone_id INT;
    fst_new_collect_id_id INT;
    fst_new_success_id INT;
    
    fst_checkin_welcome_id INT;
    fst_checkin_confirm_name_id INT;

    fst_returning_welcome_id INT;
    fst_returning_history_id INT;

    fst_instay_main_menu_id INT;
    fst_instay_reception_menu_id INT;
    fst_instay_amenities_menu_id INT;
    fst_instay_towels_confirm_id INT;
    fst_instay_housekeeping_menu_id INT;
    fst_instay_clean_room_confirm_id INT;

    fst_fallback_main_menu_id INT;

BEGIN
    -- 1. Seed Super Admin User
    -- Password is 'lobbybee_admin_password'
    INSERT INTO user_user (password, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined, user_type, is_verified, is_active_hotel_user)
    VALUES ('pbkdf2_sha256$720000$HqYJtqI3xV9n$u/aOqjwj5s2h3yZp8q3y5s2h3yZp8q3y5s2h3yZp8q3y5s=', true, 'superadmin', 'Super', 'Admin', 'superadmin@lobbybee.com', true, true, NOW(), 'superadmin', true, true);

    -- 2. Seed Hotel
    INSERT INTO hotel_hotel (id, name, description, address, city, state, country, pincode, phone, email, status, is_verified, is_active, registration_date, check_in_time, time_zone, unique_qr_code)
    VALUES (hotel_id, 'Grand Palace Hotel', 'A luxurious stay in the heart of the city.', '123 Palace Rd', 'Metropolis', 'State', 'Country', '12345', '+1234567890', 'contact@grandpalace.com', 'verified', true, true, NOW(), '14:00:00', 'UTC', 'grand_palace_hotel_qr');

    -- Seed Rooms, Guests, and Stays to enable testing all flows
    INSERT INTO hotel_roomcategory (hotel_id, name, description, base_price, max_occupancy, amenities, created_at)
    VALUES (hotel_id, 'Deluxe Suite', 'A spacious suite with a city view.', 250.00, 2, '["wifi", "tv", "ac"]', NOW());

    INSERT INTO hotel_room (hotel_id, room_number, category_id, floor, status)
    VALUES (hotel_id, '205', (SELECT id FROM hotel_roomcategory WHERE name='Deluxe Suite' AND hotel_id=hotel_id), 2, 'occupied');

    -- Add a returning guest (with a past, completed stay)
    INSERT INTO guest_guest (whatsapp_number, full_name, email, loyalty_points, status)
    VALUES ('+11111111111', 'Sarah Johnson', 'sarah.j@example.com', 2450, 'checked_out');

    INSERT INTO guest_stay (hotel_id, guest_id, room_id, check_in_date, check_out_date, status)
    VALUES (
        hotel_id,
        (SELECT id FROM guest_guest WHERE whatsapp_number='+11111111111'),
        (SELECT id FROM hotel_room WHERE room_number='205' AND hotel_id=hotel_id),
        NOW() - INTERVAL '30 days',
        NOW() - INTERVAL '27 days',
        'completed'
    );

    -- Add an in-stay guest (with an active stay)
    INSERT INTO guest_guest (whatsapp_number, full_name, email, loyalty_points, status)
    VALUES ('+22222222222', 'John Doe', 'john.d@example.com', 500, 'checked_in');

    INSERT INTO guest_stay (hotel_id, guest_id, room_id, check_in_date, check_out_date, status)
    VALUES (
        hotel_id,
        (SELECT id FROM guest_guest WHERE whatsapp_number='+22222222222'),
        (SELECT id FROM hotel_room WHERE room_number='205' AND hotel_id=hotel_id),
        NOW() - INTERVAL '1 day',
        NOW() + INTERVAL '2 days',
        'active'
    );

    -- 3. Seed Flow Templates
    INSERT INTO context_manager_flowtemplate (name, description, category, is_active) VALUES
        ('New Guest Discovery (Interactive)', 'Guides a new user through account creation.', 'new_guest_discovery_interactive', true),
        ('Guest Check-in', 'Handles check-in for guests who scanned a QR code.', 'guest_checkin', true),
        ('In-Stay Services', 'Main menu for checked-in guests.', 'in_stay_services', true),
        ('Returning Guest', 'Menu for known guests without an active stay.', 'returning_guest', true),
        ('Main Menu (Fallback)', 'A generic main menu for session resets.', 'main_menu', true)
    RETURNING id, id, id, id, id INTO ft_new_guest_discovery_id, ft_guest_checkin_id, ft_in_stay_services_id, ft_returning_guest_id, ft_main_menu_id;

    -- 4. Seed Flow Step Templates
    
    -- New Guest Discovery Flow
    INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options) VALUES
        (ft_new_guest_discovery_id, 'Interactive Welcome', '👋 Welcome to [Hotel Network]! I see you''re new here.\n\n🏨 What would you like to do?', 'INTERACTIVE_MENU', '{"1": "Create Guest Account", "2": "Take Demo Tour"}') RETURNING id INTO fst_new_welcome_id;
    INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options) VALUES
        (ft_new_guest_discovery_id, 'Collect Full Name', '📝 Let''s create your account!\nPlease share your full name:', 'TEXT', '{}') RETURNING id INTO fst_new_collect_name_id;
    INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options) VALUES
        (ft_new_guest_discovery_id, 'Collect Email', '📧 Great! Now your email address:', 'TEXT', '{}') RETURNING id INTO fst_new_collect_email_id;
    INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options) VALUES
        (ft_new_guest_discovery_id, 'Collect Phone Number', '📱 Your phone number:', 'TEXT', '{}') RETURNING id INTO fst_new_collect_phone_id;
    INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options) VALUES
        (ft_new_guest_discovery_id, 'Collect ID Document', '🆔 Please upload your ID document (photo)\n📸 Send as image', 'TEXT', '{}') RETURNING id INTO fst_new_collect_id_id;
    INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options) VALUES
        (ft_new_guest_discovery_id, 'Interactive Account Success', '✅ Account created successfully!\nYour guest ID: {guest_id}\n\n🏨 What''s next?', 'INTERACTIVE_MENU', '{"1": "Take Demo Tour", "2": "Find Hotels"}') RETURNING id INTO fst_new_success_id;

    -- Guest Check-in Flow
    INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options) VALUES
        (ft_guest_checkin_id, 'Check-in Start', 'Welcome to {hotel_name}! To check in, please confirm your full name.', 'TEXT', '{}') RETURNING id INTO fst_checkin_welcome_id;
    INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options) VALUES
        (ft_guest_checkin_id, 'Check-in Confirmation', 'Thanks, {full_name}! Your check-in is complete.', 'TEXT', '{}') RETURNING id INTO fst_checkin_confirm_name_id;

    -- Returning Guest Flow
    INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options) VALUES
        (ft_returning_guest_id, 'Returning Guest Welcome', '👋 Welcome back, {guest_name}!\n\n🏨 Your Account Options:\n1️⃣ View Stay History\n2️⃣ Make New Reservation\n3️⃣ Loyalty Points: {loyalty_points}', 'INTERACTIVE_MENU', '{"1": "View Stay History", "2": "Make New Reservation"}') RETURNING id INTO fst_returning_welcome_id;
    INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options) VALUES
        (ft_returning_guest_id, 'Stay History List', '📚 Your Stay History\n\nRecent stays:\n1️⃣ Grand Palace Hotel - Dec 2024', 'INTERACTIVE_MENU', '{"1": "View Details"}') RETURNING id INTO fst_returning_history_id;

    -- In-Stay Services Flow
    INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options) VALUES
        (ft_in_stay_services_id, 'In-Stay Main Menu', '🏨 Welcome back, {guest_name}!\nRoom {room_number} | {hotel_name}\n\n🛎️ How can I help you today?', 'INTERACTIVE_MENU', '{"1": "Reception Services", "2": "Housekeeping", "3": "Room Service"}') RETURNING id INTO fst_instay_main_menu_id;
    INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options) VALUES
        (ft_in_stay_services_id, 'Reception Services Menu', '🏨 Reception Services', 'INTERACTIVE_MENU', '{"1": "Extra Towels/Amenities", "2": "Wake-up Call"}') RETURNING id INTO fst_instay_reception_menu_id;
    INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options) VALUES
        (ft_in_stay_services_id, 'Amenities Menu', '🛁 Amenities Request\nWhat do you need?', 'INTERACTIVE_MENU', '{"1": "Extra Towels", "2": "Extra Pillows"}') RETURNING id INTO fst_instay_amenities_menu_id;
    INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options) VALUES
        (ft_in_stay_services_id, 'Extra Towels Confirmation', '✅ Extra towels requested for Room {room_number}\n⏰ Delivery time: 15-20 minutes\n\nAnything else?', 'INTERACTIVE_MENU', '{"1": "Back to Reception", "2": "Main Menu"}') RETURNING id INTO fst_instay_towels_confirm_id;
    INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options) VALUES
        (ft_in_stay_services_id, 'Housekeeping Menu', '🧹 Housekeeping Services', 'INTERACTIVE_MENU', '{"1": "Clean Room Now", "2": "Schedule Cleaning"}') RETURNING id INTO fst_instay_housekeeping_menu_id;
    INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options) VALUES
        (ft_in_stay_services_id, 'Clean Room Confirmation', '🧹 Immediate room cleaning requested\n⏰ Staff will arrive in 10-15 minutes', 'TEXT', '{}') RETURNING id INTO fst_instay_clean_room_confirm_id;

    -- Main Menu (Fallback)
    INSERT INTO context_manager_flowsteptemplate (flow_template_id, step_name, message_template, message_type, options) VALUES
        (ft_main_menu_id, 'Main Menu', 'Welcome back! How can I help you?', 'INTERACTIVE_MENU', '{"1": "Room Service", "2": "Housekeeping"}') RETURNING id INTO fst_fallback_main_menu_id;

    -- 5. Link Flow Step Templates
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('1', fst_new_collect_name_id) WHERE id = fst_new_welcome_id;
    UPDATE context_manager_flowsteptemplate SET next_step_template_id = fst_new_collect_email_id WHERE id = fst_new_collect_name_id;
    UPDATE context_manager_flowsteptemplate SET next_step_template_id = fst_new_collect_phone_id WHERE id = fst_new_collect_email_id;
    UPDATE context_manager_flowsteptemplate SET next_step_template_id = fst_new_collect_id_id WHERE id = fst_new_collect_phone_id;
    UPDATE context_manager_flowsteptemplate SET next_step_template_id = fst_new_success_id WHERE id = fst_new_collect_id_id;

    UPDATE context_manager_flowsteptemplate SET next_step_template_id = fst_checkin_confirm_name_id WHERE id = fst_checkin_welcome_id;

    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('1', fst_returning_history_id) WHERE id = fst_returning_welcome_id;

    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('1', fst_instay_reception_menu_id, '2', fst_instay_housekeeping_menu_id) WHERE id = fst_instay_main_menu_id;
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('1', fst_instay_amenities_menu_id) WHERE id = fst_instay_reception_menu_id;
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('1', fst_instay_towels_confirm_id) WHERE id = fst_instay_amenities_menu_id;
    UPDATE context_manager_flowsteptemplate SET conditional_next_steps = jsonb_build_object('1', fst_instay_clean_room_confirm_id) WHERE id = fst_instay_housekeeping_menu_id;

END $$;

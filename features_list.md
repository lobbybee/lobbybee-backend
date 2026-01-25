# LobbyBee Verified Features

## Module 1: User Management (`user`)
### Authentication & Registration
1.  **User Login**
    *   Authenticates credentials (username/password)
    *   Issues JWT Access & Refresh tokens
    *   Updates last login timestamp
2.  **Token Refresh**
    *   Generates new Access token using valid Refresh token
3.  **User Logout**
    *   Blacklists Refresh token to prevent reuse
4.  **Hotel Registration**
    *   Creates new Hotel entity (Pending status)
    *   Creates Hotel Admin user
    *   Triggers email OTP verification
5.  **OTP Verification**
    *   Verifies email ownership
    *   Activates verified account
6.  **Resend OTP**
    *   Generates new 6-digit code
    *   Enforces max 5 retry limit
7.  **Username Generator**
    *   Creates unique suggestions based on hotel name (e.g., `hotel_admin123`)

### Password Management
8.  **Password Reset Request**
    *   Initiates flow with email input
    *   Sends OTP if user exists
9.  **Password Reset Confirmation**
    *   Validates OTP and sets new password
10. **Change Password**
    *   Securely updates password for logged-in users

### Staff Management
11. **List Hotel Staff**
    *   Displays all users linked to hotel
    *   Filters by active/inactive status
12. **Role Support**
    *   **Manager**: Full operational access
    *   **Receptionist**: Front-desk operations
    *   **Department Staff**: Restricted to specific depts (Housekeeping, Room Service, Restaurant)
13. **Create Staff Account**
    *   Creates profiles with specific roles
    *   Auto-verifies staff emails
14. **Bulk Create Staff**
    *   Imports multiple staff accounts from single JSON payload
15. **Update Staff Profile**
    *   Modifies department, phone, and active status
16. **Deactivate Staff**
    *   Soft-deletes user access

### Platform Administration
17. **Platform Hotel Creation**
    *   Manual overrides for instant Hotel + Admin creation
    *   Skips OTP flow for immediate access
18. **List Platform Users**
    *   View all Staff/SuperAdmin accounts

---

## Module 2: Guest & Stay Management (`guest`)
### Guest Profiles
19. **Global Guest Search**
    *   Find by Name, Phone, ID Number, or Email
20. **Create Guest Profile**
    *   Registers new guest with photo
    *   Tracks **Nationality**, **Preferred Language**, and **WhatsApp Status**
    *   Prevents duplicate phone numbers
21. **Guest Booking History**
    *   Retrieves all past stays for a specific guest
22. **Identity Verification**
    *   Supports: **Aadhaar**, **Driving License**, **Voter ID**, **National ID**
    *   Tracks **Verified By** (Audit trail of staff member)

### Stay Operations
23. **Walk-in Check-in (Offline)**
    *   Creates immediate active stay
    *   Assigns room instantly
24. **Verify Mobile Check-in**
    *   Confirms pending online requests
    *   Validates ID documents
    *   Triggers "Check-in Successful" WhatsApp notification
25. **24-Hour Stay Mode**
    *   Logic to handle flexible check-in/out cycles
26. **Internal Guest Rating**
    *   Staff-only rating (1-5) and notes for guest behavior
27. **Guest Checkout**
    *   Completes stay record
    *   Auto-updates room status to 'Cleaning'
    *   Triggers "Feedback Request" WhatsApp notification
28. **Extend Stay**
    *   Modifies checkout date & Recalculates billing
29. **Reject Mobile Check-in**
    *   Cancels pending requests with reason
30. **View Pending Stays**
    *   Dashboard for mobile check-ins awaiting verification
31. **View In-House Guests**
    *   List of all currently checked-in users

---

## Module 3: Hotel Operations (`hotel`)
### Hotel Management
32. **Get Hotel Profile**
    *   Retrieves details including **Google Review Link** & **Timezone**
33. **Update Hotel Profile**
    *   Modifies branding, address, map location (Lat/Long), and contacts
34. **Platform Hotel List**
    *   (Admin) View all system hotels
35. **Verify Hotel**
    *   (Admin) Mark hotel as verified
36. **Reject Hotel**
    *   (Admin) Deny registration with notes
37. **Toggle Hotel Access**
    *   (Admin) Pause or resume hotel service

### Rooms & Inventory
38. **List Rooms**
    *   View rooms with status (Clean/Dirty/Occupied/Maintenance/Out-of-Order)
    *   Filter by Floor or Category
39. **Create Room**
    *   Add single room unit
40. **Bulk Create Rooms**
    *   Range Mode: Add sequence (e.g., 101-110)
    *   Multi-Range Mode: Add multiple sequences (e.g., 101-110, 201-210)
    *   Supports alphanumeric formats (e.g., F-100)
41. **List Floors**
    *   Get all configured floor numbers
42. **Update Room Status**
    *   Cycle status: Available -> Cleaning -> Maintenance -> **Out of Order**

### Room Categories
43. **List Categories**
    *   View definitions (Deluxe, Suite, etc.)
44. **Create Category**
    *   Define new room type with Max Occupancy & Base Price
    *   **Bulk Feature**: Create multiple categories in one batch

### Documents & Assets
45. **Upload Document**
    *   Store verification files (Licenses, GST)
46. **Update Document**
    *   Replace existing file assets
47. **Send Payment QR**
    *   WhatsApp trigger: Sends QR image to guest
48. **Toggle QR Active**
    *   Enable/Disable specific payment codes
49. **Smart WiFi Fetch**
    *   Retrieve credentials specific to Room > Category > Floor hierarchy
50. **List Floor WiFi**
    *   View credentials for entire floor

---

## Module 4: Chat & Communication (`chat`)
### Real-time Communication
51. **WebSocket Connection**
    *   Auto-joins "Hotel" and "Department" groups
52. **Live Event Broadcasting**
    *   Delivers Text, Image, Video, Audio, Document messages
    *   Broadcasts Staff Online/Offline status & Typing indicators
    *   Updates participant lists on join/leave

### Conversation Management
53. **Context-Aware Conversations**
    *   Types: **Service**, **Demo**, **Check-in**, **Feedback**, **General**
54. **Request Fulfillment Tracking**
    *   Staff can mark chat requests as "Fulfilled" with notes
55. **List Conversations**
    *   View active chats filtered by Department (Reception, Housekeeping, etc.)
56. **Start Conversation**
    *   Manually initiate chat via phone number
57. **Close Conversation**
    *   Mark as resolved (triggers optional feedback flow)
58. **Mark Messages Read**
    *   Bulk update status for all messages in chat
59. **Upload Media**
    *   Handle Images, PDFs, Audio, Video
60. **WhatsApp Routing Bot**
    *   Analyzes intent -> Routes to Automated Flows or Human Agent
    *   Logs Webhook Attempts for debugging

---

## Module 5: Notifications (`notifications`)
### Notification System
61. **Actionable Notifications**
    *   Supports Deep Links (URL + Label) for direct navigation
62. **Aggregate Notifications**
    *   Unified view of Personal + Group alerts
63. **Create Notification**
    *   Send to Single User, Hotel Staff, or Platform
64. **Filter Personal/Group**
    *   Separate views for direct messages vs broadcasts
65. **Mark Read (Single/Bulk)**
    *   Clear unread status for easy inbox management

---

## Module 6: Payments (`payments`)
### Financial Operations
66. **List Transactions**
    *   View records of Subscriptions/Charges
67. **Create Transaction**
    *   Manual entry for offline payments
68. **Purchase Plan**
    *   Initiate subscription upgrade (Trial/Standard)
69. **Process Payment**
    *   Simulate gateway callback (Activate Plan)
70. **View Subscription**
    *   Check active plan details & days remaining

---

## Module 7: Statistics (`hotelstat` & `admin_stat`)
### Hotel Analytics
71. **Dashboard Overview**
    *   KPIs: Occupancy %, Active Stays, Pending Actions
72. **Occupancy Analytics**
    *   Deep dive by Category & Floor
    *   Monthly trend graphs
73. **Guest Demographics**
    *   New vs Repeat, Nationality Stats, Loyalty Points
74. **Room Status Stats**
    *   Breakdown: Clean vs Dirty vs Maintenance
75. **Performance Metrics**
    *   Avg Stay Duration, Conversion Rates
76. **History Logs**
    *   Complete archive of Guest Visits & Room Usage

### Platform Analytics
77. **Platform Overview**
    *   Total Revenue, Hotel Counts, Global Subscriptions
78. **Growth Metrics**
    *   Hotel registration trends

---

## Module 8: Flag System (`flag_system`)
### Security & Safety
79. **List Flagged Guests**
    *   View all active alerts
80. **Create Flag**
    *   **Police Flag**: Mark high-risk official incidents
    *   **Hotel Flag**: Internal blacklist/watchlist
    *   **Global Note**: Public alerts visible to network
81. **Remove Flag**
    *   Resolve/Deactivate alert with audit trail (Reset By)
82. **Search Guest Safety**
    *   Pre-check-in validation endpoint for safety status

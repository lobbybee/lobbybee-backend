# LobbyBee Hotel Admin API Documentation

This document provides a comprehensive guide for frontend developers on how to integrate with the LobbyBee backend to build the flow customization interface for hotel admins.

## Authentication

All hotel admin API endpoints require token-based authentication. The `Authorization` header must be included in all requests with the value `Bearer <your_auth_token>`.

---

## API Endpoints

### Hotel Flow Configurations

These endpoints allow hotel admins to view and customize the flows that have been assigned to their hotel.

#### 1. List Hotel Flow Configurations

-   **Endpoint:** `/api/context/hotels/<uuid:hotel_id>/flow-configurations/`
-   **Method:** `GET`
-   **Description:** Retrieves a list of all flow templates available to the specified hotel.
-   **Success Response (200 OK):**
    ```json
    [
        {
            "id": 1,
            "hotel": "a8a6d3a0-3e3e-4c8a-8f8f-2f2f2f2f2f2f",
            "flow_template": {
                "id": 1,
                "name": "Check-in Flow",
                "description": "Standard guest check-in process."
            },
            "is_active": true,
            "customization_data": {}
        }
    ]
    ```

#### 2. View a Detailed Flow

-   **Endpoint:** `/api/context/hotels/<uuid:hotel_id>/flows/<int:template_id>/`
-   **Method:** `GET`
-   **Description:** Provides a detailed view of a specific flow template, including all its steps and any customizations made by the hotel.
-   **Success Response (200 OK):**
    ```json
    {
        "id": 1,
        "name": "Check-in Flow",
        "description": "Standard guest check-in process.",
        "steps": [
            {
                "id": 1,
                "step_name": "Welcome Message",
                "message_type": "text",
                "message_body": "Welcome to our hotel! Please reply with your booking ID.",
                "order": 1
            }
        ]
    }
    ```

#### 3. Customize a Flow

-   **Endpoint:** `/api/context/hotels/<uuid:hotel_id>/flows/<int:template_id>/customize/`
-   **Methods:** `PUT`, `PATCH`
-   **Description:** Allows a hotel admin to customize a flow template.
-   **Request Body:**
    ```json
    {
        "customization_data": {
            "welcome_message": "Welcome to The Grand Hotel! Please provide your booking reference."
        }
    }
    ```
-   **Success Response (200 OK):**
    ```json
    {
        "id": 1,
        "hotel": "a8a6d3a0-3e3e-4c8a-8f8f-2f2f2f2f2f2f",
        "flow_template": 1,
        "is_active": true,
        "customization_data": {
            "welcome_message": "Welcome to The Grand Hotel! Please provide your booking reference."
        }
    }
    ```

---

### Flow Steps

These endpoints are for managing the individual steps of a flow for a specific hotel.

#### 1. List and Create Flow Steps

-   **Endpoint:** `/api/context/hotels/<uuid:hotel_id>/flow-steps/`
-   **Methods:** `GET`, `POST`

#### 2. Retrieve, Update, and Delete a Flow Step

-   **Endpoint:** `/api/context/hotels/<uuid:hotel_id>/flow-steps/<str:step_id>/`
-   **Methods:** `GET`, `PUT`, `PATCH`, `DELETE`

---

### Scheduled Message Templates

These endpoints manage message templates that can be scheduled to be sent to guests.

#### 1. List and Create Scheduled Message Templates

-   **Endpoint:** `/api/context/hotels/<uuid:hotel_id>/message-templates/`
-   **Methods:** `GET`, `POST`

#### 2. Retrieve, Update, and Delete a Scheduled Message Template

-   **Endpoint:** `/api/context/hotels/<uuid:hotel_id>/message-templates/<int:template_id>/`
-   **Methods:** `GET`, `PUT`, `PATCH`, `DELETE`

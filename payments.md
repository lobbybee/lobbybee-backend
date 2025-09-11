# Payments API Specification

This document outlines the API endpoints for the payment and subscription management system in the LobbyBee Hotel CRM.

## Overview

The payment system manages subscription plans, transactions, and hotel subscriptions. It provides endpoints for both hotel users (to view their subscription) and platform staff (to manage subscriptions and transactions).

## Authentication

All endpoints require authentication using JWT tokens. Platform staff have broader access rights than hotel users.

## Models

### SubscriptionPlan

```json
{
  "id": "uuid",
  "name": "string",
  "plan_type": "trial|standard",
  "price": "decimal",
  "duration_days": "integer",
  "description": "string",
  "is_active": "boolean",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### Transaction

```json
{
  "id": "uuid",
  "hotel": "hotel_id",
  "plan": "plan_id",
  "amount": "decimal",
  "transaction_type": "subscription|manual",
  "status": "pending|completed|failed|cancelled",
  "transaction_id": "string",
  "notes": "string",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### HotelSubscription

```json
{
  "id": "uuid",
  "hotel": "hotel_id",
  "plan": "plan_id",
  "start_date": "datetime",
  "end_date": "datetime",
  "is_active": "boolean",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

## Hotel User Accessible Endpoints

### Subscription Plans

#### List Subscription Plans
- **URL**: `/plans/`
- **Method**: `GET`
- **Permission**: Authenticated users
- **Description**: Retrieve all active subscription plans
- **Response**:
  ```json
  [
    {
      "id": "uuid",
      "name": "Trial Plan",
      "plan_type": "trial",
      "price": "0.00",
      "duration_days": 14,
      "description": "Free trial plan for 14 days",
      "is_active": true,
      "created_at": "2025-09-10T12:00:00Z",
      "updated_at": "2025-09-10T12:00:00Z"
    }
  ]
  ```

#### Retrieve Subscription Plan
- **URL**: `/plans/{id}/`
- **Method**: `GET`
- **Permission**: Authenticated users
- **Description**: Retrieve a specific subscription plan

### Transactions

#### List Own Transactions
- **URL**: `/transactions/`
- **Method**: `GET`
- **Permission**: Hotel users only
- **Description**: Retrieve own transactions
- **Query Parameters**:
  - `plan`: Filter by plan ID
  - `transaction_type`: Filter by transaction type
  - `status`: Filter by status

#### Retrieve Own Transaction
- **URL**: `/transactions/{id}/`
- **Method**: `GET`
- **Permission**: Hotel users only
- **Description**: Retrieve a specific own transaction

### Hotel Subscriptions

#### List Own Subscriptions
- **URL**: `/subscriptions/`
- **Method**: `GET`
- **Permission**: Hotel users only
- **Description**: Retrieve own subscriptions

#### Retrieve Own Subscription
- **URL**: `/subscriptions/{id}/`
- **Method**: `GET`
- **Permission**: Hotel users only
- **Description**: Retrieve a specific own subscription

#### Retrieve My Subscription
- **URL**: `/subscriptions/my_subscription/`
- **Method**: `GET`
- **Permission**: Hotel users only
- **Description**: Retrieve the authenticated hotel user's subscription
- **Response**:
  ```json
  {
    "id": "uuid",
    "hotel": {
      "id": "hotel_id",
      "name": "Hotel Name",
      // ... other hotel fields
    },
    "plan": {
      "id": "plan_id",
      "name": "Standard Plan",
      "plan_type": "standard",
      "price": "99.99",
      "duration_days": 30,
      // ... other plan fields
    },
    "start_date": "2025-09-10T12:00:00Z",
    "end_date": "2025-10-10T12:00:00Z",
    "is_active": true,
    "is_expired": false,
    "days_until_expiry": 30,
    "created_at": "2025-09-10T12:00:00Z",
    "updated_at": "2025-09-10T12:00:00Z"
  }
  ```

## Platform Admin Accessible Endpoints

### Subscription Plans

#### List Subscription Plans
- **URL**: `/plans/`
- **Method**: `GET`
- **Permission**: Authenticated users
- **Description**: Retrieve all active subscription plans
- **Response**:
  ```json
  [
    {
      "id": "uuid",
      "name": "Trial Plan",
      "plan_type": "trial",
      "price": "0.00",
      "duration_days": 14,
      "description": "Free trial plan for 14 days",
      "is_active": true,
      "created_at": "2025-09-10T12:00:00Z",
      "updated_at": "2025-09-10T12:00:00Z"
    }
  ]
  ```

#### Retrieve Subscription Plan
- **URL**: `/plans/{id}/`
- **Method**: `GET`
- **Permission**: Authenticated users
- **Description**: Retrieve a specific subscription plan

#### Create Subscription Plan
- **URL**: `/plans/`
- **Method**: `POST`
- **Permission**: Platform staff only
- **Description**: Create a new subscription plan
- **Request Body**:
  ```json
  {
    "name": "string",
    "plan_type": "trial|standard",
    "price": "decimal",
    "duration_days": "integer",
    "description": "string",
    "is_active": "boolean"
  }
  ```

#### Update Subscription Plan
- **URL**: `/plans/{id}/`
- **Method**: `PUT`/`PATCH`
- **Permission**: Platform staff only
- **Description**: Update a subscription plan

#### Delete Subscription Plan
- **URL**: `/plans/{id}/`
- **Method**: `DELETE`
- **Permission**: Platform staff only
- **Description**: Delete a subscription plan

### Transactions

#### List All Transactions
- **URL**: `/transactions/`
- **Method**: `GET`
- **Permission**: Platform staff only
- **Description**: Retrieve all transactions
- **Query Parameters**:
  - `hotel`: Filter by hotel ID
  - `plan`: Filter by plan ID
  - `transaction_type`: Filter by transaction type
  - `status`: Filter by status

#### Retrieve Any Transaction
- **URL**: `/transactions/{id}/`
- **Method**: `GET`
- **Permission**: Platform staff only
- **Description**: Retrieve any specific transaction

#### Create Transaction (Manual)
- **URL**: `/transactions/`
- **Method**: `POST`
- **Permission**: Platform staff only
- **Description**: Manually create a transaction record
- **Request Body**:
  ```json
  {
    "hotel": "hotel_id",
    "plan": "plan_id",
    "amount": "decimal",
    "transaction_type": "manual",
    "status": "pending|completed|failed|cancelled",
    "transaction_id": "string",
    "notes": "string"
  }
  ```

#### Update Transaction
- **URL**: `/transactions/{id}/`
- **Method**: `PUT`/`PATCH`
- **Permission**: Platform staff only
- **Description**: Update a transaction

#### Delete Transaction
- **URL**: `/transactions/{id}/`
- **Method**: `DELETE`
- **Permission**: Platform staff only
- **Description**: Delete a transaction

### Hotel Subscriptions

#### List All Subscriptions
- **URL**: `/subscriptions/`
- **Method**: `GET`
- **Permission**: Platform staff only
- **Description**: Retrieve all subscriptions

#### Retrieve Any Subscription
- **URL**: `/subscriptions/{id}/`
- **Method**: `GET`
- **Permission**: Platform staff only
- **Description**: Retrieve any specific subscription

#### Create Subscription
- **URL**: `/subscriptions/create_subscription/`
- **Method**: `POST`
- **Permission**: Platform staff only
- **Description**: Create a new subscription for a hotel
- **Request Body**:
  ```json
  {
    "hotel": "hotel_id",
    "plan": "plan_id"
  }
  ```

#### Extend Subscription
- **URL**: `/subscriptions/extend_subscription/`
- **Method**: `POST`
- **Permission**: Platform staff only
- **Description**: Extend an existing subscription
- **Request Body**:
  ```json
  {
    "hotel": "hotel_id",
    "days": 30  // Optional, defaults to 30
  }
  ```

#### Update Subscription
- **URL**: `/subscriptions/{id}/`
- **Method**: `PUT`/`PATCH`
- **Permission**: Platform staff only
- **Description**: Update a subscription

#### Delete Subscription
- **URL**: `/subscriptions/{id}/`
- **Method**: `DELETE`
- **Permission**: Platform staff only
- **Description**: Delete a subscription

## Permissions Summary

| Role | Access Level | Description |
|------|-------------|-------------|
| Hotel Admin | Read-only | Can view subscription plans and their own subscription/transactions |
| Platform Staff | Full access | Can manage all aspects of subscriptions and transactions |
| Platform Admin | Full access | Can manage all aspects of subscriptions and transactions |

## Error Responses

Standard DRF error responses are returned for various error conditions:

- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Missing or invalid authentication
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found

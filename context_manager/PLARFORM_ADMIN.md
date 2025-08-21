# lobbybee platform admin api documentation

this document provides a comprehensive guide for frontend developers on how to integrate with the lobbybee backend to build the flow customization interface for the platform admin.

## authentication

all admin api endpoints require token-based authentication. the `authorization` header must be included in all requests with the value `bearer <your_auth_token>`.

---

## built-in guest navigation

guests interacting with any flow have access to global navigation commands that are handled automatically by the system. this functionality is hardcoded and requires no configuration within the flow templates. admins should be aware of these commands when designing conversation prompts.

#### `back`
-   typing `back` allows the guest to return to the previous step in the conversation.
-   the system maintains a history of the guest's path, and this command moves them one step backward in that history.
-   **note:** the back command is intelligent. if the previous step was for collecting data that has already been provided, the system may skip over it to avoid asking for the same information again.

#### `main menu`
-   typing `main menu` will immediately end the current flow and return the guest to the main starting point (the `main_menu` flow).
-   this serves as a global reset or an "escape hatch" if the guest gets stuck or wants to start over.

---

## api endpoints

### flow templates

flow templates are the main templates for guest interaction flows.

#### 1. list and create flow templates

-   **endpoint:** `/api/context/admin/flow-templates/`
-   **methods:** `get`, `post`

##### `get /api/context/admin/flow-templates/`

-   **description:** retrieves a list of all available flow templates.
-   **success response (200 ok):**
    ```json
    [
        {
            "id": 1,
            "name": "check-in flow",
            "description": "standard guest check-in process.",
            "trigger_keyword": "checkin"
        },
        {
            "id": 2,
            "name": "room service",
            "description": "flow for ordering room service.",
            "trigger_keyword": "roomservice"
        }
    ]
    ```

##### `post /api/context/admin/flow-templates/`

-   **description:** creates a new flow template.
-   **request body:**
    ```json
    {
        "name": "new custom flow",
        "description": "a new flow for special requests.",
        "trigger_keyword": "custom"
    }
    ```
-   **success response (201 created):**
    ```json
    {
        "id": 3,
        "name": "new custom flow",
        "description": "a new flow for special requests.",
        "trigger_keyword": "custom"
    }
    ```

#### 2. retrieve, update, and delete a flow template

-   **endpoint:** `/api/context/admin/flow-templates/<int:id>/`
-   **methods:** `get`, `put`, `patch`, `delete`

##### `get /api/context/admin/flow-templates/<int:id>/`

-   **description:** retrieves a specific flow template by its id.
-   **success response (200 ok):**
    ```json
    {
        "id": 1,
        "name": "check-in flow",
        "description": "standard guest check-in process.",
        "trigger_keyword": "checkin"
    }
    ```

##### `put /api/context/admin/flow-templates/<int:id>/`

-   **description:** updates a flow template completely.
-   **request body:**
    ```json
    {
        "name": "updated check-in flow",
        "description": "the updated standard guest check-in process.",
        "trigger_keyword": "checkin_v2"
    }
    ```

##### `patch /api/context/admin/flow-templates/<int:id>/`

-   **description:** partially updates a flow template.
-   **request body:**
    ```json
    {
        "description": "a new description for the check-in flow."
    }
    ```

##### `delete /api/context/admin/flow-templates/<int:id>/`

-   **description:** deletes a flow template.
-   **success response:** `204 no content`

---

### flow step templates

flow step templates are the individual steps within a flow template.

#### 1. list and create flow step templates

-   **endpoint:** `/api/context/admin/flow-step-templates/`
-   **methods:** `get`, `post`
-   **query parameters:** `flow_template` (integer) - filter steps by flow template id.

##### `get /api/context/admin/flow-step-templates/`

-   **description:** retrieves a list of all flow step templates, optionally filtered by `flow_template`.
-   **success response (200 ok):**
    ```json
    [
        {
            "id": 1,
            "flow_template": 1,
            "step_name": "welcome message",
            "message_type": "text",
            "message_body": "welcome to our hotel! please reply with your booking id.",
            "order": 1
        }
    ]
    ```

##### `post /api/context/admin/flow-step-templates/`

-   **description:** creates a new flow step template.
-   **request body:**
    ```json
    {
        "flow_template": 1,
        "step_name": "booking id confirmation",
        "message_type": "text",
        "message_body": "thank you. we are processing your check-in.",
        "order": 2
    }
    ```

#### 2. retrieve, update, and delete a flow step template

-   **endpoint:** `/api/context/admin/flow-step-templates/<int:id>/`
-   **methods:** `get`, `put`, `patch`, `delete`

#### 3. implementing branching and conditional flows

the system supports creating non-linear, branching conversation flows where the next step is determined by the guest's response. this is achieved using the `conditional_next_steps` field on a `flowsteptemplate`.

while each step can have a default `next_step_template` for linear progression, the `conditional_next_steps` field allows you to override this behavior based on specific user inputs.

##### how it works

the `conditional_next_steps` field is a json object where:
-   **keys** are the expected user inputs (e.g., "yes", "no", "1", "support").
-   **values** are the integer ids of the `flowsteptemplate` to transition to if the user's input matches the key.

you can also include a wildcard key `"*"` which acts as a fallback for any input that doesn't match the other keys.

the system evaluates the next step in this order:
1.  look for a matching key in `conditional_next_steps` based on the user's exact input.
2.  if no direct match, look for the wildcard `"*"` key in `conditional_next_steps`.
3.  if neither of the above is found, fall back to the linear `next_step_template`.
4.  if none are defined, the flow ends.

##### example: creating a branch

let's say you have a step that asks a yes/no question.
-   **step 10 (current step):** "did you enjoy your stay? (reply 'yes' or 'no')"
-   **step 11 (yes path):** "that's great to hear! would you like to leave a review?"
-   **step 12 (no path):** "we're sorry to hear that. a manager will contact you shortly."
-   **step 13 (invalid input path):** "sorry, i didn't understand. please reply 'yes' or 'no'."

to implement this, when creating or updating **step 10**, you would provide the following `conditional_next_steps` data. assume the ids for steps 11, 12, and 13 are `11`, `12`, and `13` respectively.

###### `patch /api/context/admin/flow-step-templates/10/`

```json
{
    "conditional_next_steps": {
        "yes": 11,
        "no": 12,
        "*": 13
    }
}
```

in this example:
- if the guest replies "yes", the flow transitions to the step with id `11`.
- if the guest replies "no", the flow transitions to the step with id `12`.
- for any other reply (e.g., "maybe", "thanks"), the flow transitions to the step with id `13`.

this allows for building complex, interactive flows that can respond dynamically to guest input.

---

### flow actions

flow actions define what happens after a flow step is completed.

#### 1. list and create flow actions

-   **endpoint:** `/api/context/admin/flow-actions/`
-   **methods:** `get`, `post`

#### 2. retrieve, update, and delete a flow action

-   **endpoint:** `/api/context/admin/flow-actions/<int:id>/`
-   **methods:** `get`, `put`, `patch`, `delete`

---

### hotel flow configurations

this endpoint allows admins to view and manage which flow templates are assigned to which hotels.

#### 1. list and create hotel flow configurations

-   **endpoint:** `/api/context/admin/hotel-configurations/`
-   **methods:** `get`, `post`
-   **query parameters:** `hotel` (uuid) - filter configurations by hotel id.

##### `get /api/context/admin/hotel-configurations/`

-   **description:** retrieves a list of all hotel flow configurations.
-   **success response (200 ok):**
    ```json
    [
        {
            "id": 1,
            "hotel": "a8a6d3a0-3e3e-4c8a-8f8f-2f2f2f2f2f2f",
            "flow_template": 1,
            "is_active": true,
            "customization_data": {}
        }
    ]
    ```

##### `post /api/context/admin/hotel-configurations/`

-   **description:** assigns a flow template to a hotel.
-   **request body:**
    ```json
    {
        "hotel": "a8a6d3a0-3e3e-4c8a-8f8f-2f2f2f2f2f2f",
        "flow_template": 2,
        "is_active": true
    }
    ```

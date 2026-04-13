# HRMS API Documentation

## 1. Project Overview

- **Project Name:** HRMS (Human Resource Management System)
- **Description:** A modular FastAPI backend for managing employees, attendance, leave requests, reporting, and operational dashboards for an organization.
- **Key Features:**
  - JWT-based authentication and session management
  - Employee onboarding and profile lifecycle management
  - Leave, comp-off, and WFH request workflows
  - Attendance check-in/check-out with task-level tracking
  - Reporting exports (CSV) and analytics endpoints
- **Tech Stack:**
  - Backend: FastAPI (Python)
  - Database: PostgreSQL (Supabase)
  - Authentication: JWT (access token + refresh token)
  - Architecture: Modular (`routes`, `schemas`, `services`, `utils`)
- **Base URL:** Not specified in source test data (commonly available from deployed environment or local Swagger server).
- **Primary Content Type:** `application/json` (except CSV download endpoints)

## 2. Authentication Details

HRMS uses JWT authentication with access and refresh token flow:

1. Authenticate via login to receive `access_token` and `refresh_token`.
2. Use `access_token` for protected API calls.
3. Use `refresh_token` to obtain a new access token when expired.
4. Invalidate refresh token on logout.

Pass the access token in request headers:

```http
Authorization: Bearer <token>
```

## 3. API Endpoints

### Authentication APIs

#### Login

- Method: `POST`
- Endpoint: `/auth/login`
- Description: Authenticates user by email and returns access/refresh tokens.

##### Request Body

```json
{
  "email": "yash.infopulsetech@gmail.com"
}
```

##### Response Example

```json
{
  "access_token": "jwt-access-token",
  "refresh_token": "refresh-token-value",
  "token_type": "bearer"
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Login successful |
| 401 | Invalid credentials |

#### Refresh Token

- Method: `POST`
- Endpoint: `/auth/refresh`
- Description: Generates a new access token using a valid refresh token.

##### Request Body

```json
{
  "refresh_token": "refresh-token-value"
}
```

##### Response Example

```json
{
  "access_token": "new-jwt-access-token",
  "refresh_token": "refresh-token-value",
  "token_type": "bearer"
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Token refreshed |
| 401 | Invalid or expired refresh token |

#### Logout

- Method: `POST`
- Endpoint: `/auth/logout`
- Description: Logs out user by invalidating refresh token.

##### Request Body

```json
{
  "refresh_token": "refresh-token-value"
}
```

##### Response Example

```json
{
  "message": "Logged out"
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Logout successful |
| 401 | Invalid token |

#### Get Current User

- Method: `GET`
- Endpoint: `/auth/me`
- Description: Returns profile details of the authenticated user.

##### Request Body

No request body.

##### Response Example

```json
{
  "full_name": "yash sakariya",
  "id": "efe2ea44-a159-447c-a89c-d3bbcd6b2fcf",
  "photo_url": "nothing",
  "role": "admin",
  "joined_on": "2026-04-03",
  "created_at": "2026-04-03T10:20:22.529203+00:00",
  "organization_id": "e5a45018-c83d-4338-ba64-0e90e36a61c2",
  "department_id": "a7a0bcab-a22f-4481-bf2e-05c16e34baee",
  "email": "yash.infopulsetech@gmail.com",
  "google_id": null,
  "designation": "AI engineer",
  "is_active": true,
  "last_login_at": "2026-04-09T05:50:29.741568+00:00",
  "updated_at": "2026-04-03T10:20:22.529203+00:00"
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | User profile returned |
| 401 | Unauthorized |

### Employee APIs

#### Add Employee

- Method: `POST`
- Endpoint: `/employee/add`
- Description: Creates a new employee record for the organization.

##### Request Body

```json
{
  "email": "saif.infopulsetech@gmail.com",
  "department_id": "a7a0bcab-a22f-4481-bf2e-05c16e34baee",
  "designation": "devops"
}
```

##### Response Example

```json
{
  "full_name": null,
  "id": "0fd4410e-e5d3-4bc0-a9bc-4ae5e56ab0ea",
  "photo_url": null,
  "role": "employee",
  "joined_on": null,
  "created_at": "2026-04-09T06:15:41.900916+00:00",
  "organization_id": "e5a45018-c83d-4338-ba64-0e90e36a61c2",
  "department_id": "a7a0bcab-a22f-4481-bf2e-05c16e34baee",
  "email": "saif.infopulsetech@gmail.com",
  "google_id": null,
  "designation": "devops",
  "is_active": true,
  "last_login_at": null,
  "updated_at": "2026-04-09T06:15:41.900916+00:00"
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 201 | Employee created |
| 400 | Validation error |
| 409 | Employee already exists |

#### Update Employee Profile

- Method: `PUT`
- Endpoint: `/employee/update-profile`
- Description: Updates authenticated employee profile metadata.

##### Request Body

```json
{
  "full_name": "yashsingh",
  "photo_url": "locally added"
}
```

##### Response Example

```json
{
  "message": "Profile updated"
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Profile updated |
| 400 | Invalid payload |
| 401 | Unauthorized |

#### Deactivate Employee

- Method: `DELETE`
- Endpoint: `/employee/{emp_id}`
- Description: Soft-deletes (deactivates) an employee by ID.

##### Request Body

No request body.

##### Response Example

```json
{
  "message": "Employee deactivated successfully"
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Employee deactivated |
| 404 | Employee not found |

#### List Employees

- Method: `GET`
- Endpoint: `/employee`
- Description: Returns employees for the organization.

##### Request Body

No request body.

##### Response Example

```json
[]
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Employee list returned |
| 401 | Unauthorized |

#### Add Project

- Method: `POST`
- Endpoint: `/project/add`
- Description: Creates a new project.

##### Request Body

```json
{
  "name": "flight booking app",
  "description": "app for flight booking"
}
```

##### Response Example

```json
{
  "id": "90634328-6b41-44a7-a398-7304188013ef",
  "name": "flight booking app",
  "description": "app for flight booking",
  "is_active": true,
  "created_at": "2026-04-09T06:24:39.371702Z"
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 201 | Project created |
| 400 | Validation error |

#### List Projects

- Method: `GET`
- Endpoint: `/project`
- Description: Returns all active projects.

##### Request Body

No request body.

##### Response Example

```json
[
  {
    "id": "28ec9d11-13c4-45fc-9413-d80c34523199",
    "name": "hrmd backend",
    "description": "hr management system for the office",
    "is_active": true,
    "created_at": "2026-04-06T08:47:58.489128Z"
  },
  {
    "id": "90634328-6b41-44a7-a398-7304188013ef",
    "name": "flight booking app",
    "description": "app for flight booking",
    "is_active": true,
    "created_at": "2026-04-09T06:24:39.371702Z"
  }
]
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Project list returned |

#### Delete Project

- Method: `DELETE`
- Endpoint: `/project/{project_id}`
- Description: Deletes a project by ID.

##### Request Body

No request body.

##### Response Example

```json
{
  "message": "Project deleted successfully"
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Project deleted |
| 404 | Project not found |

#### Add Holiday

- Method: `POST`
- Endpoint: `/holiday/add`
- Description: Creates a holiday entry for the organization calendar.

##### Request Body

```json
{
  "name": "gandhi jayanti",
  "type": "public",
  "date": "2026-04-20"
}
```

##### Response Example

```json
{
  "organization_id": "e5a45018-c83d-4338-ba64-0e90e36a61c2",
  "holiday_date": "2026-04-20",
  "holiday_type": "public",
  "name": "gandhi jayanti",
  "id": "7b81434f-a54d-4f8f-ba3b-dc4b776307c1",
  "created_at": "2026-04-09T06:27:39.824018+00:00"
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 201 | Holiday created |
| 400 | Validation error |

#### List Holidays

- Method: `GET`
- Endpoint: `/holiday`
- Description: Returns all configured holidays.

##### Request Body

No request body.

##### Response Example

```json
[
  {
    "organization_id": "e5a45018-c83d-4338-ba64-0e90e36a61c2",
    "holiday_date": "2027-03-05",
    "holiday_type": "other",
    "name": "wifi problem",
    "id": "5fc38b6c-e787-488a-a05f-dfc33b531418",
    "created_at": "2026-04-06T11:29:57.531141+00:00"
  },
  {
    "organization_id": "e5a45018-c83d-4338-ba64-0e90e36a61c2",
    "holiday_date": "2026-04-20",
    "holiday_type": "public",
    "name": "gandhi jayanti",
    "id": "7b81434f-a54d-4f8f-ba3b-dc4b776307c1",
    "created_at": "2026-04-09T06:27:39.824018+00:00"
  }
]
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Holiday list returned |

#### Delete Holiday

- Method: `DELETE`
- Endpoint: `/holiday/{holiday_id}`
- Description: Deletes holiday by ID.

##### Request Body

No request body.

##### Response Example

```json
{
  "message": "Holiday deleted successfully"
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Holiday deleted |
| 404 | Holiday not found |

### Request APIs

#### Get My Leave Dates

- Method: `GET`
- Endpoint: `/leaves/me`
- Description: Returns leave dates for current and previous months for current user.

##### Request Body

No request body.

##### Response Example

```json
{
  "current_month": {
    "month": 4,
    "year": 2026,
    "dates": [
      "2026-04-10"
    ]
  },
  "previous_months": []
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Leave details returned |
| 401 | Unauthorized |

#### Leave Summary

- Method: `GET`
- Endpoint: `/leaves/summary`
- Description: Returns leave balances and usage summary across employees.

##### Request Body

No request body.

##### Response Example

```json
[
  {
    "employee_name": "yashsingh",
    "casual_balance": 1,
    "casual_used": 0,
    "comp_off_balance": 0,
    "comp_off_used": 0
  }
]
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Summary returned |
| 403 | Admin access required |

#### Get Requests (Detailed Feed)

- Method: `GET`
- Endpoint: `/requests/requests`
- Description: Returns request records with employee metadata for review.

##### Request Body

No request body.

##### Response Example

```json
[
  {
    "id": "8b855b88-f5ce-4d92-9626-5c44f695a716",
    "request_type": "comp_off",
    "from_date": "2026-04-08",
    "to_date": "2026-04-08",
    "reason": "anythign",
    "status": "pending",
    "linked_session_id": null,
    "rejection_note": null,
    "reviewed_at": null,
    "created_at": "2026-04-08T13:27:35.852672Z",
    "employee_id": "0f5acbbe-0b9c-4868-b0a6-4cb88b343d53",
    "employee_name": "Shlok D Panchal",
    "employee_email": "shlok.infopulsetech@gmail.com"
  }
]
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Requests returned |
| 401 | Unauthorized |

#### Approve Request

- Method: `PUT`
- Endpoint: `/requests/{req_id}/approve`
- Description: Approves a pending request by ID.

##### Request Body

No request body.

##### Response Example

```json
{
  "id": "8b855b88-f5ce-4d92-9626-5c44f695a716",
  "request_type": "comp_off",
  "from_date": "2026-04-08",
  "to_date": "2026-04-08",
  "reason": "anythign",
  "status": "approved",
  "linked_session_id": null,
  "rejection_note": null,
  "reviewed_at": "2026-04-09T06:52:03.499766Z",
  "created_at": "2026-04-08T13:27:35.852672Z"
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Request approved |
| 404 | Request not found |
| 409 | Request already processed |

#### Reject Request

- Method: `PUT`
- Endpoint: `/requests/{req_id}/reject`
- Description: Rejects a pending request by ID.

##### Request Body

```json
{
  "rejection_note": "due to work load"
}
```

##### Response Example

```json
{
  "id": "2eb6a48b-df13-4f8d-a92d-e39a5d947a3c",
  "request_type": "leave",
  "from_date": "2026-04-08",
  "to_date": "2026-04-08",
  "reason": "nothing",
  "status": "rejected",
  "linked_session_id": null,
  "rejection_note": "due to work load",
  "reviewed_at": "2026-04-09T07:00:17.967209Z",
  "created_at": "2026-04-08T09:03:57.972746Z"
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Request rejected |
| 404 | Request not found |
| 409 | Request already processed |

#### List Requests

- Method: `GET`
- Endpoint: `/requests`
- Description: Returns request list for authorized scope.

##### Request Body

No request body.

##### Response Example

```json
[
  {
    "id": "8b855b88-f5ce-4d92-9626-5c44f695a716",
    "request_type": "comp_off",
    "from_date": "2026-04-08",
    "to_date": "2026-04-08",
    "reason": "anythign",
    "status": "approved",
    "linked_session_id": null,
    "rejection_note": null,
    "reviewed_at": "2026-04-09T06:52:03.499766Z",
    "created_at": "2026-04-08T13:27:35.852672Z"
  }
]
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Requests returned |
| 401 | Unauthorized |

#### Create Request

- Method: `POST`
- Endpoint: `/requests`
- Description: Creates a leave, comp-off, or WFH request.

##### Request Body

```json
{
  "request_type": "wfh",
  "from_date": "2026-04-15",
  "to_date": "2026-04-15",
  "reason": "sick"
}
```

##### Response Example

```json
{
  "id": "8306a98c-4d18-417b-972b-7f5f001ee100",
  "request_type": "wfh",
  "from_date": "2026-04-15",
  "to_date": "2026-04-15",
  "reason": "sick",
  "status": "pending",
  "linked_session_id": null,
  "rejection_note": null,
  "reviewed_at": null,
  "created_at": "2026-04-09T07:39:50.262580Z"
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 201 | Request created |
| 400 | Validation error |

#### Delete Request

- Method: `DELETE`
- Endpoint: `/requests/{req_id}`
- Description: Deletes an existing request by ID.

##### Request Body

No request body.

##### Response Example

```json
{
  "message": "request deleted"
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Request deleted |
| 404 | Request not found |

### Report APIs

#### Reporting Employee Dropdown

- Method: `GET`
- Endpoint: `/reporting/dropdown`
- Description: Returns employee list for report filter dropdown.

##### Request Body

No request body.

##### Response Example

```json
[
  {
    "id": "26a8a7b8-c5e9-4362-9979-f296c44165f9",
    "full_name": "A.r. vaghela",
    "designation": "full stack intern"
  },
  {
    "id": "0f5acbbe-0b9c-4868-b0a6-4cb88b343d53",
    "full_name": "Shlok D Panchal",
    "designation": "AI Engineer"
  }
]
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Dropdown data returned |
| 401 | Unauthorized |

#### Employee Reporting Data

- Method: `GET`
- Endpoint: `/reporting/{emp_id}`
- Description: Returns attendance/reporting records for an employee.

##### Request Body

No request body. Use query parameter:

| Param | Type | Required | Description |
| --- | --- | --- | --- |
| `whole_month` | `boolean` | No | If true, returns complete month data |

##### Response Example

```json
{
  "avg_hours_this_month": 0,
  "records": [
    {
      "date": "2026-04-08",
      "tasks": "frontedn task",
      "check_in_at": "2026-04-08T08:49:12.404953Z",
      "check_out_at": "2026-04-08T08:51:15.448029Z"
    }
  ]
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Report data returned |
| 404 | Employee not found |

#### Download Employee Report CSV

- Method: `GET`
- Endpoint: `/reporting/{emp_id}/csv`
- Description: Downloads employee reporting data in CSV format.

##### Request Body

No request body.

##### Response Example

CSV file download with headers similar to:

```http
content-disposition: attachment; filename=report_<employee_name>_<month>_<year>.csv
content-type: text/csv; charset=utf-8
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | CSV downloaded |
| 404 | Employee/report not found |

### Dashboard APIs

#### Attendance Check-In

- Method: `POST`
- Endpoint: `/attendance/check-in`
- Description: Starts daily attendance session with task entries.

##### Request Body

```json
{
  "tasks": [
    {
      "project_id": "28ec9d11-13c4-45fc-9413-d80c34523199",
      "description": "tasks",
      "hours": 2
    }
  ]
}
```

##### Response Example

```json
{
  "id": "5b132df2-2d15-40dc-a5ac-0f1de31cc2e9",
  "session_date": "2026-04-09",
  "check_in_at": "2026-04-09T07:20:59.272108Z",
  "check_out_at": null,
  "total_hours": null,
  "work_mode": "office",
  "is_corrected": false,
  "tasks": [
    {
      "id": "45a45fee-3b2d-44b1-816c-de05f6f633bc",
      "project_id": "28ec9d11-13c4-45fc-9413-d80c34523199",
      "description": "tasks",
      "hours": 2
    }
  ]
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Check-in successful |
| 409 | Already checked in |

#### Get Today Attendance

- Method: `GET`
- Endpoint: `/attendance/today`
- Description: Returns today attendance session for authenticated user.

##### Request Body

No request body.

##### Response Example

```json
{
  "id": "5b132df2-2d15-40dc-a5ac-0f1de31cc2e9",
  "session_date": "2026-04-09",
  "check_in_at": "2026-04-09T07:20:59.272108Z",
  "check_out_at": null,
  "total_hours": null,
  "work_mode": "office",
  "is_corrected": false,
  "tasks": [
    {
      "id": "45a45fee-3b2d-44b1-816c-de05f6f633bc",
      "project_id": "28ec9d11-13c4-45fc-9413-d80c34523199",
      "description": "tasks",
      "hours": 2
    }
  ]
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Session returned |
| 404 | No session found |

#### Attendance Check-Out

- Method: `POST`
- Endpoint: `/attendance/check-out`
- Description: Closes active attendance session and computes total hours.

##### Request Body

No request body.

##### Response Example

```json
{
  "id": "5b132df2-2d15-40dc-a5ac-0f1de31cc2e9",
  "session_date": "2026-04-09",
  "check_in_at": "2026-04-09T07:20:59.272108Z",
  "check_out_at": "2026-04-09T07:44:49.158141Z",
  "total_hours": 0.4,
  "work_mode": "office",
  "is_corrected": false,
  "tasks": []
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Check-out successful |
| 404 | No active session |

#### Average Attendance Hours

- Method: `GET`
- Endpoint: `/attendance/avg-hours`
- Description: Returns average attendance hours for current user/time scope.

##### Request Body

No request body.

##### Response Example

```json
{
  "avg_hours": 0.4
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Average hours returned |

#### Download Attendance Sessions CSV

- Method: `GET`
- Endpoint: `/attendance/sessions/download`
- Description: Downloads attendance sessions in CSV format for selected month/year.

##### Request Body

No request body. Use query parameters:

| Param | Type | Required | Description |
| --- | --- | --- | --- |
| `month` | `integer` | Yes | Month number |
| `year` | `integer` | Yes | Year |

##### Response Example

CSV file download with headers similar to:

```http
content-disposition: attachment; filename="attendance_april_2026.csv"
content-type: text/csv; charset=utf-8
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | CSV downloaded |
| 400 | Invalid month/year |

#### List Attendance Sessions

- Method: `GET`
- Endpoint: `/attendance/sessions`
- Description: Returns attendance sessions with task summaries.

##### Request Body

No request body.

##### Response Example

```json
[
  {
    "id": "5b132df2-2d15-40dc-a5ac-0f1de31cc2e9",
    "session_date": "2026-04-09",
    "check_in_at": "2026-04-09T07:20:59.272108Z",
    "check_out_at": null,
    "total_hours": null,
    "work_mode": "office",
    "is_corrected": false,
    "tasks": [
      {
        "id": "45a45fee-3b2d-44b1-816c-de05f6f633bc",
        "description": "tasks",
        "hours_logged": 2,
        "project_id": "28ec9d11-13c4-45fc-9413-d80c34523199",
        "project_name": "hrmd backend"
      }
    ],
    "tasks_summary": "tasks"
  }
]
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Sessions returned |

#### Get Today Tasks

- Method: `GET`
- Endpoint: `/tasks/today`
- Description: Returns tasks logged under the current day session.

##### Request Body

No request body.

##### Response Example

```json
[
  {
    "id": "45a45fee-3b2d-44b1-816c-de05f6f633bc",
    "session_id": "5b132df2-2d15-40dc-a5ac-0f1de31cc2e9",
    "project_id": "28ec9d11-13c4-45fc-9413-d80c34523199",
    "description": "tasks",
    "hours_logged": 2,
    "sort_order": 0
  }
]
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Tasks returned |

#### Create Task

- Method: `POST`
- Endpoint: `/tasks`
- Description: Adds a task record to an active attendance session.

##### Request Body

```json
{
  "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "description": "string",
  "hours": 0
}
```

##### Response Example

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "description": "string",
  "hours_logged": 0,
  "sort_order": 0
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 201 | Task created |
| 400 | Validation error |

#### Delete Task

- Method: `DELETE`
- Endpoint: `/tasks/{task_id}`
- Description: Deletes task by ID.

##### Request Body

No request body.

##### Response Example

```json
{
  "message": "task_deleted"
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Task deleted |
| 404 | Task not found |

#### Get My Leave Balance

- Method: `GET`
- Endpoint: `/balance/me`
- Description: Returns leave balance breakdown by type for current user.

##### Request Body

No request body.

##### Response Example

```json
[
  {
    "leave_type": "casual",
    "year": 2026,
    "month": 4,
    "opening_balance": 0,
    "accrued": 1,
    "used": 2,
    "adjusted": 0,
    "closing_balance": -1
  },
  {
    "leave_type": "comp_off",
    "year": 2026,
    "month": 4,
    "opening_balance": 0,
    "accrued": 1,
    "used": 0,
    "adjusted": 0,
    "closing_balance": 1
  }
]
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Leave balance returned |
| 401 | Unauthorized |

#### Calendar Data

- Method: `GET`
- Endpoint: `/calendar`
- Description: Returns calendar entries for selected month and year.

##### Request Body

No request body. Use query parameters:

| Param | Type | Required | Description |
| --- | --- | --- | --- |
| `month` | `integer` | Yes | Month number |
| `year` | `integer` | Yes | Year |

##### Response Example

```json
{
  "month": 4,
  "year": 2026,
  "data": {
    "2026-04-10": [
      {
        "employee_name": "Shlok D Panchal",
        "type": "leave"
      }
    ]
  }
}
```

##### Status Codes

| Code | Description |
| --- | --- |
| 200 | Calendar data returned |
| 400 | Invalid query parameters |

## 4. Common Error Response Pattern

The exact error schema may vary by endpoint, but FastAPI validation and authorization errors typically follow this format:

```json
{
  "detail": "Error message"
}
```

Validation errors may return a structured `detail` array:

```json
{
  "detail": [
    {
      "loc": [
        "body",
        "field_name"
      ],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

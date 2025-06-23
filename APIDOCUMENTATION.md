# API Documentation

## Health Data Endpoints

### Get Health Data for a User
```http
GET /api/v1/health/health-data/{user_id}
```

Retrieves health data for a specific user from Timestream.

#### Path Parameters
- `user_id` (string, required): The ID of the user to retrieve health data for

#### Query Parameters
- `provider_type` (enum, optional): Filter by device type (e.g., APPLE_HEALTH, GOOGLE_FIT)
- `schema_type` (string, optional): Filter by schema type (e.g., daily, body, sleep)
- `start_date` (datetime, optional): Start date for filtering (format: YYYY-MM-DD)
- `end_date` (datetime, optional): End date for filtering (format: YYYY-MM-DD)

#### Response
```json
[
  {
    "timestamp": "2025-05-22T03:47:34.547Z",
    "date": "2025-05-22",
    "provider_type": "APPLE_HEALTH",
    "user_id": "b2321fec-1b96-4bef-825f-95b743b9121b",
    "schema_type": "daily",
    "data": {
      // Health data specific to the schema type
    }
  }
]
```

#### Example Request
```http
GET /api/v1/health/health-data/b2321fec-1b96-4bef-825f-95b743b9121b?provider_type=APPLE_HEALTH&start_date=2025-05-22&end_date=2025-05-23
```

### Get All Health Data
```http
GET /api/v1/health/health-data
```

Retrieves all health data from Timestream without requiring a specific user_id.

#### Query Parameters
- `provider_type` (enum, optional): Filter by device type (e.g., APPLE_HEALTH, GOOGLE_FIT)
- `schema_type` (string, optional): Filter by schema type (e.g., daily, body, sleep)
- `start_date` (datetime, optional): Start date for filtering (format: YYYY-MM-DD)
- `end_date` (datetime, optional): End date for filtering (format: YYYY-MM-DD)

#### Response
```json
[
  {
    "timestamp": "2025-05-22T03:47:34.547Z",
    "date": "2025-05-22",
    "provider_type": "APPLE_HEALTH",
    "user_id": "b2321fec-1b96-4bef-825f-95b743b9121b",
    "schema_type": "daily",
    "data": {
      // Health data specific to the schema type
    }
  }
]
```

#### Example Request
```http
GET /api/v1/health/health-data?provider_type=APPLE_HEALTH&start_date=2025-05-22&end_date=2025-05-23
```

### Store Health Data
```http
POST /api/v1/health/health-data
```

Stores health data from a device in Timestream.

#### Request Body
```json
{
  "foodhak_user_id": "b2321fec-1b96-4bef-825f-95b743b9121b",
  "provider_type": "APPLE_HEALTH",
  "timestamp": "2025-05-22T03:47:34.547Z",
  "daily_data": {
    // Daily health metrics
  },
  "body_data": {
    // Body measurements
  },
  "sleep_data": {
    // Sleep metrics
  }
}
```

#### Response
```json
{
  "status": "success",
  "message": "Health data processed and stored successfully",
  "data": {
    "daily_data": {
      // Transformed daily schema data
    },
    "body_data": {
      // Transformed body schema data
    },
    "sleep_data": {
      // Transformed sleep schema data
    },
    "stored_records": {
      "daily": 1,
      "body": 1,
      "sleep": 1
    }
  }
}
```

#### Response Fields
- `status` (string): Status of the operation ("success" or "error")
- `message` (string): Descriptive message about the operation result
- `data` (object): Contains the processed data and storage information
  - `daily_data` (object): Transformed daily health metrics
  - `body_data` (object): Transformed body measurements
  - `sleep_data` (object): Transformed sleep metrics
  - `stored_records` (object): Count of records stored for each schema type
    - `daily` (integer): Number of daily records stored
    - `body` (integer): Number of body records stored
    - `sleep` (integer): Number of sleep records stored

### Notes
- All timestamps are in ISO 8601 format
- Date filtering is based on the 'date' column in YYYY-MM-DD format
- Results are ordered by date (DESC) and then by time (DESC)
- The original timestamp is preserved in the response data
- Authentication is required for all endpoints
- Provider types are case-sensitive and must match the enum values (e.g., APPLE_HEALTH, GOOGLE_FIT)
- Schema types are case-sensitive and must be one of: daily, body, sleep

### Error Responses
```json
{
  "detail": "Error message describing the issue"
}
```

Common error codes:
- 400: Bad Request (invalid parameters)
- 401: Unauthorized (missing or invalid authentication)
- 404: Not Found (user or device not found)
- 500: Internal Server Error (server-side issues) 
# FastAPI Health Data Integration API Documentation

## Base URL
```
http://localhost:8009/api/v1/health
```

## Authentication
All endpoints require authentication using a Bearer token in the Authorization header:
```
Authorization: Bearer <your_token>
```

## API Endpoints

### 1. Connect Device
Connects a health device to a user's account.

**Endpoint:** `POST /api/v1/health/connect`

**Request Body:**
```json
{
    "userid": "string",
    "device_type": "APPLE_HEALTH | HEALTH_CONNECT | GARMIN | FITBIT",
    "is_connected": true,
    "connection_details": {
        "token": "string",
        "refresh_token": "string",
        "expires_at": "string",
        "device_id": "string",
        "device_name": "string"
    }
}
```

**Curl Request:**
```bash
curl -X POST http://localhost:8009/api/v1/health/connect \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "userid": "b2321fec-1b96-4bef-825f-95b743b9121b",
    "device_type": "APPLE_HEALTH",
    "is_connected": true,
    "connection_details": {
        "token": "eyJhbGciOiJIUzI1NiIs...",
        "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
        "expires_at": "2024-12-31T23:59:59Z",
        "device_id": "iPhone-123",
        "device_name": "iPhone 13 Pro"
    }
}'
```

**Response:**
```json
{
    "status": "success",
    "message": "Device connected successfully",
    "data": {
        "connection_id": "uuid",
        "userid": "b2321fec-1b96-4bef-825f-95b743b9121b",
        "device_type": "APPLE_HEALTH",
        "is_connected": true,
        "connected_at": "2024-03-14T10:00:00Z"
    }
}
```

### 2. Disconnect Device
Disconnects a health device from a user's account.

**Endpoint:** `POST /api/v1/health/disconnect`

**Request Body:**
```json
{
    "userid": "string",
    "device_type": "APPLE_HEALTH | HEALTH_CONNECT | GARMIN | FITBIT"
}
```

**Curl Request:**
```bash
curl -X POST http://localhost:8009/api/v1/health/disconnect \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "userid": "b2321fec-1b96-4bef-825f-95b743b9121b",
    "device_type": "APPLE_HEALTH"
}'
```

**Response:**
```json
{
    "status": "success",
    "message": "Device disconnected successfully",
    "data": {
        "connection_id": "uuid",
        "userid": "b2321fec-1b96-4bef-825f-95b743b9121b",
        "device_type": "APPLE_HEALTH",
        "is_connected": false,
        "disconnected_at": "2024-03-14T11:00:00Z"
    }
}
```

### 3. Health Data
Retrieves health data from various providers and stores it in Amazon Timestream.

**Endpoint:** `POST /api/v1/health/health-data`

**Request Body:**
```json
{
    "foodhak_user_id": "string",
    "provider_type": "APPLE_HEALTH | HEALTH_CONNECT | GARMIN | FITBIT",
    "device_health_data": {
        // Provider-specific health data
        // See examples below
    },
    "token_data": null,
    "timestamp": "string"
}
```

**Example Request (Apple Health):**
```bash
curl -X POST http://localhost:8009/api/v1/health/health-data \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "foodhak_user_id": "b2321fec-1b96-4bef-825f-95b743b9121b",
    "provider_type": "APPLE_HEALTH",
    "device_health_data": {
        "step_count": {
            "value": 5350,
            "startDate": "2025-05-02T12:19:00.000+0100",
            "endDate": "2025-05-02T14:19:00.000+0100"
        },
        "hr_samples": [
            {
                "endDate": "2025-05-02T10:22:00.000+0100",
                "startDate": "2025-05-02T10:22:00.000+0100",
                "value": 48,
                "sourceName": "Health"
            }
        ],
        "blood_pressure_samples": [
            {
                "bloodPressureSystolicValue": 112,
                "bloodPressureDiastolicValue": 87,
                "startDate": "2025-05-02T11:00:00.000+0100",
                "endDate": "2025-05-02T11:00:00.000+0100"
            }
        ],
        "sleep_samples": [
            {
                "startDate": "2025-05-01T22:13:00.000+0100",
                "endDate": "2025-05-02T07:13:00.000+0100",
                "value": "ASLEEP"
            }
        ]
    },
    "timestamp": "2025-05-02T13:58:20.918Z"
}'
```

**Example Request (Health Connect):**
```bash
curl -X POST http://localhost:8009/api/v1/health/health-data \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "foodhak_user_id": "b2321fec-1b96-4bef-825f-95b743b9121b",
    "provider_type": "HEALTH_CONNECT",
    "device_health_data": {
        "step_count": {
            "COUNT_TOTAL": 2800
        },
        "hr_samples": [
            {
                "samples": [
                    {
                        "beatsPerMinute": 70,
                        "time": "2025-05-13T01:15:00Z"
                    }
                ],
                "startTime": "2025-05-13T01:15:00Z",
                "endTime": "2025-05-13T01:15:00.001Z"
            }
        ],
        "blood_pressure_samples": [
            {
                "diastolic": {
                    "inMillimetersOfMercury": 80
                },
                "systolic": {
                    "inMillimetersOfMercury": 120
                },
                "time": "2025-05-13T11:17:00Z"
            }
        ],
        "sleep_samples": [
            {
                "startTime": "2025-05-12T21:37:00Z",
                "endTime": "2025-05-13T05:37:00Z"
            }
        ]
    },
    "timestamp": "2025-05-13T13:52:18.831Z"
}'
```

**Response:**
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

### 4. Get Health Data
Retrieves health data from Amazon Timestream.

**Endpoint:** `GET /api/v1/health/health-data/{user_id}`

**Query Parameters:**
- `userid` (required): The user's ID
- `provider_type` (required): The device provider type (APPLE_HEALTH | HEALTH_CONNECT | GARMIN | FITBIT)
- `schema_type` (required): The type of data to retrieve (daily | body | sleep)
- `start_time` (required): Start time in ISO-8601 format
- `end_time` (required): End time in ISO-8601 format

**Curl Request:**
```bash
curl -X GET "http://localhost:8009/api/v1/health/health-data/b2321fec-1b96-4bef-825f-95b743b9121b?provider_type=APPLE_HEALTH&schema_type=daily&start_time=2025-05-01T00:00:00Z&end_time=2025-05-02T23:59:59Z" \
  -H "Authorization: Bearer <your_token>"
```

### 5. Get Connection Status
Retrieves the status of all active device connections for a user.

**Endpoint:** `GET /api/v1/health/connection-status`

**Query Parameters:**
- `user_id` (required): The user's ID

**Curl Request:**
```bash
curl -X GET "http://localhost:8009/api/v1/health/connection-status?user_id=b2321fec-1b96-4bef-825f-95b743b9121b" \
  -H "Authorization: Bearer <your_token>"
```

**Response:**
```json
{
    "connections": [
        {
            "device_type": "APPLE_HEALTH",
            "is_connected": true,
            "connection_details": {
                "token": "eyJhbGciOiJIUzI1NiIs...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
                "expires_at": "2024-12-31T23:59:59Z",
                "device_id": "iPhone-123",
                "device_name": "iPhone 13 Pro"
            },
            "last_sync_at": "2024-03-14T10:00:00Z"
        },
        {
            "device_type": "GARMIN",
            "is_connected": true,
            "connection_details": {
                "token": "eyJhbGciOiJIUzI1NiIs...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
                "expires_at": "2024-12-31T23:59:59Z",
                "device_id": "Garmin-456",
                "device_name": "Garmin Forerunner 945"
            },
            "last_sync_at": "2024-03-14T09:30:00Z"
        }
    ]
}
```

**Empty Response (No Active Connections):**
```json
{
    "connections": []
}
```

**Error Response:**
```json
{
    "detail": "Error retrieving connection status",
    "code": "CONNECTION_STATUS_ERROR",
    "timestamp": "2024-03-14T10:00:00Z"
}
```

**Notes:**
- This endpoint returns all active device connections for the specified user
- Each connection includes the device type, connection status, connection details, and last sync time
- Use this endpoint when the app starts to determine which devices are connected and show appropriate UI elements
- The connection details may contain sensitive information (tokens) and should be handled securely
- The last_sync_at field can be used to show when the device last synced data with the server
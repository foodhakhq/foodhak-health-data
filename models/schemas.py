from pydantic import BaseModel, UUID4, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from models.device_connection import DeviceType

class ConnectRequest(BaseModel):
    userid: UUID4
    device_type: DeviceType
    is_connected: bool = True
    connection_details: Dict[str, Any]

class ConnectResponse(BaseModel):
    status: str
    message: str
    data: dict

class ConnectData(BaseModel):
    connection_id: str
    userid: str
    device_type: DeviceType
    is_connected: bool
    connected_at: datetime

class DisconnectRequest(BaseModel):
    """
    Request model for disconnecting a device
    """
    userid: UUID4
    device_type: DeviceType

class DisconnectResponse(BaseModel):
    status: str
    message: str
    data: dict

class DisconnectData(BaseModel):
    connection_id: str
    userid: str
    device_type: DeviceType
    is_connected: bool
    disconnected_at: datetime

class HealthDataRequest(BaseModel):
    foodhak_user_id: str
    provider_type: DeviceType
    start_time: datetime
    end_time: Optional[datetime] = None
    device_health_data: Dict[str, Any]
    local_timezone: str = "UTC"  # Default to UTC if not provided

class HealthDataResponse(BaseModel):
    status: str = "success"
    message: str = "Health data processed and stored successfully"
    data: Dict[str, Any]

class StoredRecords(BaseModel):
    daily: int = 0
    body: int = 0
    sleep: int = 0

class ErrorResponse(BaseModel):
    detail: str
    code: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class DeviceConnectionStatus(BaseModel):
    """
    Model for a single device connection status
    """
    connection_id: UUID4
    device_type: DeviceType
    is_connected: bool
    connection_details: Optional[Dict[str, Any]] = None
    last_sync_at: Optional[datetime] = None
    connected_at: datetime

class ConnectionStatusResponse(BaseModel):
    """
    Response model for checking all device connection statuses for a user
    """
    data: List[DeviceConnectionStatus]

class HealthDataRecord(BaseModel):
    provider_type: str
    user_id: str
    schema_type: str
    measure_name: str
    timestamp: datetime
    data: Dict[str, Any]

class HealthDataListResponse(BaseModel):
    status: str = "success"
    message: str
    data: List[HealthDataRecord]

class HealthCheckResponse(BaseModel):
    status: str
    version: str
    services: Dict[str, str]
    timestamp: str 
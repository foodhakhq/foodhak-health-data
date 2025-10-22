from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import boto3
import asyncio
from sqlalchemy import text
from contextlib import asynccontextmanager
import logging
from utils.json_encoder import json_serialize  # Add this import
from utils.security import get_current_user  # Add this import

from models.schemas import (
    ConnectRequest, ConnectResponse, DisconnectResponse,
    HealthDataRequest, HealthDataResponse, ErrorResponse,
    ConnectionStatusResponse, DeviceConnectionStatus,
    DisconnectRequest, StoredRecords, HealthDataListResponse
)
from models.device_connection import DeviceConnection, DeviceType
from utils.database import get_db
from utils.timestream import TimestreamClient
from services.data_transformer import DataTransformer
from config import Settings, get_settings

# Create separate routers for authenticated and non-authenticated endpoints
router = APIRouter()
auth_router = APIRouter()

timestream_client = TimestreamClient()
s3_client = boto3.client("s3")
# Configure logging
logger = logging.getLogger(__name__)

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

async def check_database_health(db: Session) -> Dict[str, Any]:
    """Check database health with timeout"""
    try:
        # Execute a simple query to verify database connection
        result = await asyncio.to_thread(
            lambda: db.execute(text("SELECT 1")).scalar()
        )
        if result == 1:
            return {"status": "healthy"}
        return {"status": "unhealthy", "error": "Database check failed"}
    except asyncio.TimeoutError:
        return {"status": "unhealthy", "error": "Database check timed out"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

async def check_timestream_health() -> Dict[str, Any]:
    """Check Timestream health with timeout"""
    try:
        settings = get_settings()
        query = f"""
        SELECT 1
        FROM "{settings.TIMESTREAM_DATABASE}"."{settings.TIMESTREAM_TABLE}"
        LIMIT 1
        """
        await asyncio.wait_for(
            asyncio.to_thread(timestream_client.query_client.query, QueryString=query),
            timeout=settings.HEALTH_CHECK_TIMEOUT
        )
        return {"status": "healthy"}
    except asyncio.TimeoutError:
        return {"status": "unhealthy", "error": "Timestream check timed out"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# Move the health check endpoint to the non-authenticated router
@router.get("/check", tags=["system"])
async def health_check(
    db: Session = Depends(get_db),  # This will properly handle the async context
    settings: Settings = Depends(get_settings)
) -> Dict[str, Any]:
    """
    Simple health check endpoint that indicates if the health data service is up
    """
    try:
        # Just return the status without any database checks
        return {
            "status": "up",
            "service": "health-data",
            "version": settings.API_VERSION,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unavailable: {str(e)}"
        )

# Move all other endpoints to the authenticated router
@auth_router.post("/connect", response_model=ConnectResponse, dependencies=[Depends(get_current_user)])
async def connect_device(
    request: ConnectRequest,
    db: Session = Depends(get_db)
):
    """
    Connect a health device for a user
    """
    try:
        # Check if device is already connected
        existing_connection = db.query(DeviceConnection).filter(
            DeviceConnection.foodhak_user_id == request.userid,
            DeviceConnection.device_type == request.device_type,
            DeviceConnection.is_connected == True
        ).first()

        if existing_connection:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Device {request.device_type} is already connected for this user"
            )

        # Create new connection
        connected_at = datetime.utcnow()
        connection = DeviceConnection(
            foodhak_user_id=request.userid,
            device_type=request.device_type,
            is_connected=request.is_connected,
            connection_details=request.connection_details,
            created_at=connected_at,  # Set the creation timestamp
            updated_at=connected_at   # Set the update timestamp
        )

        db.add(connection)
        db.commit()
        db.refresh(connection)

        # Prepare response data
        response_data = {
            "connection_id": str(connection.id),
            "userid": connection.foodhak_user_id,
            "device_type": connection.device_type,
            "is_connected": connection.is_connected,
            "connected_at": connected_at.isoformat() + "Z"  # Format as ISO with Z suffix
        }

        return ConnectResponse(
            status="success",
            message="Device connected successfully",
            data=response_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error connecting device: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error connecting device: {str(e)}"
        )

@auth_router.post("/disconnect", response_model=DisconnectResponse, dependencies=[Depends(get_current_user)])
async def disconnect_device(
    request: DisconnectRequest,
    db: Session = Depends(get_db)
):
    """
    Disconnect a health device for a user
    """
    try:
        connection = db.query(DeviceConnection).filter(
            DeviceConnection.foodhak_user_id == request.userid,
            DeviceConnection.device_type == request.device_type,
            DeviceConnection.is_connected == True
        ).first()

        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active connection found for device type {request.device_type}"
            )

        # Update connection status
        connection.is_connected = False
        disconnected_at = datetime.utcnow()
        connection.updated_at = disconnected_at  # Update the timestamp
        db.commit()

        # Prepare response data
        response_data = {
            "connection_id": str(connection.id),
            "userid": connection.foodhak_user_id,
            "device_type": connection.device_type,
            "is_connected": connection.is_connected,
            "disconnected_at": disconnected_at.isoformat() + "Z"  # Format as ISO with Z suffix
        }

        return DisconnectResponse(
            status="success",
            message="Device disconnected successfully",
            data=response_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disconnecting device: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error disconnecting device: {str(e)}"
        )

@auth_router.post("/health-data", response_model=HealthDataResponse, dependencies=[Depends(get_current_user)])
async def process_health_data(
    request: HealthDataRequest,
    db: Session = Depends(get_db)
):
    """
    Process and store health data from a device
    """
    logger.info(f"Processing health data request for user: {request.foodhak_user_id}")
    logger.debug(f"Request data: {json.dumps(request.dict(), cls=DateTimeEncoder, indent=2)}")

    try:
        # Verify device connection
        connection = db.query(DeviceConnection).filter(
            DeviceConnection.foodhak_user_id == request.foodhak_user_id,
            DeviceConnection.device_type == request.provider_type,
            DeviceConnection.is_connected == True
        ).first()

        if not connection:
            logger.warning(f"No active connection found for user {request.foodhak_user_id} "
                          f"and device type {request.provider_type}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active connection found for device type {request.provider_type}"
            )

        # Transform the data
        logger.info("Transforming health data")
        transformed_data = DataTransformer.transform_health_data(
            request.provider_type,
            request.dict()
        )
        logger.debug(f"Transformed data: {json.dumps(transformed_data, indent=2)}")

        # Initialize stored records counter
        stored_records = StoredRecords()

        # Store each type of data in Timestream
        for schema_type, data in [
            ("daily", transformed_data["daily_data"]),
            ("body", transformed_data["body_data"]),
            ("sleep", transformed_data["sleep_data"])
        ]:
            if data:  # Only store if we have data
                logger.info(f"Writing {schema_type} data to Timestream...")
                success = timestream_client.write_health_data(
                    user_id=str(request.foodhak_user_id),
                    provider_type=request.provider_type,
                    schema_type=schema_type,
                    data=data,
                    start_time=request.start_time,
                    end_time=request.end_time,
                    local_timezone=request.local_timezone
                )
                if not success:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to write {schema_type} data to Timestream"
                    )
                # Increment the stored records counter
                setattr(stored_records, schema_type, getattr(stored_records, schema_type) + 1)
                logger.info(f"Successfully wrote {schema_type} data")

        # Update last sync time
        connection.last_sync_at = datetime.utcnow()
        db.commit()

        # Prepare response data
        response_data = {
            "daily_data": transformed_data["daily_data"],
            "body_data": transformed_data["body_data"],
            "sleep_data": transformed_data["sleep_data"],
            "stored_records": stored_records.dict()
        }

        return HealthDataResponse(
            status="success",
            message="Health data processed and stored successfully",
            data=response_data
        )

    except Exception as e:
        logger.error(f"Error in process_health_data: {str(e)}")
        if hasattr(e, 'response'):
            logger.error("Error Response:", json.dumps(e.response, indent=2))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing health data: {str(e)}"
        )

@auth_router.get("/health-data/{user_id}", response_model=HealthDataListResponse, dependencies=[Depends(get_current_user)])
async def get_health_data(
    user_id: str,
    provider_type: Optional[DeviceType] = None,
    schema_type: Optional[str] = None,
    start_date: Optional[str] = Query(None, description="Start date in ISO 8601 format (e.g., 2025-05-09T00:00:00Z)"),
    end_date: Optional[str] = Query(None, description="End date in ISO 8601 format (e.g., 2025-05-09T23:59:59Z)")
):
    """
    Retrieve health data from Timestream

    Parameters:
    - user_id: The ID of the user to retrieve health data for
    - provider_type: Filter by device type (e.g., APPLE_HEALTH, GOOGLE_FIT)
    - schema_type: Filter by schema type (e.g., daily, body, sleep)
    - start_date: Start date in ISO 8601 format (e.g., 2025-05-09T00:00:00Z)
    - end_date: End date in ISO 8601 format (e.g., 2025-05-09T23:59:59Z)

    Example:
    /api/v1/health/health-data/{user_id}?provider_type=APPLE_HEALTH&start_date=2025-05-09T00:00:00Z&end_date=2025-05-09T23:59:59Z
    """
    try:
        logger.info(f"Querying health data for user: {user_id}")
        logger.info(f"Filters - provider_type: {provider_type}, schema_type: {schema_type}")
        logger.info(f"Date range - start_date: {start_date}, end_date: {end_date}")

        print(start_date)
        print(end_date)
        results = timestream_client.query_health_data(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            provider_type=provider_type,
            schema_type=schema_type
        )

        # The results are now a list of records
        return HealthDataListResponse(
            status="success",
            message=f"Successfully retrieved {len(results)} health data records",
            data=results  # This is now a list, matching the response model
        )
    except Exception as e:
        logger.error(f"Error retrieving health data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving health data: {str(e)}"
        )

@auth_router.get("/health-data", response_model=HealthDataListResponse, dependencies=[Depends(get_current_user)])
async def get_all_health_data(
    provider_type: Optional[DeviceType] = None,
    schema_type: Optional[str] = None,
    start_date: Optional[datetime] = Query(None, description="Start date in ISO 8601 format (e.g., 2025-05-09T00:00:00Z)"),
    end_date: Optional[datetime] = Query(None, description="End date in ISO 8601 format (e.g., 2025-05-09T23:59:59Z)")
):
    """
    Retrieve all health data from Timestream without requiring a specific user_id
    
    Parameters:
    - provider_type: Filter by device type (e.g., APPLE_HEALTH, GOOGLE_FIT)
    - schema_type: Filter by schema type (e.g., daily, body, sleep)
    - start_date: Start date in ISO 8601 format (e.g., 2025-05-09T00:00:00Z)
    - end_date: End date in ISO 8601 format (e.g., 2025-05-09T23:59:59Z)
    """
    try:
        # Convert provider_type to string if it's an enum
        provider_type_str = provider_type.value if provider_type else None
        
        # Query all records with optional filters
        query = f"""
        SELECT date, provider_type, user_id, schema_type, measure_name, time, measure_value::varchar
        FROM "{timestream_client.database_name}"."{timestream_client.table_name}"
        WHERE measure_name = 'health_data'
        """
        
        if provider_type_str:
            query += f" AND provider_type = '{provider_type_str}'"
        if schema_type:
            query += f" AND schema_type = '{schema_type}'"
        if start_date:
            # Format date as YYYY-MM-DD
            start_date_str = start_date.strftime('%Y-%m-%d')
            query += f" AND date >= '{start_date_str}'"
        if end_date:
            # Format date as YYYY-MM-DD
            end_date_str = end_date.strftime('%Y-%m-%d')
            query += f" AND date <= '{end_date_str}'"
            
        query += " ORDER BY date DESC, time DESC"
        logger.debug("Query:", query)  # Debug log

        response = timestream_client.query_client.query(QueryString=query)
        results = []
        
        for row in response['Rows']:
            # Parse the ISO format timestamp from the record
            record_timestamp_str = row['Data'][5]['ScalarValue']  # time column
            record_timestamp = datetime.fromisoformat(record_timestamp_str.replace('Z', '+00:00'))
            
            # Get the data and extract the original timestamp
            data = json.loads(row['Data'][6]['ScalarValue'])  # measure_value column
            original_timestamp = datetime.fromisoformat(data.pop('original_timestamp', record_timestamp_str).replace('Z', '+00:00'))
            
            result = {
                'timestamp': original_timestamp,  # Use the original timestamp in the response
                'date': row['Data'][0]['ScalarValue'],  # date column
                'provider_type': row['Data'][1]['ScalarValue'],  # provider_type column
                'user_id': row['Data'][2]['ScalarValue'],  # user_id column
                'schema_type': row['Data'][3]['ScalarValue'],  # schema_type column
                'data': data  # data without the original_timestamp
            }
            results.append(result)
            
        return HealthDataListResponse(
            status="success",
            message="Health data fetched successfully",
            data=results
        )
    except Exception as e:
        logger.error(f"Error in get_all_health_data: {str(e)}")  # Debug log
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving health data: {str(e)}"
        )

@auth_router.get("/connection-status", response_model=ConnectionStatusResponse, dependencies=[Depends(get_current_user)])
async def check_connection_status(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Check all active device connections for a user
    """
    connections = db.query(DeviceConnection).filter(
        DeviceConnection.foodhak_user_id == user_id,
        DeviceConnection.is_connected == True
    ).all()

    return ConnectionStatusResponse(
        data=[
            DeviceConnectionStatus(
                connection_id=conn.id,
                device_type=conn.device_type,
                is_connected=conn.is_connected,
                connection_details=conn.connection_details,
                last_sync_at=conn.last_sync_at,
                connected_at=conn.created_at
            )
            for conn in connections
        ]
    )

@auth_router.post("/health-data/batch", response_model=HealthDataResponse, dependencies=[Depends(get_current_user)])
async def process_health_data_batch(
    requests: List[HealthDataRequest],
    db: Session = Depends(get_db)
):
    """
    Process and store a batch of health data records from devices
    """
    logger.info(f"Processing batch health data for {len(requests)} records")
    processed = 0
    errors = []
    stored_records = StoredRecords()
    batch_response = []
    for idx, request in enumerate(requests):
        try:
            # Verify device connection
            connection = db.query(DeviceConnection).filter(
                DeviceConnection.foodhak_user_id == request.foodhak_user_id,
                DeviceConnection.device_type == request.provider_type,
                DeviceConnection.is_connected == True
            ).first()
            if not connection:
                logger.warning(f"No active connection found for user {request.foodhak_user_id} and device type {request.provider_type}")
                errors.append({"index": idx, "error": f"No active connection for device type {request.provider_type}"})
                continue
            # Transform the data
            transformed_data = DataTransformer.transform_health_data(
                request.provider_type,
                request.dict()
            )
            # Store each type of data in Timestream
            for schema_type, data in [
                ("daily", transformed_data["daily_data"]),
                ("body", transformed_data["body_data"]),
                ("sleep", transformed_data["sleep_data"])
            ]:
                if data:
                    success = timestream_client.write_health_data(
                        user_id=str(request.foodhak_user_id),
                        provider_type=request.provider_type,
                        schema_type=schema_type,
                        data=data,
                        start_time=request.start_time,
                        end_time=request.end_time,
                        local_timezone=request.local_timezone
                    )
                    if not success:
                        errors.append({"index": idx, "error": f"Failed to write {schema_type} data to Timestream"})
                        continue
                    setattr(stored_records, schema_type, getattr(stored_records, schema_type) + 1)
            # Update last sync time
            connection.last_sync_at = datetime.utcnow()
            db.commit()
            batch_response.append({
                "user_id": request.foodhak_user_id,
                "daily_data": transformed_data["daily_data"],
                "body_data": transformed_data["body_data"],
                "sleep_data": transformed_data["sleep_data"]
            })
            processed += 1
        except Exception as e:
            logger.error(f"Error in batch item {idx}: {str(e)}")
            errors.append({"index": idx, "error": str(e)})
    return HealthDataResponse(
        status="success" if processed == len(requests) and not errors else "partial_success",
        message=f"Processed {processed} out of {len(requests)} records.",
        data={
            "batch_response": batch_response,
            "stored_records": stored_records.dict(),
            "errors": errors
        }
    )

# Include both routers in the main router
router.include_router(auth_router) 
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any, List
from models.health_data_validation import HealthData
from services.health_data_service import HealthDataService
from utils.timestream import TimestreamClient
from models.schemas import DeviceType, HealthDataListResponse, HealthDataRecord


router = APIRouter()

timestream_client = TimestreamClient()


@router.post('/health_data', response_model=HealthData)
def health_data(health_data_req: HealthData):
    try:
        health_data = HealthDataService.health_data()
        return health_data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/health_data/latest', response_model=HealthDataListResponse)
def get_latest_health_data(
    user_id: str = Query(..., alias="foodhak_user_id"),
    provider_type: DeviceType = Query(...),
    schema_type: Optional[str] = Query(None)
):
    try:
        # Fetch records (ordered by date desc in query)
        results = timestream_client.query_health_data(
            user_id=user_id,
            provider_type=provider_type,
            schema_type=schema_type
        )

        # Keep only the latest record per schema_type
        latest_by_schema: Dict[str, Dict[str, Any]] = {}
        for r in results:
            st = r.get('schema_type')
            if st and st not in latest_by_schema:
                latest_by_schema[st] = r

        records: List[HealthDataRecord] = []
        for st, r in latest_by_schema.items():
            records.append(
                HealthDataRecord(
                    provider_type=r['provider_type'],
                    user_id=r['user_id'],
                    schema_type=r['schema_type'],
                    measure_name=r['measure_name'],
                    timestamp=r['timestamp'],
                    data=r['data']
                )
            )

        return HealthDataListResponse(
            message="Latest health data per schema",
            data=records
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

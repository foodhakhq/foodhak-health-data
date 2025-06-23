from http.client import HTTPException
from fastapi import APIRouter, Request
from models.health_data_validation import HealthData
from services.health_data_service import HealthDataService
import json
import logging

router = APIRouter()


@router.post('/health_data', response_model=HealthData)
def health_data(health_data_req: HealthData):
    try:
        health_data = HealthDataService.health_data()
        return health_data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/webhook')
async def webhook(request: Request):
    """
    Webhook endpoint to receive payload data from external services
    """
    try:
        # Get the raw body as bytes
        body = await request.body()
        
        # Try to parse as JSON
        try:
            payload = json.loads(body.decode('utf-8'))
            print("=== WEBHOOK PAYLOAD RECEIVED ===")
            print(f"Content-Type: {request.headers.get('content-type', 'Not specified')}")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            print("=== END WEBHOOK PAYLOAD ===")
            
            # Log the payload
            logger = logging.getLogger("log")
            logger.info(f"Webhook payload received: {json.dumps(payload, indent=2)}")
            
            return {
                "status": "success",
                "message": "Webhook payload received and processed",
                "payload_size": len(body),
                "timestamp": "2025-01-27T10:00:00Z"
            }
            
        except json.JSONDecodeError:
            # If not JSON, print as text
            text_payload = body.decode('utf-8')
            print("=== WEBHOOK TEXT PAYLOAD RECEIVED ===")
            print(f"Content-Type: {request.headers.get('content-type', 'Not specified')}")
            print(f"Payload: {text_payload}")
            print("=== END WEBHOOK TEXT PAYLOAD ===")
            
            # Log the payload
            logger = logging.getLogger("log")
            logger.info(f"Webhook text payload received: {text_payload}")
            
            return {
                "status": "success",
                "message": "Webhook text payload received and processed",
                "payload_size": len(body),
                "timestamp": "2025-01-27T10:00:00Z"
            }
            
    except Exception as e:
        logger = logging.getLogger("log")
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing webhook: {str(e)}")


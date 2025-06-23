import os
import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now we can import from the project root
from config import get_settings

import boto3
import logging
from datetime import datetime, timezone, timedelta
from botocore.config import Config
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def query_timestream_data():
    """Query Timestream to verify data exists"""
    settings = get_settings()
    
    # Create boto3 config
    boto_config = Config(
        retries=dict(
            max_attempts=3,
            mode='adaptive'
        ),
        connect_timeout=5,
        read_timeout=5
    )

    # Create Timestream query client
    query_client = boto3.client(
        'timestream-query',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
        config=boto_config
    )

    try:
        # Query to get the most recent records
        query = f"""
        WITH latest_records AS (
            SELECT 
                date_trunc('day', time) as date,
                measure_name,
                time,
                measure_value::measure_value as measure_value,
                MAX(CASE WHEN dimension_name = 'provider_type' THEN dimension_value END) as provider_type,
                MAX(CASE WHEN dimension_name = 'user_id' THEN dimension_value END) as user_id,
                MAX(CASE WHEN dimension_name = 'schema_type' THEN dimension_value END) as schema_type,
                MAX(CASE WHEN dimension_name = 'actual_start_time' THEN dimension_value END) as actual_start_time,
                MAX(CASE WHEN dimension_name = 'actual_end_time' THEN dimension_value END) as actual_end_time,
                MAX(CASE WHEN dimension_name = 'is_historical' THEN dimension_value END) as is_historical,
                MAX(CASE WHEN dimension_name = 'local_timezone' THEN dimension_value END) as local_timezone
            FROM "{settings.TIMESTREAM_DATABASE}"."{settings.TIMESTREAM_TABLE}"
            GROUP BY date_trunc('day', time), measure_name, time, measure_value::measure_value
        )
        SELECT 
            date,
            measure_name,
            time,
            measure_value,
            provider_type,
            user_id,
            schema_type,
            actual_start_time,
            actual_end_time,
            is_historical,
            local_timezone
        FROM latest_records
        ORDER BY time DESC
        LIMIT 10
        """
        
        logger.info("Executing query...")
        logger.debug(f"Query: {query}")  # Add debug logging for the query
        response = query_client.query(QueryString=query)
        
        if not response.get('Rows'):
            logger.warning("No records found in Timestream!")
            return
        
        logger.info(f"Found {len(response['Rows'])} records:")
        for row in response['Rows']:
            try:
                # Parse the data from the row
                data = {
                    'date': row['Data'][0]['ScalarValue'],
                    'provider_type': row['Data'][4]['ScalarValue'],
                    'user_id': row['Data'][5]['ScalarValue'],
                    'schema_type': row['Data'][6]['ScalarValue'],
                    'record_time': row['Data'][2]['ScalarValue'],
                    'data': json.loads(row['Data'][3]['ScalarValue']),
                    'actual_start_time': row['Data'][7]['ScalarValue'],
                    'actual_end_time': row['Data'][8]['ScalarValue'],
                    'is_historical': row['Data'][9]['ScalarValue'],
                    'local_timezone': row['Data'][10]['ScalarValue']
                }
                logger.info("\nRecord:")
                logger.info(json.dumps(data, indent=2, default=str))
            except Exception as e:
                logger.error(f"Error parsing row: {str(e)}")
                continue

    except Exception as e:
        logger.error(f"Error querying Timestream: {str(e)}")
        if hasattr(e, 'response'):
            logger.error(f"Error response: {json.dumps(e.response, indent=2)}")

if __name__ == "__main__":
    query_timestream_data() 
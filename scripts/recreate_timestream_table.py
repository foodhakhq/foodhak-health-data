import os
import sys
from pathlib import Path
import boto3
import logging
from datetime import datetime, timezone
from botocore.config import Config

# Add the project root directory to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now we can import from the project root
from config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def recreate_timestream_table():
    """Recreate the Timestream table with retention and magnetic store writes enabled"""
    settings = get_settings()

    boto_config = Config(
        retries=dict(
            max_attempts=3,
            mode='adaptive'
        ),
        connect_timeout=5,
        read_timeout=5
    )

    timestream_client = boto3.client(
        'timestream-write',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
        config=boto_config
    )

    database_name = settings.TIMESTREAM_DATABASE
    table_name = settings.TIMESTREAM_TABLE
    #table_name = 'test_table'

    try:
        # Ensure database exists
        try:
            timestream_client.describe_database(DatabaseName=database_name)
            logger.info(f"Database {database_name} exists")
        except timestream_client.exceptions.ResourceNotFoundException:
            timestream_client.create_database(DatabaseName=database_name)
            logger.info(f"Created database {database_name}")

        # Delete table if exists
        try:
            timestream_client.describe_table(DatabaseName=database_name, TableName=table_name)
            logger.info(f"Table {table_name} exists, deleting...")
            timestream_client.delete_table(DatabaseName=database_name, TableName=table_name)
            logger.info(f"Deleted table {table_name}")
        except timestream_client.exceptions.ResourceNotFoundException:
            logger.info(f"Table {table_name} does not exist")

        retention_properties = {
            'MemoryStoreRetentionPeriodInHours': 8760,  # 1 year
            'MagneticStoreRetentionPeriodInDays': 3650  # 10 years
        }

        # Create table WITHOUT schema (Timestream infers from records)
        timestream_client.create_table(
            DatabaseName=database_name,
            TableName=table_name,
            RetentionProperties=retention_properties,
            MagneticStoreWriteProperties={
                'EnableMagneticStoreWrites': True
            }
        )
        logger.info(f"Created table {table_name} with retention properties and magnetic store enabled")

        # Tagging (optional)
        timestream_client.tag_resource(
            ResourceARN=f"arn:aws:timestream:{settings.AWS_REGION}:{settings.AWS_ACCOUNT_ID}:database/{database_name}/table/{table_name}",
            Tags=[
                {'Key': 'Environment', 'Value': settings.ENVIRONMENT},
                {'Key': 'Service', 'Value': 'HealthData'},
                {'Key': 'CreatedAt', 'Value': datetime.now(timezone.utc).isoformat()},
                {'Key': 'SchemaVersion', 'Value': '1.1'}
            ]
        )
        logger.info("Added table tags")

        logger.info("Table recreation completed successfully")
        return True

    except Exception as e:
        logger.error(f"Error recreating table: {str(e)}")
        if hasattr(e, 'response'):
            logger.error(f"Error response: {e.response}")
        return False


# Example snippet of writing records to Timestream (for context)
def write_health_data_record(write_client, database_name, table_name, user_id, provider_type_str, schema_type,
                             actual_start_time, actual_end_time, start_time, current_time, local_timezone, data, record_time):

    record = {
        'Dimensions': [
            {'Name': 'user_id', 'Value': str(user_id)},
            {'Name': 'provider_type', 'Value': str(provider_type_str)},
            {'Name': 'schema_type', 'Value': str(schema_type)},
            {'Name': 'actual_start_time', 'Value': actual_start_time.isoformat()},
            {'Name': 'actual_end_time', 'Value': actual_end_time.isoformat()},
            {'Name': 'is_historical', 'Value': 'true' if start_time < (current_time - timedelta(hours=24)) else 'false'},
            {'Name': 'local_timezone', 'Value': local_timezone},
            {'Name': 'storage_type', 'Value': 'magnetic' if start_time < (current_time - timedelta(hours=24)) else 'memory'}
        ],
        'MeasureName': 'health_data',
        'MeasureValue': json.dumps(data),
        'MeasureValueType': 'VARCHAR',
        'Time': str(record_time)
    }

    try:
        response = write_client.write_records(
            DatabaseName=database_name,
            TableName=table_name,
            Records=[record]
        )
        logger.info("Record written successfully")
        return response
    except Exception as e:
        logger.error(f"Timestream write error: {str(e)}")
        if hasattr(e, 'response'):
            logger.error(f"Error response: {e.response}")
        raise

if __name__ == "__main__":
    recreate_timestream_table()

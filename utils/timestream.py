import boto3
from datetime import datetime, timezone, timedelta
import json
from typing import Dict, Any, Optional, List
import os
from dotenv import load_dotenv
import logging
from botocore.exceptions import ClientError
from botocore.config import Config
from config import get_settings
import time # Import the time module

# Configure logging
logger = logging.getLogger(__name__)

class TimestreamClient:
    def __init__(self):
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

        # Write client for writing records
        self.write_client = boto3.client(
            'timestream-write',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
            config=boto_config
        )

        # Query client for querying records
        self.query_client = boto3.client(
            'timestream-query',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
            config=boto_config
        )

        # S3 client for storing bulky payload parts and full payloads
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
            config=boto_config
        )

        self.database_name = settings.TIMESTREAM_DATABASE
        self.table_name = settings.TIMESTREAM_TABLE
        # S3 settings
        self.s3_bucket = getattr(settings, 'S3_BUCKET', None)
        self.s3_prefix = getattr(settings, 'S3_PREFIX', 'health-data')

    def write_health_data(
        self,
        user_id: str,
        provider_type: str,
        schema_type: str,
        data: Dict[str, Any],
        start_time: datetime,
        end_time: Optional[datetime] = None,
        local_timezone: str = "UTC"
    ) -> bool:
        """Write health data to Timestream with explicit start and end time
        
        Args:
            user_id (str): The user identifier
            provider_type (str): The type of health data provider
            schema_type (str): The type of health data schema
            data (Dict[str, Any]): The health data to store
            start_time (datetime): The start time of the health data period
            end_time (Optional[datetime]): The end time of the health data period. If None, will use start_time
            local_timezone (str): The user's local timezone (e.g., "America/New_York", "Europe/London"). Defaults to "UTC"
            
        Returns:
            bool: True if write was successful, False otherwise
        """
        try:
            # If end_time is not provided, use start_time
            if end_time is None:
                end_time = start_time

            # Validate timestamps
            if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
                raise ValueError("start_time and end_time must be datetime objects")
            
            if start_time > end_time:
                raise ValueError("start_time must be before end_time")



            # Store the actual timestamps for querying
            actual_start_time = start_time
            actual_end_time = end_time

            # Get current time in UTC
            current_time = datetime.now(timezone.utc)
            record_version = int(time.time() * 1000)
            record_time = int(time.time() * 1000)
            logger.info(f"Writing data with timestamp {start_time.isoformat()}")

            provider_type_str = provider_type.value if hasattr(provider_type, 'value') else str(provider_type)

            # Validate data before writing
            if not isinstance(data, dict):
                raise ValueError("data must be a dictionary")

            # Prepare payload and enforce size constraints (Timestream VARCHAR <= 2048)
            payload: Dict[str, Any] = dict(data)

            # No separate step_samples offload; include them in the full payload S3 object

            # Also store the full payload in S3 and keep a reference
            try:
                if self.s3_bucket:
                    date_str = actual_start_time.astimezone(timezone.utc).strftime("%Y-%m-%d")
                    provider_type_s = provider_type_str
                    full_key = f"{self.s3_prefix}/{user_id}/{provider_type_s}/{schema_type}/{date_str}/payload_{int(time.time()*1000)}.json"
                    payload_s3_key = self._upload_json_to_s3(full_key, payload)
                    payload = dict(payload)
                    payload['payload_s3_key'] = payload_s3_key
            except Exception as s3e:
                logger.error(f"Failed to offload full payload to S3: {str(s3e)}")

            # Serialize and check size
            try:
                payload_str = json.dumps(payload)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Data cannot be serialized to JSON: {str(e)}")

            if len(payload_str) > 2048:
                # Fallback to minimal representation (preserve S3 reference)
                minimal: Dict[str, Any] = {
                    'metadata': payload.get('metadata', {}),
                }
                if 'distance_data' in payload and isinstance(payload['distance_data'], dict):
                    minimal['distance_data'] = {
                        'steps': payload['distance_data'].get('steps', 0)
                    }
                # Include compact heart rate summary if it fits
                if 'heart_rate_data' in payload and isinstance(payload['heart_rate_data'], dict):
                    summary = payload['heart_rate_data'].get('summary', {})
                    test_str = json.dumps({**minimal, 'heart_rate_data': {'summary': summary}})
                    if len(test_str) <= 2048:
                        minimal['heart_rate_data'] = {'summary': summary}
                # Preserve pointer to full payload stored in S3
                if 'payload_s3_key' in payload:
                    minimal['payload_s3_key'] = payload['payload_s3_key']
                payload = minimal
                payload_str = json.dumps(payload)

            # Prepare the record with both actual and record timestamps in dimensions
            record = {
                'Dimensions': [
                    {'Name': 'user_id', 'Value': str(user_id)},
                    {'Name': 'provider_type', 'Value': str(provider_type_str)},
                    {'Name': 'schema_type', 'Value': str(schema_type)},
                    {'Name': 'actual_start_time', 'Value': actual_start_time.isoformat()},
                    {'Name': 'actual_end_time', 'Value': actual_end_time.isoformat()},
                    {'Name': 'local_timezone', 'Value': local_timezone},
                ],
                'MeasureName': 'health_data',
                'MeasureValue': payload_str,
                'MeasureValueType': 'VARCHAR',
                'Time': str(record_time),
                'Version': record_version
            }
            print("record *************", record)
            print("database_name *************", self.database_name)
            print("table_name *************", self.table_name)

            try:
                response = self.write_client.write_records(
                    DatabaseName=self.database_name,
                    TableName=self.table_name,
                    Records=[record]
                )
                print("Timestream write response *************", response)
                # Log the full response from the write operation
                logger.debug(f"Timestream write response: {json.dumps(response, indent=2)}")
                
                # Check for rejected records
                if 'RejectedRecords' in response and response['RejectedRecords']:
                    for rejected in response['RejectedRecords']:
                        logger.error(f"Record rejected: {rejected}")
                        if 'Reason' in rejected:
                            logger.error(f"Rejection reason: {rejected['Reason']}")
                        if 'ExistingVersion' in rejected:
                            logger.error(f"Existing version: {rejected['ExistingVersion']}")
                    return False

                logger.info(
                    f"Successfully wrote health data for user {user_id} "
                    f"(actual time: {actual_start_time.isoformat()} to {actual_end_time.isoformat()}, "
                    f"storage: {'magnetic' if start_time < (current_time - timedelta(hours=24)) else 'memory'})"
                )
                return True

            except ClientError as e:
                error_code = e.response['Error']['Code']
                error_message = e.response['Error']['Message']
                logger.error(f"Timestream write ClientError - Code: {error_code}, Message: {error_message}")
                
                if error_code == 'RejectedRecordsException':
                    if 'RejectedRecords' in e.response:
                        for rejected in e.response['RejectedRecords']:
                            logger.error(f"Record rejected by Timestream: {rejected}")
                            if 'Reason' in rejected:
                                logger.error(f"Rejection reason: {rejected['Reason']}")
                            if 'ExistingVersion' in rejected:
                                logger.error(f"Existing version: {rejected['ExistingVersion']}")
                # Ensure we log other ClientErrors too
                logger.error(f"ClientError details: {json.dumps(e.response, indent=2)}")
                return False
            except Exception as e:
                # Catch any other unexpected exceptions during the write operation
                logger.error(f"Unexpected error writing to Timestream: {str(e)}")
                if hasattr(e, 'response'):
                    logger.error(f"Error response details: {json.dumps(e.response, indent=2)}")
                return False

        except ValueError as ve:
            logger.error(f"Validation error in write_health_data: {str(ve)}")
            return False
        except Exception as e:
            logger.error(f"Error writing to Timestream: {str(e)}")
            if hasattr(e, 'response'):
                logger.error(f"Error response: {json.dumps(e.response, indent=2)}")
            return False

    def _upload_json_to_s3(self, key: str, obj: Dict[str, Any]) -> str:
        body = json.dumps(obj).encode("utf-8")
        self.s3_client.put_object(
            Bucket=self.s3_bucket,
            Key=key,
            Body=body,
            ContentType="application/json"
        )
        return key

    # def query_health_data(
    #         self,
    #         user_id: str,
    #         start_date: Optional[datetime] = None,
    #         end_date: Optional[datetime] = None,
    #         provider_type: Optional[str] = None,
    #         schema_type: Optional[str] = None
    # ) -> List[Dict[str, Any]]:
    #     """Query health data from Timestream and return as a list of records"""
    #     try:
    #         query = f"""
    #         SELECT provider_type, user_id, schema_type, measure_name, time, measure_value::varchar
    #         FROM "{self.database_name}"."{self.table_name}"
    #         WHERE user_id = '{user_id}'
    #         """

    #         if provider_type:
    #             provider_type_str = provider_type.value if hasattr(provider_type, 'value') else str(provider_type)
    #             query += f" AND provider_type = '{provider_type_str}'"

    #         if schema_type:
    #             query += f" AND schema_type = '{schema_type}'"
    #         else:
    #             query += " AND schema_type IN ('daily', 'body', 'sleep')"

    #         if start_date:
    #             query += f" AND actual_start_time >= from_iso8601_timestamp('{start_date}')"

    #         if end_date:
    #             query += f" AND actual_end_time <= from_iso8601_timestamp('{end_date}')"

    #         query += " ORDER BY time DESC"

    #         logger.debug(f"Executing Timestream query: {query}")
    #         print(f"Executing Timestream query: {query}")
    #         response = self.query_client.query(QueryString=query)

    #         results = []
    #         for row in response.get('Rows', []):
    #             try:
    #                 data = {
    #                     'provider_type': row['Data'][0]['ScalarValue'],
    #                     'user_id': row['Data'][1]['ScalarValue'],
    #                     'schema_type': row['Data'][2]['ScalarValue'],
    #                     'measure_name': row['Data'][3]['ScalarValue'],
    #                     'timestamp': datetime.fromisoformat(row['Data'][4]['ScalarValue'].replace('Z', '+00:00')),
    #                     'data': json.loads(row['Data'][5]['ScalarValue'])
    #                 }
    #                 results.append(data)
    #             except (KeyError, json.JSONDecodeError, ValueError) as e:
    #                 logger.error(f"Error parsing row data: {str(e)}")
    #                 continue

    #         return results

    #     except Exception as e:
    #         logger.error(f"Error querying Timestream: {str(e)}")
    #         raise



    def query_health_data(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        provider_type: Optional[str] = None,
        schema_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Query health data from Timestream and return as a list of latest records per schema type"""
        try:
            # Start building the base query using CTE and row_number()
            query = f"""
            WITH ranked_data AS (
                SELECT 
                    provider_type,
                    user_id,
                    schema_type,
                    measure_name,
                    time,
                    measure_value::varchar,
                    cast(from_iso8601_timestamp(actual_start_time) as date) AS data_date,
                    ROW_NUMBER() OVER (
                        PARTITION BY schema_type, cast(from_iso8601_timestamp(actual_start_time) as date)
                        ORDER BY time DESC
                    ) AS rn
                FROM "{self.database_name}"."{self.table_name}"
                WHERE user_id = '{user_id}'
            """

            if provider_type:
                provider_type_str = provider_type.value if hasattr(provider_type, 'value') else str(provider_type)
                query += f" AND provider_type = '{provider_type_str}'"

            if schema_type:
                query += f" AND schema_type = '{schema_type}'"
            else:
                query += " AND schema_type IN ('daily', 'body', 'sleep')"

            if start_date:
                query += f" AND from_iso8601_timestamp(actual_start_time) >= from_iso8601_timestamp('{start_date}')"

            if end_date:
                query += f" AND from_iso8601_timestamp(actual_end_time) <= from_iso8601_timestamp('{end_date}')"

            # Close CTE
            query += """
            )
            SELECT provider_type, user_id, schema_type, measure_name, time, measure_value::varchar
            FROM ranked_data
            WHERE rn = 1
            ORDER BY data_date DESC, schema_type
            """

            logger.debug(f"Executing Timestream query: {query}")
            print(f"Executing Timestream query: {query}")
            response = self.query_client.query(QueryString=query)

            results = []
            print("response------>", response)
            for row in response.get('Rows', []):
                try:
                    record = {
                        'provider_type': row['Data'][0]['ScalarValue'],
                        'user_id': row['Data'][1]['ScalarValue'],
                        'schema_type': row['Data'][2]['ScalarValue'],
                        'measure_name': row['Data'][3]['ScalarValue'],
                        'timestamp': datetime.fromisoformat(row['Data'][4]['ScalarValue'].replace('Z', '+00:00')),
                        'data': json.loads(row['Data'][5]['ScalarValue'])
                    }
                    # Expand S3 reference if present
                    if isinstance(record['data'], dict) and 'payload_s3_key' in record['data'] and self.s3_bucket:
                        try:
                            s3_key = record['data']['payload_s3_key']
                            record['data'] = self._fetch_json_from_s3(s3_key)
                        except Exception as e:
                            logger.error(f"Failed to fetch payload from S3 for key %s: %s", s3_key, str(e))
                    results.append(record)
                except (KeyError, json.JSONDecodeError, ValueError) as e:
                    logger.error(f"Error parsing row data: {str(e)}")
                    continue

            return results

        except Exception as e:
            logger.error(f"Error querying Timestream: {str(e)}")
            raise

    def _fetch_json_from_s3(self, key: str) -> Dict[str, Any]:
        response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=key)
        body = response['Body'].read()
        return json.loads(body)





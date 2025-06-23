import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from dateutil import parser
from models.schemas import DeviceType
import statistics
import logging

logger = logging.getLogger(__name__)

class DataTransformer:
    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        """Ensure a datetime is in UTC timezone"""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def transform_health_data(provider_type: DeviceType, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform provider-specific health data to our unified schemas
        Returns a dictionary with daily_data, body_data, and sleep_data
        """
        print("Inside transform_health_data ")
        # Ensure start_time and end_time are in UTC
        start_time = DataTransformer._ensure_utc(data.get('start_time'))
        end_time = DataTransformer._ensure_utc(data.get('end_time')) if data.get('end_time') else start_time

        # Log the timestamps for debugging
        logger.debug(f"Transforming health data with start_time: {start_time.isoformat()}, end_time: {end_time.isoformat()}")

        if provider_type == DeviceType.APPLE_HEALTH:
            return {
                "daily_data": DataTransformer._transform_daily_data_apple(data, start_time, end_time),
                "body_data": DataTransformer._transform_body_data_apple(data, start_time, end_time),
                "sleep_data": DataTransformer._transform_sleep_data_apple(data, start_time, end_time)
            }
        elif provider_type == DeviceType.HEALTH_CONNECT:
            print("Inside HEALTH_CONNECT")
            return {
                "daily_data": DataTransformer._transform_daily_data_health_connect(data, start_time, end_time),
                "body_data": DataTransformer._transform_body_data_health_connect(data, start_time, end_time),
                "sleep_data": DataTransformer._transform_sleep_data_health_connect(data, start_time, end_time)
            }
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")

    @staticmethod
    def _transform_daily_data_apple(data: Dict[str, Any], start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        health_data = data.get('device_health_data', {})
        # Extract heart rate data for summary calculations
        hr_samples = health_data.get('hr_samples', [])
        hr_values = [sample.get('value') for sample in hr_samples if sample.get('value') is not None]
        
        daily_data = {
            "metadata": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            },
            "distance_data": {
               "steps": health_data.get('step_count', {}).get('value', 0)
            },
            "heart_rate_data": {
                "summary": {
                    "avg_hr_bpm": statistics.mean(hr_values) if hr_values else 0
                }
            }
        }
        return daily_data

    @staticmethod
    def _transform_body_data_apple(data: Dict[str, Any], start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        health_data = data.get('device_health_data', {})
        bp_samples = health_data.get("blood_pressure_samples", [])
        if not bp_samples:
            return {
                "metadata": {
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat()
                },
                "blood_pressure_data": {
                    "blood_pressure_samples": []
                }
            }

        # Get the latest sample based on endDate
        latest_sample = sorted(
            bp_samples,
            key=lambda x: parser.parse(x["endDate"]),
            reverse=True
        )[0]
        
        # Convert sample timestamps to UTC
        sample_start = DataTransformer._ensure_utc(parser.parse(latest_sample["startDate"]))
        
        body_data = {
            "metadata": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            },
            "blood_pressure_data": {
                "blood_pressure_samples": [
                    {
                        "timestamp": sample_start.isoformat(),
                        "systolic_bp": latest_sample["bloodPressureSystolicValue"],
                        "diastolic_bp": latest_sample["bloodPressureDiastolicValue"]
                    }
                ]
            }
        }
        return body_data

    @staticmethod
    def _transform_sleep_data_apple(data: Dict[str, Any], start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        health_data = data.get('device_health_data', {})
        sleep_samples = health_data.get('sleep_samples', [])
        
        if not sleep_samples:
            return {
                "metadata": {}
            }

        # Sort samples by endDate (latest first)
        latest_sleep = sorted(
            sleep_samples,
            key=lambda x: parser.parse(x["endDate"]),
            reverse=True
        )[0]

        # # Convert sleep timestamps to UTC
        # sleep_start = DataTransformer._ensure_utc(parser.parse(latest_sleep["startDate"]))
        # sleep_end = DataTransformer._ensure_utc(parser.parse(latest_sleep["endDate"]))

        sleep_data = {
            "metadata": {
                "start_time": latest_sleep["startDate"],
                "end_time": latest_sleep["endDate"],
                "is_nap": False
            }
        }
        print("sleep_dta" , sleep_data)
        return sleep_data

    @staticmethod
    def _transform_daily_data_health_connect(data: Dict[str, Any], start_time: datetime, end_time: datetime) -> Dict[str, Any]:

        print("***********************8")
        health_data = data.get('device_health_data', {})
        # Steps
        steps = health_data.get('step_count', {}).get('COUNT_TOTAL', 0)
        # Heart rate
        hr_samples = []
        for sample_group in health_data.get('hr_samples', []):
            for sample in sample_group.get('samples', []):
                if sample.get('beatsPerMinute') is not None:
                    hr_samples.append(sample.get('beatsPerMinute'))
        daily_data = {
            "metadata": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            },
            "distance_data": {
                "steps": steps
            },
            "heart_rate_data": {
                "summary": {
                    "avg_hr_bpm": statistics.mean(hr_samples) if hr_samples else 0
                }
            }
        }
        return daily_data

    @staticmethod
    def _transform_body_data_health_connect(data: Dict[str, Any], start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Transform Health Connect body data into unified format"""
        health_data = data.get('device_health_data', {})
        bp_samples = health_data.get('blood_pressure_samples', [])
        
        if not bp_samples:
            return {
                "metadata": {
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat()
                },
                "blood_pressure_data": {
                    "blood_pressure_samples": []
                }
            }

        # Get the latest sample based on time
        latest_sample = sorted(
            bp_samples,
            key=lambda x: parser.parse(x["time"]),
            reverse=True
        )[0]
        
        # Convert sample timestamp to UTC
        sample_time = DataTransformer._ensure_utc(parser.parse(latest_sample["time"]))
        
        body_data = {
            "metadata": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            },
            "blood_pressure_data": {
                "blood_pressure_samples": [
                    {
                        "timestamp": sample_time.isoformat(),
                        "systolic_bp": latest_sample["systolic"]["inMillimetersOfMercury"],
                        "diastolic_bp": latest_sample["diastolic"]["inMillimetersOfMercury"]
                    }
                ]
            }
        }
        return body_data

    @staticmethod
    def _transform_sleep_data_health_connect(data: Dict[str, Any], start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Transform Health Connect sleep data into unified format"""
        health_data = data.get('device_health_data', {})
        sleep_samples = health_data.get('sleep_samples', [])

        if not sleep_samples:
            return {
                "metadata": {}
            }

        # Get the latest sleep session based on endTime
        latest_sleep = sorted(
            sleep_samples,
            key=lambda x: parser.parse(x["endTime"]),
            reverse=True
        )[0]
        
        sleep_data = {
            "metadata": {
                "start_time": latest_sleep["startTime"],
                "end_time": latest_sleep["endTime"],
                "is_nap": False
            }
        }
        return sleep_data

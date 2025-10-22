import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta
from dateutil import parser
from dateutil.parser import ParserError
from models.schemas import DeviceType
import statistics
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import pytz

logger = logging.getLogger(__name__)


class DataTransformer:
    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        """Ensure a datetime is in UTC timezone"""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _format_local_dt_with_millis_no_colon(dt: datetime) -> str:
        """Format datetime like 2025-08-13T00:00:00.000+0100 (no colon in offset, 3-digit millis)."""
        s = dt.strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        dot_index = s.find(".")
        if dot_index == -1:
            return s
        # Keep 3 digits of fractional seconds and append numeric offset
        return f"{s[:dot_index]}.{s[dot_index+1:dot_index+4]}{s[-5:]}"

    @staticmethod
    def _build_hourly_step_samples_apple(
        input_step_samples: List[Dict[str, Any]],
        start_time_utc: datetime,
        end_time_utc: datetime,
        local_timezone: str
    ) -> List[Dict[str, Any]]:
        """
        Build a continuous per-hour series between start and end (inclusive of the last hour)
        in the user's local timezone. Hours without samples are filled with value=0.
        """
        try:
            tz = ZoneInfo(local_timezone) if local_timezone else ZoneInfo("UTC")
        except ZoneInfoNotFoundError:
            tz = ZoneInfo("UTC")

        local_start = start_time_utc.astimezone(tz)
        local_end = end_time_utc.astimezone(tz)

        # Align to hour boundaries
        series_start = local_start.replace(minute=0, second=0, microsecond=0)
        series_end_exclusive = local_end.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

        # Initialize bins with 0 values
        bins: Dict[datetime, int] = {}
        cursor = series_start
        while cursor < series_end_exclusive:
            bins[cursor] = 0
            cursor = cursor + timedelta(hours=1)

        # Aggregate provided samples into the bins by their start hour
        for sample in input_step_samples or []:
            try:
                sample_start = parser.parse(sample.get("startDate"))
                if sample_start.tzinfo is None:
                    sample_start = sample_start.replace(tzinfo=tz)
                else:
                    sample_start = sample_start.astimezone(tz)
                bin_key = sample_start.replace(minute=0, second=0, microsecond=0)
                steps_value = int(sample.get("value", 0) or 0)
                if bin_key in bins:
                    bins[bin_key] += steps_value
            except (ParserError, ValueError, TypeError):
                # Skip malformed samples
                continue

        # Emit ordered list of hourly samples (value field)
        hourly_samples: List[Dict[str, Any]] = []
        for bin_start in sorted(bins.keys()):
            bin_end = bin_start + timedelta(hours=1)
            hourly_samples.append(
                {
                    "value": bins[bin_start],
                    "start_time": DataTransformer._format_local_dt_with_millis_no_colon(bin_start),
                    "end_time": DataTransformer._format_local_dt_with_millis_no_colon(bin_end),
                }
            )
        return hourly_samples

    @staticmethod
    def _build_hourly_step_samples_health_connect(
        input_step_samples: List[Dict[str, Any]],
        start_time_utc: datetime,
        end_time_utc: datetime,
        local_timezone: str
    ) -> List[Dict[str, Any]]:
        """
        Build a continuous per-hour series (local timezone) from Health Connect step samples.
        Health Connect samples use fields: count, startTime, endTime.
        """
        try:
            tz = ZoneInfo(local_timezone) if local_timezone else ZoneInfo("UTC")
        except ZoneInfoNotFoundError:
            tz = ZoneInfo("UTC")

        local_start = start_time_utc.astimezone(tz)
        local_end = end_time_utc.astimezone(tz)

        series_start = local_start.replace(minute=0, second=0, microsecond=0)
        series_end_exclusive = local_end.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

        bins: Dict[datetime, int] = {}
        cursor = series_start
        while cursor < series_end_exclusive:
            bins[cursor] = 0
            cursor = cursor + timedelta(hours=1)

        for sample in input_step_samples or []:
            try:
                sample_start = parser.parse(sample.get("startTime"))
                if sample_start.tzinfo is None:
                    sample_start = sample_start.replace(tzinfo=timezone.utc).astimezone(tz)
                else:
                    sample_start = sample_start.astimezone(tz)
                bin_key = sample_start.replace(minute=0, second=0, microsecond=0)
                steps_value = int(sample.get("count", 0) or 0)
                if bin_key in bins:
                    bins[bin_key] += steps_value
            except (ParserError, ValueError, TypeError):
                continue

        hourly_samples: List[Dict[str, Any]] = []
        for bin_start in sorted(bins.keys()):
            bin_end = bin_start + timedelta(hours=1)
            hourly_samples.append(
                {
                    "value": bins[bin_start],
                    "start_time": DataTransformer._format_local_dt_with_millis_no_colon(bin_start),
                    "end_time": DataTransformer._format_local_dt_with_millis_no_colon(bin_end),
                }
            )
        return hourly_samples

    @staticmethod
    def transform_health_data(provider_type: DeviceType, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform provider-specific health data to our unified schemas
        Returns a dictionary with daily_data, body_data, and sleep_data
        """
        # Ensure start_time and end_time are in UTC
        start_time = DataTransformer._ensure_utc(data.get('start_time'))
        end_time = DataTransformer._ensure_utc(data.get('end_time')) if data.get('end_time') else start_time

        # Log the timestamps for debugging
        logger.debug(
            "Transforming health data with start_time: %s, end_time: %s",
            start_time.isoformat(),
            end_time.isoformat(),
        )

        if provider_type == DeviceType.APPLE_HEALTH:
            return {
                "daily_data": DataTransformer._transform_daily_data_apple(data, start_time, end_time),
                "body_data": DataTransformer._transform_body_data_apple(data, start_time, end_time),
                "sleep_data": DataTransformer._transform_sleep_data_apple(data, start_time, end_time)
            }
        elif provider_type == DeviceType.HEALTH_CONNECT:
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
        # Build hourly step samples across the requested window
        step_samples_hourly = DataTransformer._build_hourly_step_samples_apple(
            health_data.get('step_samples', []),
            start_time,
            end_time,
            data.get('local_timezone', 'UTC')
        )

        daily_data = {
            "metadata": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            },
            "distance_data": {
                "steps": health_data.get('step_count', {}).get('value', 0),
                "step_samples": step_samples_hourly
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
    def _transform_sleep_data_apple(
        data: Dict[str, Any],
        _start_time: datetime,
        _end_time: datetime
    ) -> Dict[str, Any]:
        health_data = data.get('device_health_data', {})
        sleep_samples = health_data.get('sleep_samples', [])

        if not sleep_samples:
            return {
                "metadata": {},
                "stages": []
            }

        # Normalize Apple types to desired output
        type_map = {
            "REM": "REM",
            "CORE": "Core",
            "DEEP": "Deep",
            "AWAKE": "Awake",
            "ASLEEP": "Asleep",  # mapped from ASLEEP → CORE
            "INBED": "Inbed"  # mapped from INBED → AWAKE
        }

        # Aggregate durations and bounds per stage type
        aggregated: Dict[str, Dict[str, Any]] = {}
        overall_starts: List[datetime] = []
        overall_ends: List[datetime] = []

        for sample in sleep_samples:
            try:
                raw = (sample.get("value") or "").upper()
                if raw not in type_map:
                    # Ignore INBED/ASLEEP and unknowns for stage breakdown
                    continue
                stage_type = type_map[raw]
                start_dt = parser.parse(sample["startDate"])  # preserves local offset
                end_dt = parser.parse(sample["endDate"])      # preserves local offset
                if start_dt >= end_dt:
                    continue
                duration_mins = int((end_dt - start_dt).total_seconds() // 60)

                if stage_type not in aggregated:
                    aggregated[stage_type] = {
                        "type": stage_type,
                        "start_time": sample["startDate"],
                        "end_time": sample["endDate"],
                        "total_duration": 0
                    }

                # Sum durations
                aggregated[stage_type]["total_duration"] += duration_mins

                # Expand bounds
                if parser.parse(aggregated[stage_type]["start_time"]) > start_dt:
                    aggregated[stage_type]["start_time"] = sample["startDate"]
                if parser.parse(aggregated[stage_type]["end_time"]) < end_dt:
                    aggregated[stage_type]["end_time"] = sample["endDate"]

                overall_starts.append(start_dt)
                overall_ends.append(end_dt)
            except Exception:
                # skip malformed
                continue

        stages = list(aggregated.values())

        metadata: Dict[str, Any] = {}
        if overall_starts and overall_ends:
            metadata = {
                "start_time": min(overall_starts).isoformat(),
                "end_time": max(overall_ends).isoformat(),
                "is_nap": False
            }

        return {
            "metadata": metadata,
            "stages": stages
        }

    @staticmethod
    def _transform_daily_data_health_connect(data: Dict[str, Any], start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        health_data = data.get('device_health_data', {})
        # Steps
        steps = health_data.get('step_count', {}).get('COUNT_TOTAL', 0)
        # Hourly step samples from HC input
        step_samples_hourly = DataTransformer._build_hourly_step_samples_health_connect(
            health_data.get('step_samples', []),
            start_time,
            end_time,
            data.get('local_timezone', 'UTC')
        )
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
                "steps": steps,
                "step_samples": step_samples_hourly
            },
            "heart_rate_data": {
                "summary": {
                    "avg_hr_bpm": statistics.mean(hr_samples) if hr_samples else 0
                }
            }
        }
        return daily_data

    @staticmethod
    def _transform_body_data_health_connect(
            data: Dict[str, Any],
            start_time: datetime,
            end_time: datetime
    ) -> Dict[str, Any]:
        """Transform Health Connect body data into unified format in local timezone"""

        # Get user's local timezone from data
        local_tz_str = data.get('local_timezone', 'UTC')
        tz = pytz.timezone(local_tz_str)

        health_data = data.get('device_health_data', {})
        bp_samples = health_data.get('blood_pressure_samples', [])

        if not bp_samples:
            return {
                "metadata": {
                    "start_time": start_time.astimezone(tz).isoformat(),
                    "end_time": end_time.astimezone(tz).isoformat()
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

        # Convert sample timestamp to local timezone
        sample_time = parser.parse(latest_sample["time"]).astimezone(tz)

        body_data = {
            "metadata": {
                "start_time": start_time.astimezone(tz).isoformat(),
                "end_time": end_time.astimezone(tz).isoformat()
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
    def _transform_sleep_data_health_connect(
            data: Dict[str, Any],
            _start_time: datetime,
            _end_time: datetime
    ) -> Dict[str, Any]:
        """Transform Health Connect sleep data into unified format with stage-wise durations in local timezone"""

        # Get user's local timezone from data
        local_tz_str = data.get('local_timezone', 'UTC')
        tz = pytz.timezone(local_tz_str)

        health_data = data.get('device_health_data', {})
        sleep_samples = health_data.get('sleep_samples', [])

        if not sleep_samples:
            print("sleep_samples", sleep_samples)
            return {"metadata": {}, "stages": []}

        # Pick the latest sleep session
        latest_sleep = sorted(
            sleep_samples,
            key=lambda x: parser.parse(x["endTime"]),
            reverse=True
        )[0]
        stages = latest_sleep.get("stages", [])
        print("stages", stages)

        if not stages:
            start = parser.parse(latest_sleep['startTime']).astimezone(tz)
            end = parser.parse(latest_sleep['endTime']).astimezone(tz)
            return {
                "metadata": {
                    "start_time": start.isoformat(),
                    "end_time": end.isoformat(),
                    "is_nap": False
                },
                "stages": []
            }

        # Health Connect stage codes → labels
        code_map = {
            1: "Awake",
            2: "Asleep",
            3: "Awake",
            4: "Core",
            5: "Deep",
            6: "REM",
        }

        aggregated: Dict[str, Dict[str, Any]] = {}
        overall_starts: List[datetime] = []
        overall_ends: List[datetime] = []

        for s in latest_sleep.get("stages", []) or []:
            try:
                code = s.get("stage")
                label = code_map.get(int(code)) if code is not None else None
                if not label:
                    continue

                start = parser.parse(s["startTime"]).astimezone(tz)
                end = parser.parse(s["endTime"]).astimezone(tz)
                if start >= end:
                    continue

                mins = int((end - start).total_seconds() // 60)

                if label not in aggregated:
                    aggregated[label] = {
                        "type": label,
                        "start_time": start.isoformat(),
                        "end_time": end.isoformat(),
                        "total_duration": 0
                    }

                aggregated[label]["total_duration"] += mins

                if parser.parse(aggregated[label]["start_time"]).astimezone(tz) > start:
                    aggregated[label]["start_time"] = start.isoformat()
                if parser.parse(aggregated[label]["end_time"]).astimezone(tz) < end:
                    aggregated[label]["end_time"] = end.isoformat()

                overall_starts.append(start)
                overall_ends.append(end)
            except Exception as e:
                print("Error processing stage:", e)
                continue

        stages = list(aggregated.values())

        metadata: Dict[str, Any] = {}
        if overall_starts and overall_ends:
            metadata = {
                "start_time": parser.parse(latest_sleep.get("startTime")).astimezone(tz).isoformat(),
                "end_time": parser.parse(latest_sleep.get("endTime")).astimezone(tz).isoformat(),
                "is_nap": False
            }

        return {"metadata": metadata, "stages": stages}

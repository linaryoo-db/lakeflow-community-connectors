import csv
import io
import datetime as dt
from datetime import timedelta
from typing import Dict, List, Iterator
from urllib.parse import quote

import requests
from pyspark.sql.types import *


class LakeflowConnect:
    def __init__(self, options: Dict[str, str]) -> None:
        """
        Initialize the AppsFlyer connector with authentication and configuration.

        Required options:
        - api_token: AppsFlyer API V2 token
        - app_id: Application identifier (iOS bundle ID or Android package name)

        Optional options:
        - start_date: Initial sync start date (default: 90 days ago)
        - lookback_days: Lookback window for incremental sync (default: 3)
        """
        self.api_token = options["api_token"]
        self.app_id = options["app_id"]
        self.start_date = options.get("start_date", None)
        self.lookback_days = int(options.get("lookback_days", "3"))
        self.base_url = f"https://hq1.appsflyer.com/api/raw-data/export/app/{self.app_id}"
        self.auth_header = {"Authorization": f"Bearer {self.api_token}"}

        # Maximum rows per request (AppsFlyer supports up to 1M)
        self.max_rows = 1000000

    def list_tables(self) -> List[str]:
        """
        Returns a list of available AppsFlyer report types.
        Note: Currently only organic_in_app_events_report is enabled for testing.
        Other reports are commented out due to subscription limitations or unavailability.
        """
        return [
            # Ad Engagement Reports
            # "clicks_report",  # Requires higher subscription tier
            # "impressions_report",  # Requires higher subscription tier
            # User Acquisition Reports (Non-Organic)
            # "installs_report",  # Requires higher subscription tier
            # "in_app_events_report",  # Requires higher subscription tier
            # "sessions_report",  # Requires higher subscription tier
            # "uninstall_events_report",  # Requires higher subscription tier
            # "attributed_ad_revenue_report",  # Requires higher subscription tier
            # User Acquisition Reports (Organic)
            # "organic_installs_report",  # Requires higher subscription tier
            "organic_in_app_events_report",
            # "organic_sessions_report",  # Requires higher subscription tier
            # "organic_uninstall_events_report",  # Requires higher subscription tier
            # "organic_ad_revenue_report",  # Requires higher subscription tier
            # Retargeting Reports
            # "conversions_report",  # Requires higher subscription tier
            # "retargeting_in_app_events_report",  # Requires higher subscription tier
            # "retargeting_sessions_report",  # Requires higher subscription tier
            # "retargeting_ad_revenue_report",  # Requires higher subscription tier
            # Postback Reports
            # "install_postbacks_report",  # Requires higher subscription tier
            # "inapps_postbacks_report",  # Requires higher subscription tier
            # "conversions_postbacks_report",  # Requires higher subscription tier
            # "retargeting_inapps_postbacks_report",  # Requires higher subscription tier
            # Fraud & Protection Reports
            # "blocked_installs_report",  # Requires Protect360 subscription
            # "blocked_install_postbacks_report",  # Requires Protect360 subscription
            # "blocked_clicks_report",  # Requires higher subscription tier
            # "post_attribution_installs_report",  # Unknown report
            # "blocked_inapps_events_report",  # Unknown report
        ]

    def get_table_schema(
        self, table_name: str, table_options: Dict[str, str]
    ) -> StructType:
        """
        Returns the schema for the specified AppsFlyer report.
        """
        if table_name not in self.list_tables():
            raise ValueError(f"Table '{table_name}' is not supported.")

        # Base schema fields present in all reports
        base_fields = [
            StructField("appsflyer_id", StringType(), True),
            StructField("event_time", TimestampType(), True),
            StructField("install_time", TimestampType(), True),
            StructField("event_name", StringType(), True),
            StructField("event_type", StringType(), True),
            StructField("event_value", StringType(), True),
            StructField("event_revenue", DoubleType(), True),
            StructField("event_revenue_currency", StringType(), True),
            StructField("event_revenue_usd", DoubleType(), True),
        ]

        # Attribution fields (null in organic reports)
        attribution_fields = [
            StructField("attributed_touch_type", StringType(), True),
            StructField("attributed_touch_time", TimestampType(), True),
            StructField("media_source", StringType(), True),
            StructField("campaign", StringType(), True),
            StructField("af_channel", StringType(), True),
            StructField("af_ad", StringType(), True),
            StructField("af_ad_id", StringType(), True),
            StructField("af_adset", StringType(), True),
            StructField("af_c_id", StringType(), True),
            StructField("match_type", StringType(), True),
            StructField("af_keywords", StringType(), True),
            StructField("af_cost_value", DoubleType(), True),
            StructField("af_cost_currency", StringType(), True),
        ]

        # Device fields
        device_fields = [
            StructField("advertising_id", StringType(), True),
            StructField("idfa", StringType(), True),
            StructField("idfv", StringType(), True),
            StructField("android_id", StringType(), True),
            StructField("imei", StringType(), True),
            StructField("device_model", StringType(), True),
            StructField("os_version", StringType(), True),
            StructField("platform", StringType(), True),
            StructField("language", StringType(), True),
        ]

        # Location fields
        location_fields = [
            StructField("country_code", StringType(), True),
            StructField("city", StringType(), True),
            StructField("region", StringType(), True),
            StructField("postal_code", StringType(), True),
            StructField("ip", StringType(), True),
        ]

        # App fields
        app_fields = [
            StructField("app_id", StringType(), True),
            StructField("app_name", StringType(), True),
            StructField("app_version", StringType(), True),
            StructField("bundle_id", StringType(), True),
        ]

        # Network fields
        network_fields = [
            StructField("carrier", StringType(), True),
            StructField("wifi", BooleanType(), True),
            StructField("user_agent", StringType(), True),
        ]

        # IAP & Subscription fields
        iap_fields = [
            StructField("af_product_id", StringType(), True),
            StructField("af_purchase_date_ms", LongType(), True),
            StructField("af_transaction_id", StringType(), True),
            StructField("af_order_id", StringType(), True),
            StructField("af_net_revenue", DoubleType(), True),
            StructField("af_store", StringType(), True),
            StructField("af_currency", StringType(), True),
            StructField("af_price", DoubleType(), True),
            StructField("af_quantity", LongType(), True),
        ]

        # Ad Revenue fields
        ad_revenue_fields = [
            StructField("ad_revenue_ad_type", StringType(), True),
            StructField("mediation_network", StringType(), True),
            StructField("placement", StringType(), True),
            StructField("impressions", LongType(), True),
        ]

        # Fraud Prevention fields
        fraud_fields = [
            StructField("blocked_reason", StringType(), True),
            StructField("is_organic", StringType(), True),
            StructField("rejected_reason", StringType(), True),
        ]

        # Combine all fields
        all_fields = (
            base_fields +
            attribution_fields +
            device_fields +
            location_fields +
            app_fields +
            network_fields +
            iap_fields +
            ad_revenue_fields +
            fraud_fields
        )

        return StructType(all_fields)

    def read_table_metadata(
        self, table_name: str, table_options: Dict[str, str]
    ) -> Dict:
        """
        Returns metadata for the specified AppsFlyer report.
        """
        if table_name not in self.list_tables():
            raise ValueError(f"Table '{table_name}' is not supported.")

        # Determine primary keys based on report type
        if "installs_report" in table_name or "uninstall" in table_name:
            primary_keys = ["appsflyer_id"]
        elif "events_report" in table_name or "sessions_report" in table_name:
            primary_keys = ["appsflyer_id", "event_time", "event_name"]
        elif "conversions" in table_name or "clicks" in table_name or "impressions" in table_name:
            primary_keys = ["appsflyer_id", "event_time"]
        elif "postbacks" in table_name:
            primary_keys = ["appsflyer_id", "event_time"]
        elif "blocked" in table_name or "post_attribution" in table_name:
            primary_keys = ["appsflyer_id", "event_time"]
        else:
            primary_keys = ["appsflyer_id"]

        # Determine ingestion type
        if "uninstall" in table_name:
            ingestion_type = "cdc"
        else:
            ingestion_type = "append"

        metadata = {
            "primary_keys": primary_keys,
            "cursor_field": "event_time",
            "ingestion_type": ingestion_type,
        }

        return metadata

    def _get_date_range(self, start_offset: dict) -> tuple:
        """Determine the date range for data extraction."""
        if start_offset and "from_date" in start_offset and "to_date" in start_offset:
            from_date = dt.datetime.fromisoformat(start_offset["from_date"])
            to_date = dt.datetime.fromisoformat(start_offset["to_date"])
        else:
            # Initial sync - use start_date or default to 90 days ago
            from_date = (
                dt.datetime.fromisoformat(self.start_date)
                if self.start_date
                else dt.datetime.now() - timedelta(days=90)
            )
            # Read one day at a time initially
            to_date = from_date + timedelta(days=1)
        return from_date, to_date

    def _build_query_params(
        self, from_date: dt.datetime, to_date: dt.datetime, table_options: Dict[str, str]
    ) -> dict:
        """Build query parameters for API request."""
        params = {
            "from": from_date.strftime("%Y-%m-%d %H:%M:%S"),
            "to": to_date.strftime("%Y-%m-%d %H:%M:%S"),
            "maximum_rows": str(self.max_rows),
        }

        # Add optional table_options
        optional_params = [
            "event_name", "media_source", "geo",
            "timezone", "currency", "additional_fields"
        ]
        for param in optional_params:
            if param in table_options:
                params[param] = table_options[param]

        return params

    def _calculate_next_offset(
        self, num_records: int, from_date: dt.datetime, to_date: dt.datetime
    ) -> dict:
        """Calculate the next offset for pagination."""
        current_time = dt.datetime.now()

        if num_records >= self.max_rows:
            # Hit row limit - need to split time range
            time_diff = to_date - from_date
            if time_diff.total_seconds() <= 3600:  # Already at 1 hour or less
                # Can't split further, move to next hour
                return {
                    "from_date": to_date.isoformat(),
                    "to_date": min(to_date + timedelta(hours=1), current_time).isoformat(),
                }
            # Split the range in half
            mid_date = from_date + (time_diff / 2)
            return {
                "from_date": from_date.isoformat(),
                "to_date": mid_date.isoformat(),
            }

        if to_date >= current_time:
            # Caught up to current time - return same offset to signal completion
            return {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
            }

        # Move to next time window
        return {
            "from_date": to_date.isoformat(),
            "to_date": min(to_date + timedelta(days=1), current_time).isoformat(),
        }

    def read_table(
        self, table_name: str, start_offset: dict, table_options: Dict[str, str]
    ) -> (Iterator[dict], dict):
        """
        Reads data from the specified AppsFlyer report.

        Optional table_options:
        - event_name: Filter specific events (comma-separated)
        - media_source: Filter by media source
        - geo: Filter by country code
        - timezone: Timezone offset
        - currency: Currency preference (USD or preferred)
        - additional_fields: Additional fields to include (comma-separated)
        """
        if table_name not in self.list_tables():
            raise ValueError(f"Table '{table_name}' is not supported.")

        # Determine date range for this read
        from_date, to_date = self._get_date_range(start_offset)

        # Build API request
        endpoint = f"{self.base_url}/{table_name}/v5"
        params = self._build_query_params(from_date, to_date, table_options)

        # Make API request
        response = requests.get(endpoint, headers=self.auth_header, params=params)

        if response.status_code != 200:
            raise Exception(
                f"AppsFlyer API error for {table_name}: {response.status_code} {response.text}"
            )

        # Parse CSV response
        records_list = list(self._parse_csv_response(response.text))

        # Calculate next offset
        next_offset = self._calculate_next_offset(len(records_list), from_date, to_date)

        return iter(records_list), next_offset

    def _parse_timestamp(self, record: dict, field: str) -> None:
        """Parse timestamp field in-place."""
        if field in record and record[field]:
            try:
                record[field] = dt.datetime.strptime(
                    record[field], "%Y-%m-%d %H:%M:%S"
                )
            except (ValueError, TypeError):
                record[field] = None

    def _parse_numeric_fields(self, record: dict) -> None:
        """Parse all numeric fields in-place."""
        # Parse float fields
        float_fields = [
            "event_revenue", "event_revenue_usd", "af_cost_value",
            "af_net_revenue", "af_price"
        ]
        for field in float_fields:
            if field in record and record[field]:
                try:
                    record[field] = float(record[field])
                except (ValueError, TypeError):
                    record[field] = None

        # Parse integer fields
        integer_fields = [
            "af_purchase_date_ms", "af_quantity", "impressions"
        ]
        for field in integer_fields:
            if field in record and record[field]:
                try:
                    record[field] = int(record[field])
                except (ValueError, TypeError):
                    record[field] = None

        # Parse boolean fields
        if "wifi" in record and record["wifi"]:
            record["wifi"] = record["wifi"].lower() == "true"

    def _parse_csv_response(self, csv_text: str) -> List[dict]:
        """
        Parses CSV response from AppsFlyer API into list of dictionaries.
        """
        if not csv_text or csv_text.strip() == "":
            return []

        records = []
        csv_reader = csv.DictReader(io.StringIO(csv_text))

        for row in csv_reader:
            # Convert empty strings to None
            record = {k: (v if v != "" else None) for k, v in row.items()}

            # Parse timestamps
            for timestamp_field in ["event_time", "install_time", "attributed_touch_time"]:
                self._parse_timestamp(record, timestamp_field)

            # Parse numeric fields
            self._parse_numeric_fields(record)

            records.append(record)

        return records

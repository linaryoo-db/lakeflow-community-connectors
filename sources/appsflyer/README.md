# Lakeflow AppsFlyer Community Connector

This documentation provides setup instructions and reference information for the AppsFlyer source connector.

The Lakeflow AppsFlyer Connector allows you to extract raw data from your AppsFlyer mobile attribution platform and load it into your data lake or warehouse. This connector supports incremental synchronization for various AppsFlyer raw data reports.

## Prerequisites

- Access to an AppsFlyer account with API permissions
- AppsFlyer API V2 token with read permissions for raw data reports
- Admin role in AppsFlyer to generate and manage API tokens
- Raw Data Reports access (requires specific AppsFlyer subscription tiers)

## Setup

### Required Connection Parameters

To configure the connector, provide the following parameters in your connector options:

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `api_token` | string | Yes | AppsFlyer API V2 token (JWT format) for authentication | `eyJhbGciOiJBM...` |
| `app_id` | string | Yes | Application identifier (iOS bundle ID or Android package name) | `com.example.app` |
| `start_date` | string | No | Initial sync start date in YYYY-MM-DD format (default: 90 days ago) | `2025-01-01` |
| `lookback_days` | string | No | Number of days to look back for incremental sync (default: 3) | `3` |
| `externalOptionsAllowList` | string | Yes | Comma-separated list of allowed table-specific options: `event_name,media_source,geo,timezone,currency,additional_fields` | `event_name,media_source,geo` |

**Note on `externalOptionsAllowList`:** This parameter is required and must contain the exact comma-separated list above. These options allow you to filter and customize data extraction on a per-table basis.

### Getting Your API Token

1. Log in to your AppsFlyer dashboard as an admin
2. Navigate to **Integration → API Access**
3. Locate the **V2.0 token** section
4. Copy the API V2 token (JWT format - long encoded string starting with "eyJ...")
5. Note: API V2 tokens should be rotated every 180 days for security

**Security Best Practices:**
- Only admins can view and manage API tokens
- Store tokens securely and never commit them to version control
- Replace tokens regularly (recommended every 180 days)
- API V2 tokens (JWT) are preferred over deprecated V1 tokens

### Finding Your App ID

- **iOS apps**: Use your bundle ID from App Store Connect (e.g., `com.company.appname`)
- **Android apps**: Use your package name from Google Play Console (e.g., `com.company.appname`)
- You can also find this in your AppsFlyer dashboard under **Apps → [Your App] → Settings**

### Create a Unity Catalog Connection

A Unity Catalog connection for this connector can be created in two ways via the UI:
1. Follow the Lakeflow Community Connector UI flow from the "Add Data" page
2. Select any existing Lakeflow Community Connector connection for this source or create a new one
3. In the connection parameters, set `externalOptionsAllowList` to: `event_name,media_source,geo,timezone,currency,additional_fields`

The connection can also be created using the standard Unity Catalog API.

## Supported Objects

The AppsFlyer connector currently supports the following raw data report:

### organic_in_app_events_report

- **Description**: Organic (non-attributed) in-app events from users who installed the app organically
- **Primary Keys**: `appsflyer_id`, `event_time`, `event_name`
- **Incremental Strategy**: Cursor-based on `event_time`
- **Ingestion Type**: Append-only (new events are continuously added)

**Key Fields:**
- `appsflyer_id` - Unique identifier for the user
- `event_time` - Timestamp when the event occurred
- `event_name` - Name of the in-app event (e.g., "purchase", "level_complete")
- `event_value` - JSON string containing event parameters
- `event_revenue` - Revenue value extracted from event (if applicable)
- `event_revenue_currency` - Currency code for revenue
- `event_revenue_usd` - Revenue converted to USD
- `install_time` - Timestamp of the app installation
- `customer_user_id` - Your custom user identifier
- Device identifiers: `advertising_id`, `idfa`, `idfv`, `android_id`
- Device information: `platform`, `device_model`, `os_version`, `app_version`
- Location: `country_code`, `city`, `region`, `ip`
- Attribution fields: `media_source`, `campaign` (null for organic events)

**Schema:** 59 fields including event details, user identifiers, device information, location data, and attribution metadata

**Additional Reports (Commented Out):**

The connector includes commented-out support for additional report types that require higher AppsFlyer subscription tiers:
- Ad Engagement Reports: `clicks_report`, `impressions_report`
- User Acquisition Reports: `installs_report`, `in_app_events_report`, `sessions_report`
- Retargeting Reports: `conversions_report`, `retargeting_in_app_events_report`
- Fraud Protection Reports: `blocked_installs_report`, `blocked_clicks_report`

To enable these reports, uncomment the desired report names in the connector code and ensure your AppsFlyer subscription includes access to the corresponding raw data.

### Table-Specific Configuration Options

When configuring tables in your pipeline, you can use the following optional filters to customize data extraction for `organic_in_app_events_report`:

| Option | Type | Description | Example |
|--------|------|-------------|---------|
| `event_name` | string | Filter by specific event names (comma-separated for multiple events) | `purchase,level_complete` |
| `media_source` | string | Filter by media source (null for organic) | `organic` |
| `geo` | string | Filter by country code (ISO 3166-1 alpha-2) | `US,CA,GB` |
| `timezone` | string | Timezone offset for event timestamps | `UTC+0` |
| `currency` | string | Currency preference (USD or preferred) | `USD` |
| `additional_fields` | string | Request additional fields beyond default schema (comma-separated) | `custom_field1,custom_field2` |

**Important:** All table-specific options must be listed in the connection-level `externalOptionsAllowList` parameter.

## Data Type Mapping

The AppsFlyer connector maps source data types to Databricks data types as follows:

| AppsFlyer Type | Databricks Type | Notes |
|----------------|-----------------|-------|
| String | StringType | Text fields, IDs, event names |
| Timestamp | TimestampType | Event times, install times (format: YYYY-MM-DD HH:MM:SS) |
| Number (decimal) | DoubleType | Revenue values, cost values |
| Number (integer) | LongType | Quantities, impression counts, millisecond timestamps |
| Boolean | BooleanType | Flags like wifi connection status |
| JSON Object | StringType | Event values stored as JSON strings |

## How to Run

### Step 1: Clone/Copy the Source Connector Code

Follow the Lakeflow Community Connector UI, which will guide you through setting up a pipeline using the AppsFlyer source connector code.

### Step 2: Configure Your Pipeline

1. Update the `pipeline_spec` in the main pipeline file (e.g., `ingest.py`).
2. Configure table-specific options to filter and customize data extraction:

```json
{
  "pipeline_spec": {
      "connection_name": "my_appsflyer_connection",
      "object": [
        {
            "table": {
                "source_table": "organic_in_app_events_report",
                "event_name": "purchase,subscription",
                "geo": "US,CA",
                "currency": "USD"
            }
        }
      ]
  }
}
```

**Example: Filter Purchase Events from US**
```json
{
  "table": {
    "source_table": "organic_in_app_events_report",
    "event_name": "purchase",
    "geo": "US"
  }
}
```

**Example: Get All Events with Additional Fields**
```json
{
  "table": {
    "source_table": "organic_in_app_events_report",
    "additional_fields": "custom_dimension_1,custom_dimension_2"
  }
}
```

3. (Optional) Customize the source connector code if needed for special use cases.

### Step 3: Run and Schedule the Pipeline

#### Best Practices

- **Start Small**: Begin with a short date range (e.g., last 7 days) to test your pipeline
- **Use Incremental Sync**: The connector automatically handles incremental reads using `event_time` as the cursor field
- **Lookback Window**: The default 3-day lookback helps capture late-arriving events
- **Set Appropriate Schedules**: Balance data freshness requirements with API rate limits
  - Hourly sync: Good for real-time analytics needs
  - Daily sync: Sufficient for most reporting use cases
- **Monitor API Rate Limits**: AppsFlyer enforces daily limits on raw data report downloads
  - Free/basic tiers: Limited number of report downloads per day
  - Premium tiers: Higher limits with auto-scaling support
  - See error messages for specific limit information
- **Filter Wisely**: Use table-specific options to reduce data volume and API usage
- **Date Range Limits**: Raw data is available for the last 90 days (standard) or longer with Data Locker

#### Troubleshooting

**Common Issues:**

1. **Authentication Error (401/403)**
   - **Cause**: Invalid or expired API V2 token
   - **Solution**:
     - Verify your token is the V2 (JWT) format, not V1
     - Regenerate token from AppsFlyer dashboard if expired
     - Ensure the token has read permissions for raw data

2. **Rate Limit Exceeded (400)**
   - **Error**: "You've reached your maximum number of in-app event reports that can be downloaded today"
   - **Solution**:
     - Wait 24 hours for the limit to reset
     - Upgrade your AppsFlyer subscription for higher limits
     - Reduce sync frequency or use longer time intervals
     - Contact AppsFlyer support to increase limits

3. **Missing Data or Empty Results**
   - **Cause**: Date range outside available data window
   - **Solution**:
     - Verify your `start_date` is within the last 90 days
     - Check that events exist for the specified filters
     - Remove overly restrictive filters (e.g., `event_name`, `geo`)

4. **Subscription Access Error (400)**
   - **Error**: "Your current subscription package doesn't include raw data reports"
   - **Solution**:
     - Upgrade to a plan that includes Raw Data Reports access
     - Contact your AppsFlyer Customer Success Manager
     - Only `organic_in_app_events_report` is available in the current implementation

5. **Invalid App ID (400)**
   - **Error**: "App not found" or authentication failures
   - **Solution**:
     - Verify `app_id` matches your bundle ID/package name exactly
     - Check that the app is registered in your AppsFlyer account
     - Ensure the API token has access to this specific app

6. **Schema Mismatch**
   - **Cause**: Custom fields or schema changes not reflected
   - **Solution**:
     - Use `additional_fields` option to include custom fields
     - Re-run schema discovery if AppsFlyer adds new standard fields
     - Check AppsFlyer field dictionary for field name changes

## Data Freshness and Consistency

- **Real-time events**: Events typically appear in raw data reports within 2-10 minutes
- **Data finality**: Data for a given hour becomes final approximately 1 hour after the hour ends
- **Lookback window**: The default 3-day lookback ensures late-arriving events are captured
- **Backfill**: Historical data can be ingested by setting `start_date` to an earlier date (within 90-day window)

## References

- [AppsFlyer Raw Data Reports Documentation](https://support.appsflyer.com/hc/en-us/articles/208387843)
- [AppsFlyer Pull API V2 Documentation](https://support.appsflyer.com/hc/en-us/articles/360004562377)
- [AppsFlyer Field Dictionary](https://support.appsflyer.com/hc/en-us/articles/207034486)
- [AppsFlyer API Rate Limits](https://support.appsflyer.com/hc/en-us/articles/207034366)
- [AppsFlyer Authentication Guide](https://support.appsflyer.com/hc/en-us/articles/360004562377#authentication)

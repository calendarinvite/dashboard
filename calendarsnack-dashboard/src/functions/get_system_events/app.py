"""Return system events."""

import json
import logging
from os import environ

import boto3

# Variable Reuse
dynamodb = boto3.client("dynamodb", region_name=environ["REGION"])


def lambda_handler(event, __):
    """Process API request."""
    configure_logging(environ.get("LOG_LEVEL", "WARNING"))
    logging.info(event)
    event_list = get_system_event_list()

    return {
        "statusCode": 200,
        "headers": {"Access-Control-Allow-Origin": "*"},
        "body": json.dumps(event_list),
    }


def get_system_event_list():
    """Get system event list."""
    event_list = get_event_records()
    return format_events_from(event_list)


def get_event_records():
    """Get event records."""
    return dynamodb.query(
        TableName=environ["DYNAMODB_TABLE"],
        IndexName="system_events",
        KeyConditionExpression="tenant = :tenant AND last_modified > :time",
        ProjectionExpression=(
            "created, description_html, dtend, dtstart, location_html, "
            + "mailto, organizer, #status, summary_html, uid"
        ),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":tenant": {"S": "thirtyone"},
            ":time": {"N": "0"},
        },
        ScanIndexForward=False,
        Limit=min(
            int(environ.get("EVENT_VIEW_LENGTH", 100)),
            int(environ.get("MAX_EVENT_VIEW_LENGTH", 500)),
        ),
        ConsistentRead=False,
    ).get("Items", [])


def format_events_from(event_list):
    """Format events from event list."""
    formatted_event_list = []

    for event in event_list:
        formatted_event_list.append(
            {
                "uid": event["uid"]["S"],
                "mailto": event["mailto"]["S"],
                "organizer": event["organizer"]["S"],
                "status": event["status"]["S"],
                "created": int(event["created"]["N"]),
                "dtstart": int(event["dtstart"]["N"]),
                "dtend": int(event["dtend"]["N"]),
                "summary_html": event["summary_html"]["S"],
                "description_html": event["description_html"]["S"],
                "location_html": event["location_html"]["S"],
            }
        )

    return formatted_event_list


def configure_logging(log_level=environ.get("LOG_LEVEL", "WARNING")):
    """Configure program logging."""
    root = logging.getLogger()

    _ = [
        root.removeHandler(handler)
        for handler in root.handlers
        if root.handlers
    ]

    logging.basicConfig(**get_logging_settings(log_level))


def get_logging_settings(log_level):
    """Configure logging settings."""
    return {
        "format": "%(asctime)s - %(levelname)s - %(funcName)s(): %(message)s",
        "datefmt": "[%Y.%m.%d] %H:%M:%S",
        "level": log_level,
    }

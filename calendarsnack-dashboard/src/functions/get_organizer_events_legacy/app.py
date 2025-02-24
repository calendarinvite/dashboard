"""Get organizer events - legacy code."""

import json
import logging

# from base64 import b64decode
# from hashlib import sha256
from os import environ

import boto3

# Variable Reuse
DYNAMODB = boto3.client("dynamodb", region_name=environ["REGION"])


def lambda_handler(event, _):
    """Process API request."""
    configure_logging(environ.get("LOG_LEVEL", "WARNING"))
    logging.info(event)
    return get_organizer_events(event)


def get_organizer_events(request):
    """Return organizer's events.

    Organizer events are returned as dictionary elements within
    an array.
    """
    # try:
    response = {
        "statusCode": 200,
        "headers": {"Access-Control-Allow-Origin": "*"},
        "body": json.dumps(
            format_events(get_event_list(get_organizer(request)))
        ),
    }
    # except Exception as error:
    #     response = invalid_request()

    #     logging.warning(
    #         "Failed to process: %s \nError: %s",
    #         request.get("headers", "Empty Request"),
    #         error,
    #     )

    return response


def get_event_list(organizer):
    """Get event list for organizer."""
    return DYNAMODB.query(
        TableName=environ["DYNAMODB_TABLE"],
        IndexName="organizer_events",
        KeyConditionExpression=(
            "mailto = :organizer " "AND last_modified > :time"
        ),
        ProjectionExpression=(
            "created, description_html, dtend, dtstart, location_html, "
            "mailto, organizer, #status, summary_html, uid"
        ),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":organizer": {"S": organizer},
            ":time": {"N": "0"},
        },
        ScanIndexForward=False,
        Limit=int(environ.get("EVENT_VIEW_LENGTH", 100)),
        ConsistentRead=False,
    ).get("Items", [])


def get_organizer(request):
    """Get organizer email from request.

    Return organizer email from legacy method (GET)
    """
    return request.get("pathParameters", {}).get("organizer", {})


def format_events(events):
    """Standardize event information."""
    return [
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
        for event in events
    ]


def invalid_request():
    """Return default invalid request response."""
    return {"statusCode": 404, "headers": {"Access-Control-Allow-Origin": "*"}}


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

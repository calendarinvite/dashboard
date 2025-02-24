"""Get event attendee sanitized list."""

import json
import logging
from os import environ

import boto3

# Variable Reuse
dynamodb = boto3.client("dynamodb", region_name=environ["REGION"])


def lambda_handler(event, _):
    """Handle lambda event."""
    configure_logging(environ.get("LOG_LEVEL", "WARNING"))
    logging.info(event)
    attendee_list = get_sanitized_attendee_list_for(
        event["pathParameters"]["uid"]
    )

    return {
        "statusCode": 200,
        "headers": {"Access-Control-Allow-Origin": "*"},
        "body": json.dumps(attendee_list),
    }


def get_sanitized_attendee_list_for(uid):
    """Get sanitized attendee list for uid."""
    attendee_list = get_attendee_list_for(uid)

    return sanitize(attendee_list)


def get_attendee_list_for(uid):
    """Get attendee list for uid."""
    return dynamodb.query(
        TableName=environ["DYNAMODB_TABLE"],
        KeyConditionExpression="pk = :pk AND begins_with ( sk , :attendee )",
        ProjectionExpression="attendee, #name, origin, prodid, #status",
        ExpressionAttributeNames={"#name": "name", "#status": "status"},
        ExpressionAttributeValues={
            ":pk": {"S": "event#{}".format(uid)},
            ":attendee": {"S": "attendee#"},
        },
        Limit=100,
        ConsistentRead=False,
    ).get("Items", [])


def sanitize(attendee_list):
    """Sanitize attendee list."""
    sanitized_attendee_list = []

    for attendee in attendee_list:
        sanitized_attendee_list.append(
            {
                "attendee": sanitize_sender_from(attendee["attendee"]["S"]),
                "name": sanitize_attendee(attendee["name"]["S"]),
                "status": attendee["status"]["S"],
                "origin": attendee["origin"]["S"],
                "prodid": attendee["prodid"]["S"],
            }
        )

    return sanitized_attendee_list


def sanitize_sender_from(email):
    """Sanitize sender email."""
    sender, domain = email.split("@")

    return "{sender}@{domain}".format(
        sender=sender[0] + ("*" * 7), domain=domain
    )


def sanitize_attendee(name):
    """Sanitize attendee name."""
    return name[0] + ("*" * 7)


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

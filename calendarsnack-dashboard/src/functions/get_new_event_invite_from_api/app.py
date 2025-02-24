"""Process new event invite from api."""

import json
import logging
import re
from os import environ

import boto3
from thirtyone import aws

# Variable Reuse
sns = boto3.client("sns")


def lambda_handler(event, _):
    """Handle lambda event."""
    configure_logging(environ.get("LOG_LEVEL", "WARNING"))
    logging.info(event)
    return get_event_invite_from_api(event)


def get_event_invite_from_api(request):
    """Get event invite from api request."""
    if request_is_valid(request):
        result = queue_invite_for_processing(get_request_values_from(request))
    else:
        result = {
            "statusCode": 400,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": "Failed",
        }

    return result


def request_is_valid(request):
    """Very basic organizer and uid check."""
    email = re.compile(r"(?i)^[^@\s\;'\"]+@([^@\s\.\;'\"]+\.){1,}[A-Z]{2,}$")
    uid = re.compile(r"^[a-z0-9]{40}")

    # Handles invalid requests with no query paramet
    if request["queryStringParameters"] is None:
        request["queryStringParameters"] = {}

    return (
        email.match(request["queryStringParameters"].get("email", ""))
        is not None
        and uid.match(request.get("pathParameters", {}).get("uid", ""))
        is not None
        and request["queryStringParameters"].get("origin", "api")
        in valid_origins()
    )
    # and request['queryStringParameters'].get('origin', 'api')
    # in valid_origins()


def valid_origins():
    """Return valid origins."""
    return (
        "api",
        "bulk",
        "convertkit",
        "emailcta",
        "hubspot",
        "klaviyo",
        "klaviyocta",
        "landingpage",
        "mailchimpcta",
        "multievent",
        "sendgrid",
        "sendgridcta",
        "shared",
        "singlesend",
        "test",
        "vip",
        "webform",
        "wix",
        "wixv2",
        "wix",
        "zoho",
    )


def get_request_values_from(request):
    """Get request values."""
    return {
        "uid": request["pathParameters"]["uid"].lower(),
        "email": request["queryStringParameters"]["email"].lower(),
        "name": request["queryStringParameters"].get("name", "customer"),
        "landing": get_landing_page_from(request["queryStringParameters"]),
        "origin": request["queryStringParameters"]
        .get("origin", "api")
        .lower(),
        "partstat": "noaction",
        "prodid": "31events//ses",
    }


def get_landing_page_from(request):
    """Produce landing page from request."""
    landing_page = request.pop("landing", "https://calendarsnack.com")

    if not landing_page.startswith("http"):
        # Default to http under the assumption that it will redirect to HTTPS
        landing_page = "http://" + landing_page

    return landing_page


def queue_invite_for_processing(request):
    """Queue invitee for an event invite."""
    status = {
        "statusCode": 302,
        "headers": {"Location": request.pop("landing")},
        "body": "Acknowledged",
    }

    aws.publish_sns_message(
        message=json.dumps({"default": json.dumps(request)}),
        arn=environ["NEW_EVENT_INVITE_REQUEST"],
        sns=sns,
    )

    return status


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

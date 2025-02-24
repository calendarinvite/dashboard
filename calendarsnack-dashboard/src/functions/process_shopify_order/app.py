"""Process shopify order."""

import json
import logging
from base64 import b64decode
from os import environ
from time import time

import boto3
from botocore.exceptions import ClientError

# Variable Reuse
DYNAMODB = boto3.client("dynamodb", region_name=environ["REGION"])
SNS = boto3.client("sns")


def lambda_handler(event, _):
    """Handle lambda event."""
    configure_logging(environ.get("LOG_LEVEL", "WARNING"))
    logging.info(event)
    return process_order(event)


def process_order(event):
    """Process shopify payment and enroll user."""
    try:
        order = get_order(event)
        purchase_email = order.get("email", None)
        order_number = order.get("order_number", None)

        for order_item in order["line_items"]:
            register_subscription(order_number, order_item, purchase_email)

        status = {"statusCode": 200}
    except KeyError as error:
        logging.warning("Invalid request: %s", error)
        status = {"statusCode": 404}
    # except Exception as error:
    #     logging.exception("Fatal error: %s", error)
    #     status = {"statusCode": 404}

    return status


def get_order(event):
    """Extract order from event.

    If base64, body is decoded from event['body']
    """
    if event.get("isBase64Encoded", False):
        encoded_order = b64decode(event["body"].encode("utf-8"))
        order = encoded_order.decode("utf-8")
    else:
        order = event["body"]

    return json.loads(order)


def register_subscription(order_number, order_item, purchase_email):
    """Enroll user's Calendar Snack subscription."""
    if valid_subscription(order_item, purchase_email):
        subscription = {
            "id": order_number,
            "product": order_item["name"],
            "product_id": order_item["product_id"],
            "purchase_email": purchase_email,
            "organizer_email": get_organizer_email(order_item, purchase_email),
        }

        complete_enrollment(subscription)
    else:
        raise InvalidRequest("Invalid request")


class InvalidRequest(Exception):
    """Except invalid request."""


def valid_subscription(order_item, purchase_email):
    """Validate subscription order.

    Ensure that all required fields exist in order.
    """
    required_fields = ("product_id", "name")
    is_valid = True

    if purchase_email:
        for field in required_fields:
            if not order_item.get(field, False):
                logging.warning("%s not available", field)
                is_valid = False
                break
    else:
        logging.warning("Purchase email unavailable")
        is_valid = False

    return is_valid


def get_organizer_email(order, purchase_email):
    """Get organizer email for subscription use.

    If specified, return custom organizer email field. If not specified, return
    the purchasing email to use as the organizer email.
    """
    if custom_organizer(order.get("properties", [{}])):
        organizer_email = order["properties"][0]["value"]
    else:
        organizer_email = purchase_email

    return organizer_email.lower()


def custom_organizer(custom_property):
    """Validate custom organizer email value exists."""
    return custom_property[0].get("name", "") == "email"


def complete_enrollment(request):
    """Create organizer enrollment record if it doesn't exist."""
    try:
        DYNAMODB.put_item(
            TableName=environ["DYNAMODB_TABLE"],
            Item={
                "pk": {"S": f'organizer#{request["organizer_email"]}'},
                "sk": {"S": f'subscription#{request["organizer_email"]}'},
                "invoice_id": {"S": str(request["id"])},
                "product": {"S": str(request["product"])},
                "product_id": {"S": str(request["product_id"])},
                "enrollment_date": {"N": str(int(time()))},
                "purchase_email": {"S": request["purchase_email"]},
                "organizer_email": {"S": request["organizer_email"]},
            },
            ConditionExpression=(
                "attribute_not_exists(pk) AND attribute_not_exists(sk)"
            ),
            ReturnConsumedCapacity="NONE",
        )

        send_notification_of_successful_enrollment(request)
    except ClientError as error:
        if (
            error.response["Error"]["Code"]
            == "ConditionalCheckFailedException"
        ):
            logging.warning("Organizer record already exists")
            # Create update check in future
        else:
            raise


def send_notification_of_successful_enrollment(event):
    """Notify the user that their order has been processed successfully."""
    return SNS.publish(
        TargetArn=environ["SUCCESSFUL_ENROLLMENT"],
        MessageStructure="json",
        Message=json.dumps(
            {"default": json.dumps({"mailto": event["organizer_email"]})}
        ),
    )


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

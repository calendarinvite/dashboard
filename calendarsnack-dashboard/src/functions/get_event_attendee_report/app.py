"""Get event attendee report."""

import logging
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from os import environ, path

import boto3
from thirtyone import aws

# Variable Reuse
codecommit = boto3.client("codecommit")
dynamodb = boto3.client("dynamodb", region_name=environ["REGION"])
dynamodb_table = environ["DYNAMODB_TABLE"]
ses = boto3.client("ses", region_name=environ["REGION"])


def lambda_handler(event, _):
    """Handle lambda event."""
    configure_logging(environ.get("LOG_LEVEL", "WARNING"))
    logging.info(event)
    generate_attendee_report_for(event["pathParameters"]["uid"])

    return {
        "statusCode": 200,
        "headers": {"Access-Control-Allow-Origin": "*"},
        "body": "Acknowledged",
    }


def generate_attendee_report_for(uid):
    """Generate attendee report for uid."""
    event = {"uid": uid}
    event.update({"attendees": get_attendee_list_for(uid)})
    event.update(get_organizer_email_for(event))
    send_report_to_organizer_for(generate_csv_report_for(event))


def get_attendee_list_for(uid):
    """Get attendee list for uid."""
    return dynamodb.query(
        TableName=environ["DYNAMODB_TABLE"],
        KeyConditionExpression="pk = :pk AND begins_with ( sk , :attendee )",
        ProjectionExpression=(
            "attendee, mailto, #name, origin, prodid, #status"
        ),
        ExpressionAttributeNames={"#name": "name", "#status": "status"},
        ExpressionAttributeValues={
            ":pk": {"S": "event#{}".format(uid)},
            ":attendee": {"S": "attendee#"},
        },
        ConsistentRead=False,
    ).get("Items", [])


def get_organizer_email_for(event):
    """Get organizer email for event."""
    if len(event["attendees"]) > 0:
        organizer_email = event["attendees"][0]["mailto"]["S"]
    else:
        organizer_email = get_organizer_email_from(event["uid"])

    return {"mailto": organizer_email}


def get_organizer_email_from(uid):
    """Get organizer email from uid."""
    return aws.get_dynamodb_record_for(
        "event#{}".format(uid),
        secondary_key="event#{}".format(uid),
        dynamodb=dynamodb,
        dynamodb_table=dynamodb_table,
    )["mailto"]


def generate_csv_report_for(event):
    """Generate csv report for event."""
    event["report_location"] = environ["LOCAL_CSV_FILE"].format(event["uid"])
    attendee_list = event.pop("attendees", [])

    with open(event["report_location"], "w", encoding="utf8") as csv:
        export = ["email,name,status,origin,prodid"]

        for attendee in attendee_list:
            export.append(
                "{email},{name},{status},{origin},{prodid}".format(
                    email=attendee["attendee"]["S"],
                    name=attendee["name"]["S"],
                    status=attendee["status"]["S"],
                    origin=attendee["origin"]["S"],
                    prodid=attendee["prodid"]["S"],
                )
            )

        csv.write("\n".join(export) + "\n")
        csv.close()

    return event


def send_report_to_organizer_for(event):
    """Send report to organizer for event."""
    report_email = MIMEMultipart("mixed")
    report_email["Subject"] = environ["SUBJECT"].format(event["uid"])
    report_email["From"] = environ["SENDER"]
    report_email["To"] = event["mailto"]

    report_email_body = MIMEText(
        get_attendee_report_email_template_for(event), "html"
    )

    report_email.attach(report_email_body)

    attachment = MIMEApplication(open(event["report_location"], "rb").read())

    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename=path.basename(event["report_location"]),
    )

    report_email.attach(attachment)

    ses.send_raw_email(
        Source=environ["SENDER"],
        Destinations=[event["mailto"]],
        RawMessage={
            "Data": report_email.as_string(),
        },
    )


def get_attendee_report_email_template_for(event):
    """Get attendee report email template for event."""
    attendee_report_email_template = aws.get_codecommit_file_for(
        environ["ATTENDEE_REPORT_EMAIL"],
        repository=environ["CODECOMMIT_REPO"],
        codecommit=codecommit,
    )

    return attendee_report_email_template.replace("{uid}", event["uid"])


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

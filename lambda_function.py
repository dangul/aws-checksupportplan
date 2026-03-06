import boto3
import os
from datetime import date, timedelta

ce = boto3.client("ce")
org = boto3.client("organizations")
ses = boto3.client("ses", region_name="eu-north-1")

SENDER = os.environ.get("SENDER")
RECIPIENTS = os.environ.get("RECIPIENTS")
TEST_NO_ACCOUNT = os.environ.get("TESTNOACCOUNT", "false").lower() == "true"
COST_EXPLORER_LINK = os.environ.get("COST_EXPLORER_LINK")

if not SENDER or not RECIPIENTS:
    raise Exception("SENDER and RECIPIENTS environment variables must be set")

RECIPIENT_LIST = [email.strip() for email in RECIPIENTS.split(",")]


# -----------------------------
# Get previous month period
# -----------------------------
def get_previous_month_period():
    today = date.today()
    first_day_this_month = today.replace(day=1)
    last_day_last_month = first_day_this_month - timedelta(days=1)
    first_day_last_month = last_day_last_month.replace(day=1)

    return (
        first_day_last_month.strftime("%Y-%m-%d"),
        first_day_this_month.strftime("%Y-%m-%d"),
    )


# -----------------------------
# Get AWS Account Names
# -----------------------------
def get_account_names():
    accounts = {}
    paginator = org.get_paginator("list_accounts")

    for page in paginator.paginate():
        for acct in page["Accounts"]:
            accounts[acct["Id"]] = acct["Name"]

    return accounts


# -----------------------------
# Lambda Handler
# -----------------------------
def lambda_handler(event, context):

    start_date, end_date = get_previous_month_period()
    account_names = get_account_names()

    support_accounts = {}

    if not TEST_NO_ACCOUNT:

        response = ce.get_cost_and_usage(
            TimePeriod={
                "Start": start_date,
                "End": end_date
            },
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[
                {"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"},
                {"Type": "DIMENSION", "Key": "SERVICE"},
            ],
        )

        for result in response["ResultsByTime"]:
            for group in result["Groups"]:
                account_id = group["Keys"][0]
                service = group["Keys"][1]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])

                if "Support" in service and amount > 0:
                    if account_id not in support_accounts:
                        support_accounts[account_id] = {
                            "services": [],
                            "total": 0
                        }

                    support_accounts[account_id]["services"].append(service)
                    support_accounts[account_id]["total"] += amount

    sorted_accounts = sorted(
        support_accounts.items(),
        key=lambda x: x[1]["total"],
        reverse=True
    )

    grand_total = sum(data["total"] for _, data in sorted_accounts)

    # -----------------------------
    # Build HTML Email
    # -----------------------------
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2>AWS Support Plan Report</h2>
        <p><strong>Period:</strong> {start_date} to {(date.fromisoformat(end_date) - timedelta(days=1))}</p>
    """

    if TEST_NO_ACCOUNT or not sorted_accounts:
        html_body += """
        <p style="color: green;">
            No AWS accounts incurred Support charges during this period.<br>
            All accounts are likely operating under Basic Support.
        </p>
        """

        if TEST_NO_ACCOUNT:
            html_body += """
            <p style="font-size: 12px; color: orange;">
                (Test mode enabled – TESTNOACCOUNT=true)
            </p>
            """
    else:
        html_body += """
        <p>The following accounts have paid Support plans:</p>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">
            <tr style="background-color: #f2f2f2;">
                <th>Account Name</th>
                <th>Account ID</th>
                <th>Support Type</th>
                <th>Total Support Cost (USD)</th>
            </tr>
        """

        for account_id, data in sorted_accounts:
            account_name = account_names.get(account_id, "Unknown Account")
            services = ", ".join(set(data["services"]))
            total = round(data["total"], 2)

            html_body += f"""
            <tr>
                <td>{account_name}</td>
                <td>{account_id}</td>
                <td>{services}</td>
                <td>${total}</td>
            </tr>
            """

        html_body += f"""
            <tr style="font-weight: bold; background-color: #f9f9f9;">
                <td colspan="3" align="right">Total Support Cost</td>
                <td>${round(grand_total, 2)}</td>
            </tr>
        </table>
        """

    # -----------------------------
    # Cost Explorer Link Section
    # -----------------------------
    if COST_EXPLORER_LINK:
        html_body += f"""
        <br>
        <hr>
        <p>
            If you would like to view detailed information in AWS Cost Explorer,
            please log in to the <strong>TCXN Billing account</strong> and open the link below:
        </p>
        <p>
            <a href="{COST_EXPLORER_LINK}" target="_blank">
                Open detailed Support Cost report in Cost Explorer
            </a>
        </p>
        """

    html_body += """
        <hr>
        <p style="font-size: 12px; color: gray;">
            Generated automatically by AWS Cost Monitoring Lambda.
        </p>
    </body>
    </html>
    """

    # -----------------------------
    # Send Email
    # -----------------------------
    ses.send_email(
        Source=SENDER,
        Destination={"ToAddresses": RECIPIENT_LIST},
        Message={
            "Subject": {
                "Data": f"AWS Support Report – {start_date} to {end_date}"
            },
            "Body": {
                "Html": {"Data": html_body}
            },
        },
    )

    return {
        "statusCode": 200,
        "body": "Support report sent successfully"
    }

# AWS Support Cost Monitoring Lambda
## Overview

This Lambda function generates a monthly AWS Support cost report and sends it via email using Amazon SES.

The report covers the previous calendar month and includes:

- Account Name and ID
- Support Type
- Total Support Cost (USD)
- Grand total across all accounts
- Direct link to AWS Cost Explorer

---

## Architecture

- **AWS Lambda** (runtime: Python)
- **AWS Cost Explorer API** (cost data retrieval)
- **AWS Organizations** (account information)
- **Amazon SES** (email delivery)
- **Amazon EventBridge** (scheduled execution)

---

## Environment Variables

| Variable             | Required | Description                              |
| -------------------- | -------- | ---------------------------------------- |
| `SENDER`             | Yes      | Verified SES sender email address        |
| `RECIPIENTS`         | Yes      | Comma-separated list of recipient emails |
| `TESTNOACCOUNT`      | No       | Set to `true` to simulate zero accounts  |
| `COST_EXPLORER_LINK` | No       | Direct link to Cost Explorer report      |

---

## IAM Permissions Required

The Lambda execution role requires:

- `ce:GetCostAndUsage` (Cost Explorer)
- `organizations:ListAccounts` (Organizations)
- `ses:SendEmail` (SES)

---

## How It Works

1. Calculates the previous month period
2. Fetches cost data from Cost Explorer API grouped by account and service
3. Filters for AWS Support-related services
4. Aggregates totals per account and sorts by highest cost
5. Generates an HTML email report
6. Sends the email using Amazon SES

**Test Mode:** Set `TESTNOACCOUNT=true` to skip cost retrieval and send a "No Support charges" report.

---

## Setup Requirements

- SES sender email must be verified
- If SES is in sandbox mode, recipient emails must also be verified
- Lambda must run in a region where SES is available

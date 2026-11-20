"""Circuit breaker: stop the API function by setting its reserved concurrency to 0.

Invoked by CloudWatch alarms when invocations are unusually high. With concurrency 0
every request is throttled, and Lambda doesn't bill throttled requests. Re-enable by
re-applying the api-function stack, which restores its configured concurrency.
"""

import json
import os

import boto3

lambda_client = boto3.client("lambda")


def handler(event, context):
    target = os.environ["TARGET_FUNCTION"]
    alarm = event.get("alarmData", {}).get("alarmName", "unknown alarm")
    state = event.get("alarmData", {}).get("state", {}).get("value")

    if state != "ALARM":
        print(json.dumps({"action": "none", "alarm": alarm, "state": state}))
        return {"stopped": False}

    lambda_client.put_function_concurrency(FunctionName=target, ReservedConcurrentExecutions=0)
    print(json.dumps({"action": "stopped", "function": target, "alarm": alarm}))
    return {"stopped": True, "function": target}

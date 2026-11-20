#!/usr/bin/env bash
# Deploy a built package to one environment's function:
#
#   scripts/deploy.sh <function-name> <path/to/lambda.zip>
#
# 1. Upload the code and publish it as a numbered version. If `live` already runs this
#    exact package, stop: re-running is safe.
# 2. Ask CodeDeploy to move the `live` alias to that version, using the environment's
#    deployment config (all at once in staging, a 10% canary in production), and wait.
#    If the error alarm fires, CodeDeploy moves the alias back and this script fails.
set -euo pipefail

function_name="$1"
package="$2"
alias_name=live
deployment_group=live # see infra/terragrunt/modules/deployment
# shellcheck disable=SC2016 # the literal name of Lambda's unpublished version
latest='$LATEST'

package_sha=$(openssl dgst -sha256 -binary "$package" | base64)
current=$(aws lambda get-alias --function-name "$function_name" --name "$alias_name" \
  --query FunctionVersion --output text)
live_sha=$(aws lambda get-function-configuration --function-name "$function_name" \
  --qualifier "$current" --query CodeSha256 --output text)
if [[ "$current" != "$latest" && "$live_sha" == "$package_sha" ]]; then
  echo "$alias_name (version $current) already runs this package; nothing to deploy"
  exit 0
fi

echo "Uploading $package to $function_name"
aws lambda update-function-code --function-name "$function_name" \
  --zip-file "fileb://$package" --output text --query CodeSha256 >/dev/null
aws lambda wait function-updated --function-name "$function_name"

code_sha=$(aws lambda get-function-configuration --function-name "$function_name" \
  --query CodeSha256 --output text)
version=$(aws lambda publish-version --function-name "$function_name" \
  --code-sha256 "$code_sha" --query Version --output text)
echo "Published version $version; $alias_name is on $current"

if [[ "$current" == "$latest" ]]; then
  # First deploy: there's no earlier version for CodeDeploy to shift from.
  aws lambda update-alias --function-name "$function_name" --name "$alias_name" \
    --function-version "$version" --output text --query AliasArn >/dev/null
  echo "$alias_name now on version $version (first deploy, no canary)"
  exit 0
fi

appspec=$(jq -cn --arg fn "$function_name" --arg alias "$alias_name" \
  --arg from "$current" --arg to "$version" '{
    version: 0.0,
    Resources: [{api: {Type: "AWS::Lambda::Function", Properties: {
      Name: $fn, Alias: $alias, CurrentVersion: $from, TargetVersion: $to}}}]
  }')
request=$(jq -cn --arg app "$function_name" --arg group "$deployment_group" --arg spec "$appspec" '{
  applicationName: $app,
  deploymentGroupName: $group,
  revision: {revisionType: "AppSpecContent", appSpecContent: {content: $spec}}
}')

deployment_id=$(aws deploy create-deployment --cli-input-json "$request" \
  --query deploymentId --output text)
echo "CodeDeploy deployment $deployment_id: $alias_name $current -> $version"

if ! aws deploy wait deployment-successful --deployment-id "$deployment_id"; then
  aws deploy get-deployment --deployment-id "$deployment_id" \
    --query 'deploymentInfo.[status, errorInformation.message]' --output text
  echo "Deployment failed; CodeDeploy keeps (or puts back) $alias_name on version $current" >&2
  exit 1
fi
echo "$alias_name now on version $version"

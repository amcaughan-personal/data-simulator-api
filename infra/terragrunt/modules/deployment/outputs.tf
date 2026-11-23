output "codedeploy_app" {
  value = aws_codedeploy_app.this.name
}

output "deployment_group" {
  value = aws_codedeploy_deployment_group.live.deployment_group_name
}

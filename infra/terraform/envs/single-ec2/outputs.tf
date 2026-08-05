output "public_ip" {
  value = aws_eip.this.public_ip
}

output "instance_id" {
  value = aws_instance.this.id
}

output "url" {
  value = var.domain_name != "" ? "https://${var.domain_name}" : "http://${aws_eip.this.public_ip}"
}

output "connect_command" {
  description = "No SSH key, no open port 22 — this is the only way in."
  value       = "aws ssm start-session --target ${aws_instance.this.id} --profile ${var.aws_profile} --region ${var.aws_region}"
}

output "route53_name_servers" {
  value = var.domain_name != "" && var.route53_zone_id == "" ? aws_route53_zone.this[0].name_servers : []
}

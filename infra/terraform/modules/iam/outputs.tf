output "core_api_role_arn" {
  value = aws_iam_role.core_api.arn
}

output "kms_key_arn" {
  value = aws_kms_key.encryption.arn
}

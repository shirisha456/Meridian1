# IRSA (IAM Roles for Service Accounts): lets core-api's pod assume this
# role via its Kubernetes service account token, federated through the
# cluster's OIDC provider — no long-lived AWS credentials baked into the
# image or a Kubernetes Secret.
data "aws_iam_policy_document" "assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:${var.namespace}:${var.service_account_name}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "core_api" {
  name               = "${var.name}-core-api"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json

  tags = var.tags
}

# Production-grade replacement for the local Fernet key used to encrypt
# Plaid access tokens at rest (ADR-0003's documented stand-in) — this is
# the real KMS envelope encryption key that stand-in is meant to become
# once this Terraform is actually applied.
resource "aws_kms_key" "encryption" {
  description             = "${var.name} - Plaid access token envelope encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = var.tags
}

data "aws_iam_policy_document" "core_api_permissions" {
  statement {
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = var.secret_arns
  }

  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [aws_kms_key.encryption.arn]
  }
}

resource "aws_iam_role_policy" "core_api" {
  name   = "${var.name}-core-api"
  role   = aws_iam_role.core_api.id
  policy = data.aws_iam_policy_document.core_api_permissions.json
}

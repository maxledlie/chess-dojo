resource "aws_acm_certificate" "chess" {
  provider          = aws.us_east_1
  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = { Name = var.domain_name }
}

# This resource blocks until the cert is validated.
# Before running a full `terraform apply`, add the CNAME from the
# `acm_validation_cnames` output to your domain name provider's DNS and wait for validation.
resource "aws_acm_certificate_validation" "chess" {
  provider        = aws.us_east_1
  certificate_arn = aws_acm_certificate.chess.arn
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain name — set this as the CNAME target for the chess app's URL"
  value       = aws_cloudfront_distribution.main.domain_name
}

output "acm_validation_cnames" {
  description = "CNAME records to add to domain name provider DNS for ACM certificate validation"
  value = {
    for dvo in aws_acm_certificate.chess.domain_validation_options : dvo.domain_name => {
      name  = dvo.resource_record_name
      value = dvo.resource_record_value
      type  = dvo.resource_record_type
    }
  }
}

output "ecr_repo_url" {
  description = "ECR repository URL for pushing backend images"
  value       = aws_ecr_repository.main.repository_url
}

output "alb_dns" {
  description = "ALB DNS name"
  value       = aws_lb.main.dns_name
}

output "s3_bucket_name" {
  description = "S3 bucket name for frontend assets"
  value       = aws_s3_bucket.frontend.bucket
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (needed for cache invalidations)"
  value       = aws_cloudfront_distribution.main.id
}

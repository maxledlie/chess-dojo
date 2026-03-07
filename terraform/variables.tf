variable "app_name" {
  description = "Application name used as a prefix for resource names"
  type        = string
  default     = "cress"
}

variable "aws_region" {
  description = "AWS region for primary resources"
  type        = string
  default     = "eu-west-2"
}

variable "domain_name" {
  description = "Full domain name for the app"
  type        = string
  default     = "chess.maxledlie.com"
}

variable "container_image" {
  description = "Full ECR image URI to deploy (e.g. 123456789.dkr.ecr.eu-west-2.amazonaws.com/cress:latest)"
  type        = string
  default     = "168380805746.dkr.ecr.eu-west-2.amazonaws.com/cress:latest"
}

resource "aws_secretsmanager_secret" "session_secret" {
  name                    = "${var.app_name}/session-secret"
  description             = "SESSION_SECRET for itsdangerous cookie signing"
  recovery_window_in_days = 0 # Allow immediate deletion when destroying

  tags = { Name = "${var.app_name}-session-secret" }
}

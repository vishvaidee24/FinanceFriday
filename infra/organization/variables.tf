variable "aws_region" {
  description = "AWS region used for Organizations API calls and provider configuration."
  type        = string
  default     = "us-east-1"
}

variable "finance_account_name" {
  description = "Friendly name for the finance development AWS member account."
  type        = string
  default     = "finance-dev"
}

variable "finance_account_email" {
  description = "Globally unique root email address for the new finance AWS account."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.finance_account_email))
    error_message = "finance_account_email must be a valid email address."
  }
}

variable "finance_ou_name" {
  description = "Organizational Unit that contains finance AWS accounts."
  type        = string
  default     = "Finance"
}

variable "organization_access_role_name" {
  description = "Cross-account admin role AWS Organizations creates in the new member account."
  type        = string
  default     = "OrganizationAccountAccessRole"
}

variable "project_name" {
  description = "Project tag applied to the finance member account."
  type        = string
  default     = "finance-platform"
}

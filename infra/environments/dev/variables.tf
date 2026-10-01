variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "finance_account_id" {
  description = "AWS account ID created by infra/organization."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.finance_account_id))
    error_message = "finance_account_id must be a 12-digit AWS account ID."
  }
}

variable "organization_access_role_name" {
  description = "Cross-account role created by AWS Organizations in finance-dev."
  type        = string
  default     = "OrganizationAccountAccessRole"
}

variable "project_name" {
  type    = string
  default = "finance-platform"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "public_subnet_cidr" {
  type    = string
  default = "10.20.1.0/24"
}

variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.20.11.0/24", "10.20.12.0/24"]
}

variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}

variable "db_name" {
  type    = string
  default = "finance"
}

variable "db_username" {
  type    = string
  default = "finance_admin"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_allocated_storage" {
  type    = number
  default = 20
}

variable "db_max_allocated_storage" {
  type    = number
  default = 100
}

variable "project_name" { type = string }
variable "vpc_cidr" { type = string }
variable "public_subnet_cidr" { type = string }

variable "private_subnet_cidrs" {
  type = list(string)
  validation {
    condition     = length(var.private_subnet_cidrs) >= 2
    error_message = "At least two private subnets are required."
  }
}

variable "availability_zones" {
  type = list(string)
  validation {
    condition     = length(var.availability_zones) >= 2
    error_message = "At least two availability zones are required."
  }
}

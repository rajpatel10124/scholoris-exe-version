variable "region" {
  default = "us-east-1" # You can change this to ap-south-1 (Mumbai)
}

variable "instance_type" {
  default = "m7i-flex.large" # Free Tier eligible (Current Generation)
}

variable "project_name" {
  default = "scholaris-project"
}
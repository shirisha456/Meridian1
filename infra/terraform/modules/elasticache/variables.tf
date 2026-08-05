variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "allowed_security_group_id" {
  type = string
}

variable "node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "num_cache_clusters" {
  description = "1 keeps dev cost down; 2+ enables automatic failover for a real prod deployment."
  type        = number
  default     = 1
}

variable "tags" {
  type    = map(string)
  default = {}
}

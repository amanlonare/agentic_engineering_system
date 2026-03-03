# Mobile Terraform Infrastructure

This repository contains the Infrastructure as Code (IaC) definitions for the entire Mobile platform.

## Architectural Overview
We use HashiCorp Terraform to provision and manage our cloud infrastructure on AWS. This ensures reproducible and version-controlled environments (Dev, Staging, Prod).

## Core Responsibilities
- **Compute Provisioning**: ECS clusters and Fargate tasks for `mobile-backend` and `mobile-prediction-service`.
- **Database Provisioning**: RDS instances for PostgreSQL.
- **Storage**: S3 buckets for the `mobile-prediction-service` raw data.
- **Networking**: VPCs, subnets, and load balancers.

## Directory Structure
- `main.tf`: Core infrastructure definitions (ECS, RDS).
- `variables.tf`: Input variables for environemnt configuration.
- `outputs.tf`: Exported values like load balancer URLs.
- `modules/`: Reusable Terraform modules.

## Key Technologies
- **IaC**: Terraform
- **Cloud Provider**: AWS

*Note: For the mock environment, actual implementation files may be missing. Assume the interfaces exist as described.*

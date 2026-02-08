# JunkOS Backend - Enterprise AWS Deployment

Complete guide for deploying JunkOS backend on AWS with ECS/Fargate, RDS, and full production infrastructure.

## Overview

**Best for:** Enterprise applications, high-scale, compliance requirements, full AWS ecosystem integration

**Architecture:**
```
Internet → Route53 → ALB → ECS Fargate → RDS PostgreSQL
                      ↓
                  CloudWatch Logs
```

**Estimated Cost:** $30-100+/month (scales with usage)

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Step-by-Step Setup](#step-by-step-setup)
4. [Infrastructure as Code](#infrastructure-as-code)
5. [CI/CD Pipeline](#cicd-pipeline)
6. [Monitoring & Logging](#monitoring--logging)
7. [Security Best Practices](#security-best-practices)
8. [Cost Optimization](#cost-optimization)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- [ ] AWS account with billing enabled
- [ ] AWS CLI installed and configured
- [ ] Docker installed locally
- [ ] Domain name (for Route53)
- [ ] Basic AWS knowledge (VPC, IAM, ECS)
- [ ] 2-4 hours for initial setup

**AWS CLI Setup:**
```bash
# Install AWS CLI
brew install awscli  # macOS
# or: pip install awscli

# Configure credentials
aws configure
# Enter: Access Key ID, Secret Access Key, Region (us-east-1), Output format (json)
```

---

## Architecture Overview

### Production Infrastructure

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                    ┌────▼────┐
                    │ Route53 │ (DNS)
                    └────┬────┘
                         │
                    ┌────▼─────┐
                    │   ALB    │ (Load Balancer, SSL)
                    └────┬─────┘
                         │
            ┌────────────┼────────────┐
            │                         │
       ┌────▼─────┐             ┌────▼─────┐
       │  ECS     │             │  ECS     │
       │ Fargate  │             │ Fargate  │
       │ Task 1   │             │ Task 2   │
       └────┬─────┘             └────┬─────┘
            │                         │
            └────────────┬────────────┘
                         │
                    ┌────▼─────┐
                    │   RDS    │ (PostgreSQL)
                    │ Multi-AZ │
                    └──────────┘
```

### AWS Services Used

| Service | Purpose | Cost/month |
|---------|---------|------------|
| **ECS Fargate** | Container hosting | $15-30 |
| **RDS PostgreSQL** | Database (Multi-AZ) | $15-50 |
| **Application Load Balancer** | Traffic distribution | $16 |
| **CloudWatch** | Logs & monitoring | $5-10 |
| **Route53** | DNS management | $0.50 |
| **ACM** | SSL certificates | Free |
| **ECR** | Docker image registry | $1-5 |
| **Secrets Manager** | Secret storage | $1-2 |
| **Total** | | **$53-114/month** |

---

## Step-by-Step Setup

### 1. Create VPC and Networking (15 min)

#### Create VPC

```bash
# Create VPC
aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=junkos-vpc}]'

# Enable DNS
aws ec2 modify-vpc-attribute \
  --vpc-id vpc-xxxxx \
  --enable-dns-hostnames
```

#### Create Subnets (2 public, 2 private)

```bash
# Public Subnet 1 (us-east-1a)
aws ec2 create-subnet \
  --vpc-id vpc-xxxxx \
  --cidr-block 10.0.1.0/24 \
  --availability-zone us-east-1a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=junkos-public-1a}]'

# Public Subnet 2 (us-east-1b)
aws ec2 create-subnet \
  --vpc-id vpc-xxxxx \
  --cidr-block 10.0.2.0/24 \
  --availability-zone us-east-1b \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=junkos-public-1b}]'

# Private Subnet 1 (us-east-1a) - for ECS tasks
aws ec2 create-subnet \
  --vpc-id vpc-xxxxx \
  --cidr-block 10.0.10.0/24 \
  --availability-zone us-east-1a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=junkos-private-1a}]'

# Private Subnet 2 (us-east-1b) - for ECS tasks
aws ec2 create-subnet \
  --vpc-id vpc-xxxxx \
  --cidr-block 10.0.11.0/24 \
  --availability-zone us-east-1b \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=junkos-private-1b}]'

# Database Subnet 1 (us-east-1a)
aws ec2 create-subnet \
  --vpc-id vpc-xxxxx \
  --cidr-block 10.0.20.0/24 \
  --availability-zone us-east-1a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=junkos-db-1a}]'

# Database Subnet 2 (us-east-1b)
aws ec2 create-subnet \
  --vpc-id vpc-xxxxx \
  --cidr-block 10.0.21.0/24 \
  --availability-zone us-east-1b \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=junkos-db-1b}]'
```

#### Create Internet Gateway

```bash
aws ec2 create-internet-gateway \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=junkos-igw}]'

aws ec2 attach-internet-gateway \
  --vpc-id vpc-xxxxx \
  --internet-gateway-id igw-xxxxx
```

#### Configure Route Tables

```bash
# Create public route table
aws ec2 create-route-table \
  --vpc-id vpc-xxxxx \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=junkos-public-rt}]'

# Add route to internet gateway
aws ec2 create-route \
  --route-table-id rtb-xxxxx \
  --destination-cidr-block 0.0.0.0/0 \
  --gateway-id igw-xxxxx

# Associate public subnets with public route table
aws ec2 associate-route-table --subnet-id subnet-public1 --route-table-id rtb-xxxxx
aws ec2 associate-route-table --subnet-id subnet-public2 --route-table-id rtb-xxxxx
```

#### Create NAT Gateway (for private subnet internet access)

```bash
# Allocate Elastic IP
aws ec2 allocate-address --domain vpc

# Create NAT Gateway in public subnet
aws ec2 create-nat-gateway \
  --subnet-id subnet-public1 \
  --allocation-id eipalloc-xxxxx \
  --tag-specifications 'ResourceType=nat-gateway,Tags=[{Key=Name,Value=junkos-nat}]'

# Create private route table with NAT
aws ec2 create-route-table \
  --vpc-id vpc-xxxxx \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=junkos-private-rt}]'

aws ec2 create-route \
  --route-table-id rtb-private \
  --destination-cidr-block 0.0.0.0/0 \
  --nat-gateway-id nat-xxxxx

# Associate private subnets
aws ec2 associate-route-table --subnet-id subnet-private1 --route-table-id rtb-private
aws ec2 associate-route-table --subnet-id subnet-private2 --route-table-id rtb-private
```

---

### 2. Create RDS PostgreSQL Database (20 min)

#### Create DB Subnet Group

```bash
aws rds create-db-subnet-group \
  --db-subnet-group-name junkos-db-subnet-group \
  --db-subnet-group-description "JunkOS database subnet group" \
  --subnet-ids subnet-db1 subnet-db2 \
  --tags Key=Name,Value=junkos-db-subnet-group
```

#### Create Security Group for RDS

```bash
aws ec2 create-security-group \
  --group-name junkos-db-sg \
  --description "Security group for JunkOS RDS database" \
  --vpc-id vpc-xxxxx

# Allow PostgreSQL from ECS security group (create ECS SG first, then update)
aws ec2 authorize-security-group-ingress \
  --group-id sg-db-xxxxx \
  --protocol tcp \
  --port 5432 \
  --source-group sg-ecs-xxxxx
```

#### Create RDS Instance

```bash
# Generate strong password
DB_PASSWORD=$(openssl rand -base64 32)
echo "Save this password: $DB_PASSWORD"

# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier junkos-prod-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15.4 \
  --master-username junkosadmin \
  --master-user-password "$DB_PASSWORD" \
  --allocated-storage 20 \
  --storage-type gp3 \
  --storage-encrypted \
  --db-subnet-group-name junkos-db-subnet-group \
  --vpc-security-group-ids sg-db-xxxxx \
  --backup-retention-period 7 \
  --preferred-backup-window "03:00-04:00" \
  --preferred-maintenance-window "mon:04:00-mon:05:00" \
  --multi-az \
  --publicly-accessible false \
  --enable-cloudwatch-logs-exports '["postgresql"]' \
  --tags Key=Name,Value=junkos-prod-db Key=Environment,Value=production
```

**Wait for database to be available (~10 minutes):**
```bash
aws rds wait db-instance-available --db-instance-identifier junkos-prod-db
```

#### Store Database Credentials in Secrets Manager

```bash
aws secretsmanager create-secret \
  --name junkos/production/database \
  --description "JunkOS production database credentials" \
  --secret-string "{\"username\":\"junkosadmin\",\"password\":\"$DB_PASSWORD\",\"host\":\"junkos-prod-db.xxxxx.us-east-1.rds.amazonaws.com\",\"port\":5432,\"database\":\"postgres\"}"
```

---

### 3. Create ECR Repository (5 min)

```bash
# Create ECR repository for Docker images
aws ecr create-repository \
  --repository-name junkos/backend \
  --image-scanning-configuration scanOnPush=true \
  --encryption-configuration encryptionType=AES256 \
  --tags Key=Name,Value=junkos-backend

# Get repository URI
aws ecr describe-repositories --repository-names junkos/backend
# Output: 123456789012.dkr.ecr.us-east-1.amazonaws.com/junkos/backend
```

#### Build and Push Docker Image

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

# Build image
docker build -t junkos/backend:latest .

# Tag for ECR
docker tag junkos/backend:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/junkos/backend:latest

# Push to ECR
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/junkos/backend:latest
```

**Dockerfile example:**
```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .

EXPOSE 8080

CMD ["node", "server.js"]
```

---

### 4. Create ECS Cluster and Service (30 min)

#### Create ECS Cluster

```bash
aws ecs create-cluster \
  --cluster-name junkos-prod \
  --capacity-providers FARGATE FARGATE_SPOT \
  --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 \
  --tags key=Name,value=junkos-prod key=Environment,value=production
```

#### Create IAM Roles

**ECS Task Execution Role (for pulling images, logging):**
```bash
# Create trust policy
cat > ecs-task-execution-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

aws iam create-role \
  --role-name junkosEcsTaskExecutionRole \
  --assume-role-policy-document file://ecs-task-execution-trust-policy.json

aws iam attach-role-policy \
  --role-name junkosEcsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Add Secrets Manager access
cat > secrets-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:junkos/*"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name junkosEcsTaskExecutionRole \
  --policy-name SecretsManagerAccess \
  --policy-document file://secrets-policy.json
```

**ECS Task Role (for application permissions):**
```bash
aws iam create-role \
  --role-name junkosEcsTaskRole \
  --assume-role-policy-document file://ecs-task-execution-trust-policy.json

# Add policies as needed (S3, SES, etc.)
```

#### Create CloudWatch Log Group

```bash
aws logs create-log-group --log-group-name /ecs/junkos-backend
aws logs put-retention-policy --log-group-name /ecs/junkos-backend --retention-in-days 30
```

#### Create ECS Task Definition

```bash
cat > task-definition.json <<EOF
{
  "family": "junkos-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::123456789012:role/junkosEcsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::123456789012:role/junkosEcsTaskRole",
  "containerDefinitions": [
    {
      "name": "junkos-backend",
      "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/junkos/backend:latest",
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "essential": true,
      "environment": [
        {
          "name": "NODE_ENV",
          "value": "production"
        },
        {
          "name": "PORT",
          "value": "8080"
        }
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:junkos/production/database:DATABASE_URL::"
        },
        {
          "name": "JWT_SECRET",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:junkos/production/app:JWT_SECRET::"
        },
        {
          "name": "STRIPE_SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:junkos/production/stripe:SECRET_KEY::"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/junkos-backend",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
EOF

aws ecs register-task-definition --cli-input-json file://task-definition.json
```

#### Create Security Groups

```bash
# ALB Security Group
aws ec2 create-security-group \
  --group-name junkos-alb-sg \
  --description "Security group for JunkOS ALB" \
  --vpc-id vpc-xxxxx

aws ec2 authorize-security-group-ingress \
  --group-id sg-alb-xxxxx \
  --protocol tcp --port 443 --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress \
  --group-id sg-alb-xxxxx \
  --protocol tcp --port 80 --cidr 0.0.0.0/0

# ECS Security Group
aws ec2 create-security-group \
  --group-name junkos-ecs-sg \
  --description "Security group for JunkOS ECS tasks" \
  --vpc-id vpc-xxxxx

aws ec2 authorize-security-group-ingress \
  --group-id sg-ecs-xxxxx \
  --protocol tcp --port 8080 --source-group sg-alb-xxxxx
```

---

### 5. Create Application Load Balancer (20 min)

#### Create ALB

```bash
aws elbv2 create-load-balancer \
  --name junkos-alb \
  --subnets subnet-public1 subnet-public2 \
  --security-groups sg-alb-xxxxx \
  --scheme internet-facing \
  --type application \
  --ip-address-type ipv4 \
  --tags Key=Name,Value=junkos-alb
```

#### Create Target Group

```bash
aws elbv2 create-target-group \
  --name junkos-backend-tg \
  --protocol HTTP \
  --port 8080 \
  --vpc-id vpc-xxxxx \
  --target-type ip \
  --health-check-enabled \
  --health-check-protocol HTTP \
  --health-check-path /health \
  --health-check-interval-seconds 30 \
  --health-check-timeout-seconds 5 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3
```

#### Request SSL Certificate (ACM)

```bash
aws acm request-certificate \
  --domain-name api.junkos.com \
  --validation-method DNS \
  --subject-alternative-names api.junkos.com \
  --tags Key=Name,Value=junkos-api-cert
```

**Validate certificate:**
1. Get validation CNAME from ACM console
2. Add CNAME record to Route53
3. Wait for validation (~5-10 minutes)

#### Create HTTPS Listener

```bash
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/junkos-alb/xxxxx \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=arn:aws:acm:us-east-1:123456789012:certificate/xxxxx \
  --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/junkos-backend-tg/xxxxx
```

#### Create HTTP → HTTPS Redirect

```bash
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/junkos-alb/xxxxx \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=redirect,RedirectConfig="{Protocol=HTTPS,Port=443,StatusCode=HTTP_301}"
```

---

### 6. Create ECS Service

```bash
aws ecs create-service \
  --cluster junkos-prod \
  --service-name junkos-backend \
  --task-definition junkos-backend:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --platform-version LATEST \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-private1,subnet-private2],securityGroups=[sg-ecs-xxxxx],assignPublicIp=DISABLED}" \
  --load-balancers targetGroupArn=arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/junkos-backend-tg/xxxxx,containerName=junkos-backend,containerPort=8080 \
  --health-check-grace-period-seconds 60 \
  --enable-execute-command \
  --tags key=Name,value=junkos-backend key=Environment,value=production
```

---

### 7. Configure Route53 DNS (5 min)

```bash
# Get ALB DNS name
aws elbv2 describe-load-balancers --names junkos-alb --query 'LoadBalancers[0].DNSName'

# Create hosted zone (if not exists)
aws route53 create-hosted-zone --name junkos.com --caller-reference $(date +%s)

# Create A record (alias to ALB)
cat > change-batch.json <<EOF
{
  "Changes": [
    {
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "api.junkos.com",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "Z35SXDOTRQ7X7K",
          "DNSName": "junkos-alb-123456.us-east-1.elb.amazonaws.com",
          "EvaluateTargetHealth": true
        }
      }
    }
  ]
}
EOF

aws route53 change-resource-record-sets \
  --hosted-zone-id Z1234567890ABC \
  --change-batch file://change-batch.json
```

---

## Infrastructure as Code (Terraform)

For repeatable, version-controlled infrastructure:

**`main.tf`:**
```hcl
terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  
  name = "junkos-vpc"
  cidr = "10.0.0.0/16"
  
  azs             = ["us-east-1a", "us-east-1b"]
  private_subnets = ["10.0.10.0/24", "10.0.11.0/24"]
  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24"]
  database_subnets = ["10.0.20.0/24", "10.0.21.0/24"]
  
  enable_nat_gateway = true
  single_nat_gateway = false
  
  enable_dns_hostnames = true
  enable_dns_support   = true
}

module "rds" {
  source = "terraform-aws-modules/rds/aws"
  
  identifier = "junkos-prod-db"
  
  engine            = "postgres"
  engine_version    = "15.4"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  storage_encrypted = true
  
  db_name  = "junkos"
  username = "junkosadmin"
  password = var.db_password
  
  multi_az = true
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = module.vpc.database_subnet_group_name
  
  backup_retention_period = 7
  skip_final_snapshot     = false
  final_snapshot_identifier = "junkos-final-snapshot"
}

module "ecs" {
  source = "terraform-aws-modules/ecs/aws"
  
  cluster_name = "junkos-prod"
  
  fargate_capacity_providers = {
    FARGATE = {
      default_capacity_provider_strategy = {
        weight = 100
      }
    }
  }
}

# ... (additional resources)
```

**Deploy with Terraform:**
```bash
terraform init
terraform plan
terraform apply
```

---

## CI/CD Pipeline

### GitHub Actions Example

**`.github/workflows/deploy.yml`:**
```yaml
name: Deploy to AWS ECS

on:
  push:
    branches: [main]

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: junkos/backend
  ECS_SERVICE: junkos-backend
  ECS_CLUSTER: junkos-prod
  CONTAINER_NAME: junkos-backend

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}
      
      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1
      
      - name: Build, tag, and push image to Amazon ECR
        id: build-image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          echo "image=$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG" >> $GITHUB_OUTPUT
      
      - name: Download task definition
        run: |
          aws ecs describe-task-definition \
            --task-definition junkos-backend \
            --query taskDefinition > task-definition.json
      
      - name: Update task definition with new image
        id: task-def
        uses: aws-actions/amazon-ecs-render-task-definition@v1
        with:
          task-definition: task-definition.json
          container-name: ${{ env.CONTAINER_NAME }}
          image: ${{ steps.build-image.outputs.image }}
      
      - name: Deploy to Amazon ECS
        uses: aws-actions/amazon-ecs-deploy-task-definition@v1
        with:
          task-definition: ${{ steps.task-def.outputs.task-definition }}
          service: ${{ env.ECS_SERVICE }}
          cluster: ${{ env.ECS_CLUSTER }}
          wait-for-service-stability: true
```

---

## Monitoring & Logging

### CloudWatch Dashboards

```bash
# Create custom dashboard
aws cloudwatch put-dashboard \
  --dashboard-name junkos-prod \
  --dashboard-body file://dashboard.json
```

**`dashboard.json`:**
```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/ECS", "CPUUtilization", {"stat": "Average"}],
          [".", "MemoryUtilization", {"stat": "Average"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "ECS Resource Utilization"
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/ApplicationELB", "TargetResponseTime", {"stat": "Average"}],
          [".", "RequestCount", {"stat": "Sum"}]
        ],
        "period": 60,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "ALB Metrics"
      }
    }
  ]
}
```

### CloudWatch Alarms

```bash
# High CPU alarm
aws cloudwatch put-metric-alarm \
  --alarm-name junkos-high-cpu \
  --alarm-description "Alert when CPU exceeds 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:junkos-alerts

# High error rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name junkos-high-5xx \
  --metric-name HTTPCode_Target_5XX_Count \
  --namespace AWS/ApplicationELB \
  --statistic Sum \
  --period 60 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:junkos-alerts
```

### X-Ray Tracing (Optional)

Add to task definition:
```json
{
  "name": "xray-daemon",
  "image": "public.ecr.aws/xray/aws-xray-daemon:latest",
  "cpu": 32,
  "memoryReservation": 256,
  "portMappings": [
    {
      "containerPort": 2000,
      "protocol": "udp"
    }
  ]
}
```

---

## Security Best Practices

### IAM Least Privilege

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:BatchCheckLayerAvailability"
      ],
      "Resource": "arn:aws:ecr:us-east-1:123456789012:repository/junkos/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:123456789012:log-group:/ecs/junkos-*"
    }
  ]
}
```

### Network Security

- [ ] Private subnets for ECS tasks (no public IPs)
- [ ] Security groups with minimum required access
- [ ] RDS not publicly accessible
- [ ] VPC Flow Logs enabled
- [ ] GuardDuty enabled for threat detection

### Secrets Management

- [ ] Use Secrets Manager for all credentials
- [ ] Enable automatic rotation for RDS passwords
- [ ] Never log secrets
- [ ] Use IAM roles instead of access keys where possible

### Compliance

- [ ] Enable CloudTrail for audit logging
- [ ] Configure AWS Config for compliance checks
- [ ] Enable S3 bucket encryption
- [ ] Implement backup policies
- [ ] Document data retention policies

---

## Cost Optimization

### Right-Sizing

**Start small, scale up:**
- Begin with `db.t3.micro` (RDS)
- Begin with 0.5 vCPU / 1GB RAM (Fargate)
- Monitor utilization, adjust as needed

### Savings Plans

- **Compute Savings Plans:** Save up to 66% on Fargate
- **RDS Reserved Instances:** Save up to 69% on database costs

### Cost Monitoring

```bash
# Enable Cost Explorer
# Set up billing alerts

aws budgets create-budget \
  --account-id 123456789012 \
  --budget file://monthly-budget.json \
  --notifications-with-subscribers file://notifications.json
```

**Monthly cost breakdown:**
| Service | On-Demand | With Savings |
|---------|-----------|--------------|
| Fargate (2 tasks, 24/7) | $30 | $18 |
| RDS t3.micro Multi-AZ | $30 | $20 |
| ALB | $16 | $16 |
| NAT Gateway | $32 | $32 |
| Other (CloudWatch, ECR) | $10 | $10 |
| **Total** | **$118/month** | **$96/month** |

---

## Troubleshooting

### ECS Tasks Not Starting

```bash
# Check task status
aws ecs describe-tasks \
  --cluster junkos-prod \
  --tasks task-arn

# Common issues:
# 1. Cannot pull image - check ECR permissions
# 2. Out of memory - increase task memory
# 3. Health check fails - verify /health endpoint
```

### Database Connection Issues

```bash
# Test connectivity from ECS task
aws ecs execute-command \
  --cluster junkos-prod \
  --task task-arn \
  --container junkos-backend \
  --interactive \
  --command "/bin/sh"

# Inside container:
nc -zv junkos-prod-db.xxxxx.rds.amazonaws.com 5432
```

### High Latency

- Check ALB target health
- Monitor RDS performance insights
- Review CloudWatch logs for slow queries
- Consider adding ElastiCache (Redis)

---

## Next Steps

- [ ] Set up staging environment
- [ ] Configure auto-scaling policies
- [ ] Implement backup/restore procedures
- [ ] Set up monitoring dashboard
- [ ] Configure log aggregation (Elasticsearch)
- [ ] Implement disaster recovery plan
- [ ] Performance testing with realistic load
- [ ] Security audit and penetration testing

---

## Resources

- [AWS ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [Terraform AWS Modules](https://registry.terraform.io/namespaces/terraform-aws-modules)

---

**Last Updated:** 2026-02-06  
**Version:** 1.0.0

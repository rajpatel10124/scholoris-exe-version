🛡️ Scholaris | Cloud-Native AI Plagiarism Engine
Scholaris is a distributed, high-availability platform designed to detect academic misconduct using advanced AI. This project demonstrates a professional-grade Cloud DevOps workflow, transitioning a heavy AI workload into a stateless, auto-scaling production environment.

🏗️ System Architecture
Built for the "Zero-Downtime" era, the architecture focuses on Decoupling and Statelessness.

Traffic Management: An Application Load Balancer (ALB) serves as the entry point, distributing requests across a fleet of servers.

Auto-Scaling: An AWS Auto Scaling Group (ASG) dynamically manages m7i-flex.large instances, scaling compute power based on real-time CPU demand.

Stateless Storage: Utilizes Amazon EFS (Elastic File System) to allow multiple EC2 instances to share a single /uploads directory in real-time.

Database Persistence: Externalized data to Amazon RDS (PostgreSQL), ensuring student records and plagiarism reports are safe even if servers are terminated.

Monitoring: Integrated Amazon CloudWatch for centralized logging and system health metrics.

🛠️ Tech Stack
Cloud: AWS (VPC, EC2, ALB, ASG, RDS, EFS, CloudWatch)

Infrastructure: Terraform (Infrastructure as Code)

Containers: Docker

AI/ML: FAISS (Vector Search), Sentence-Transformers, PyTorch

Backend: Flask (Python), Gunicorn, Eventlet

🔧 Infrastructure as Code (IaC) Workflow
The entire environment is fully automated. One command builds the network, storage, database, and scaling logic:

VPC Setup: Multi-AZ subnets for high availability.

Shared Disk: EFS mount targets provisioned across all subnets.

RDS Hookup: Managed Postgres with security groups restricted to the EC2 tier.

Auto-Deployment: Launch Template uses user_data to bootstrap Docker, mount the network drive, and deploy the app container.

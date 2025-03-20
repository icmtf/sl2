# CodeHorizon - Network Management System

CodeHorizon is a comprehensive network management system designed for tracking device backups and monitoring network infrastructure status. It provides a user-friendly interface for viewing backup compliance, operational status, configuration validation, and remote access monitoring.

## 🌟 Features

- **Backup Status Monitoring**: Track backup compliance with visual indicators
- **Operational Status**: Monitor device health (SSH, HTTPS, SNMP, etc.)
- **Validation Status**: Validate configurations against templates
- **Remote Access Monitoring**: Track VPN sessions and MAC tables
- **Interactive Dashboards**: Filter and visualize your network data
- **Multi-vendor Support**: Cisco, Fortinet, F5, and CheckPoint devices
- **Distributed Tracing**: OpenTelemetry integration with Jaeger

## 🏗️ Architecture

CodeHorizon follows a microservices architecture built on modern technologies:

### Frontend
- **Streamlit**: Interactive dashboards with filtering and visualization capabilities

### Backend
- **FastAPI**: RESTful API service for data access
- **Redis**: In-memory database for device and backup information
- **Python Workers**:
  - **EasyNet Worker**: Collects device data from EasyNet API
  - **S3 Worker**: Fetches backup information from S3 storage
- **Nginx**: Reverse proxy for routing requests
- **Jaeger**: Distributed tracing for observability
- **MkDocs**: Documentation system

### Data Flow
1. EasyNet Worker collects device data and stores it in Redis
2. S3 Worker fetches backup information from S3 and validates it against templates
3. Frontend dashboards visualize the data through FastAPI endpoints

## 📦 Data Model

- **Unified Data Structure**: All device data is stored in Redis using the key format `device:{hostname}`
- **Data Components**:
  - `easynet`: Basic device information
  - `backup_data`: Backup files and validation info
  - `validation`: Configuration validation data
  - `opstatus`: Operational status information

## 🚀 Getting Started

### Prerequisites
- Docker and Docker Compose
- AWS S3 compatible storage (or S3Mocker for development)
- EasyNet API credentials (or sample data for development)

### Installation

1. Clone the repository
   ```bash
   git clone [repository-url]
   cd CodeHorizon
   ```

2. Configure environment variables
   ```bash
   cp .env.example .env
   # Edit .env file with your configuration
   ```

3. Build and start the services
   ```bash
   docker-compose up -d
   ```

4. Access the application
   - Streamlit interface: http://localhost:8080
   - FastAPI documentation: http://localhost:8080/api/docs
   - Jaeger tracing: http://localhost:16686

### Development Setup

For local development:

1. Use the included S3Mocker for simulating S3 storage
   ```bash
   docker-compose up -d s3mocker
   ```

2. Set `ENVIRONMENT=local` to use sample data instead of live API

## 📋 Project Structure

```
CodeHorizon/
├── ci/                     # CI/CD configuration
├── docs/                   # Documentation (MkDocs)
├── fastapi/                # FastAPI backend service
├── mkdocs/                 # MkDocs configuration
├── nginx_reverse_proxy/    # Nginx configuration
├── python_workers/
│   ├── common/             # Shared code and utilities
│   ├── easynet_worker/     # EasyNet API integration
│   └── s3_worker/          # S3 backup retrieval and validation
├── redis/                  # Redis configuration
├── s3mocker/               # S3 mock service for development
├── streamlit/              # Streamlit dashboards
│   ├── views/              # Dashboard views and components
│   └── app.py              # Main Streamlit application
├── docker-compose.yaml     # Docker Compose configuration
└── .env.example            # Example environment variables
```

## 🔍 Monitoring & Observability

CodeHorizon includes built-in monitoring capabilities:

- **Distributed Tracing**: OpenTelemetry integration with Jaeger for tracing requests across services
- **Logging**: Centralized logging for all services
- **Dashboard Metrics**: Visual indicators of system health

## 📚 Documentation

Comprehensive documentation is available through the MkDocs site at http://localhost:8080/docs/ when the application is running.

## 🛡️ Security

The application implements:
- Authentication with login/logout functionality
- HTTPS support via Nginx
- Secure API access

## 🤝 Contributing

Contributions are welcome! Please refer to the development workflow documentation for our branching strategy and code review process.

## 📄 License

[License information]
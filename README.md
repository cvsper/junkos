# JunkOS - Junk Removal Management System

A complete Docker-based application for managing junk removal operations with customer portal and operator dashboard.

## 🚀 Quick Start

### Prerequisites

- Docker Desktop (Mac/Windows) or Docker Engine + Docker Compose (Linux)
- Git
- At least 4GB RAM available for Docker

### First-Time Setup

1. Clone and navigate to the project:
   ```bash
   cd ~/Documents/programs/webapps/junkos/
   ```

2. Create environment file:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. Build and start services:
   ```bash
   make build
   make up
   ```

4. Run initial database migrations:
   ```bash
   make migrate
   ```

5. Access the application:
   - **Customer Portal**: http://localhost
   - **Operator Dashboard**: http://localhost/dashboard
   - **API**: http://localhost/api

That's it! 🎉

## 📦 Services

The application consists of 6 Docker services:

| Service | Purpose | Port |
|---------|---------|------|
| `postgres` | Database | 5432 |
| `redis` | Cache/Sessions | 6379 |
| `backend` | Flask API | 5000 |
| `frontend` | Customer Portal (React) | 3000 |
| `dashboard` | Operator Dashboard (React) | 3001 |
| `nginx` | Reverse Proxy | 80 |

## 🛠️ Development Workflow

### Development Mode (Hot Reload)

Start services with hot reload enabled for frontend and backend changes:

```bash
make dev
```

This will:
- Mount local code into containers
- Enable auto-reload on file changes
- Expose services on separate ports:
  - Frontend: http://localhost:3000
  - Dashboard: http://localhost:3001
  - Backend: http://localhost:5000

### Makefile Commands

```bash
make help          # Show all available commands
make build         # Build all Docker images
make up            # Start services (production mode)
make dev           # Start services (development mode)
make down          # Stop all services
make restart       # Restart all services
make logs          # View logs from all services
make logs-backend  # View backend logs only
make clean         # Remove all containers, volumes, and images
make migrate       # Run database migrations
make test          # Run backend tests
make status        # Show container status and resource usage
make shell-backend # Open bash shell in backend container
make shell-db      # Open postgres shell
```

### Working with the Backend

```bash
# Run migrations
make migrate

# Run tests
make test

# Access backend shell
make shell-backend

# View backend logs
make logs-backend

# Restart just the backend
docker-compose restart backend
```

### Working with Frontend/Dashboard

```bash
# View frontend logs
make logs-frontend

# View dashboard logs
make logs-dashboard

# Rebuild frontend after dependency changes
docker-compose build frontend
docker-compose up -d frontend
```

### Database Access

```bash
# Access PostgreSQL shell
make shell-db

# Backup database
docker-compose exec postgres pg_dump -U junkos junkos > backup.sql

# Restore database
docker-compose exec -T postgres psql -U junkos junkos < backup.sql
```

## 🔧 Environment Variables

Key environment variables in `.env`:

### Flask Backend
```bash
FLASK_ENV=production              # production | development
SECRET_KEY=your-secret-key        # Change in production!
```

### Database
```bash
POSTGRES_DB=junkos
POSTGRES_USER=junkos
POSTGRES_PASSWORD=secure-password  # Change in production!
```

### Frontend/Dashboard
```bash
REACT_APP_API_URL=http://localhost/api
```

## 🚢 Production Deployment

### Security Checklist

Before deploying to production:

1. **Change default credentials:**
   ```bash
   # Generate secure secret key
   python -c 'import secrets; print(secrets.token_hex(32))'
   
   # Update .env
   SECRET_KEY=<generated-key>
   POSTGRES_PASSWORD=<strong-password>
   ```

2. **Update CORS settings** in backend to only allow your domain

3. **Configure SSL/TLS:**
   - Use a reverse proxy (Traefik, Caddy) or
   - Update nginx.conf with SSL certificates

4. **Set proper environment:**
   ```bash
   FLASK_ENV=production
   ```

### Deployment Steps

1. **On your production server:**
   ```bash
   git clone <your-repo>
   cd junkos
   cp .env.example .env
   # Edit .env with production values
   ```

2. **Build and start:**
   ```bash
   make build
   make up
   make migrate
   ```

3. **Verify services:**
   ```bash
   make status
   make logs
   ```

### Cloud Deployment

#### Docker Compose on VPS (DigitalOcean, Linode, etc.)

1. SSH into your server
2. Install Docker and Docker Compose
3. Clone repository
4. Run `make up`
5. Configure firewall to allow port 80/443

#### Kubernetes/EKS/GKE

Convert `docker-compose.yml` to Kubernetes manifests:
```bash
# Using kompose
kompose convert
kubectl apply -f .
```

## 🐛 Troubleshooting

### Services won't start

```bash
# Check Docker is running
docker ps

# Check logs for errors
make logs

# Rebuild from scratch
make clean
make build
make up
```

### Port conflicts

If ports 80, 3000, 3001, 5000, 5432, or 6379 are in use:

1. Stop conflicting services
2. Or modify ports in `docker-compose.yml`

### Database connection errors

```bash
# Check postgres is healthy
docker-compose ps postgres

# Check logs
make logs-postgres

# Restart postgres
docker-compose restart postgres
```

### Frontend can't reach backend

1. Check `REACT_APP_API_URL` in `.env`
2. Verify nginx is routing correctly: `make logs-nginx`
3. Test backend directly: `curl http://localhost:5000/health`

## 📁 Project Structure

```
junkos/
├── backend/
│   ├── Dockerfile            # Multi-stage Python build
│   ├── .dockerignore
│   ├── requirements.txt
│   └── app.py
├── frontend/
│   ├── Dockerfile            # Multi-stage React build
│   ├── Dockerfile.dev        # Development build
│   ├── .dockerignore
│   ├── nginx.conf            # Frontend nginx config
│   ├── package.json
│   └── src/
├── dashboard/
│   ├── Dockerfile            # Multi-stage React build
│   ├── Dockerfile.dev        # Development build
│   ├── .dockerignore
│   ├── nginx.conf            # Dashboard nginx config
│   ├── package.json
│   └── src/
├── docker-compose.yml        # Production configuration
├── docker-compose.dev.yml    # Development overrides
├── nginx.conf                # Main nginx reverse proxy
├── Makefile                  # Convenient commands
├── .env.example              # Environment template
└── README.md                 # This file
```

## 🤝 Contributing

1. Start development environment: `make dev`
2. Make changes (hot reload enabled)
3. Run tests: `make test`
4. Check logs: `make logs`

## 📝 License

[Your License Here]

## 🆘 Support

For issues or questions:
- Check logs: `make logs`
- View status: `make status`
- Open an issue on GitHub

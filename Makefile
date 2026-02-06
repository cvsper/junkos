.PHONY: help build up down restart logs clean migrate test dev prod

# Default target
help:
	@echo "JunkOS Docker Management"
	@echo "========================"
	@echo ""
	@echo "Available commands:"
	@echo "  make build       - Build all Docker images"
	@echo "  make up          - Start all services (production mode)"
	@echo "  make down        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make logs        - View logs from all services"
	@echo "  make clean       - Remove containers, volumes, and images"
	@echo "  make migrate     - Run database migrations"
	@echo "  make test        - Run tests in backend container"
	@echo "  make dev         - Start services in development mode"
	@echo "  make prod        - Start services in production mode"
	@echo ""
	@echo "Service-specific logs:"
	@echo "  make logs-backend"
	@echo "  make logs-frontend"
	@echo "  make logs-dashboard"
	@echo "  make logs-nginx"
	@echo "  make logs-postgres"
	@echo "  make logs-redis"

# Build all images
build:
	@echo "Building Docker images..."
	docker-compose build

# Start services in production mode
up prod:
	@echo "Starting JunkOS services (production)..."
	docker-compose up -d
	@echo "Services started!"
	@echo "Frontend: http://localhost"
	@echo "Dashboard: http://localhost/dashboard"
	@echo "API: http://localhost/api"

# Start services in development mode
dev:
	@echo "Starting JunkOS services (development)..."
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
	@echo "Services started!"
	@echo "Frontend: http://localhost:3000"
	@echo "Dashboard: http://localhost:3001"
	@echo "API: http://localhost:5000"

# Stop all services
down:
	@echo "Stopping JunkOS services..."
	docker-compose down

# Restart all services
restart:
	@echo "Restarting JunkOS services..."
	docker-compose restart

# View logs from all services
logs:
	docker-compose logs -f

# View logs from specific services
logs-backend:
	docker-compose logs -f backend

logs-frontend:
	docker-compose logs -f frontend

logs-dashboard:
	docker-compose logs -f dashboard

logs-nginx:
	docker-compose logs -f nginx

logs-postgres:
	docker-compose logs -f postgres

logs-redis:
	docker-compose logs -f redis

# Clean up everything
clean:
	@echo "Cleaning up Docker resources..."
	@read -p "This will remove all containers, volumes, and images. Continue? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v --rmi all; \
		echo "Cleanup complete!"; \
	else \
		echo "Cleanup cancelled."; \
	fi

# Run database migrations
migrate:
	@echo "Running database migrations..."
	docker-compose exec backend flask db upgrade

# Run tests
test:
	@echo "Running tests..."
	docker-compose exec backend pytest

# Enter backend shell
shell-backend:
	docker-compose exec backend /bin/bash

# Enter postgres shell
shell-db:
	docker-compose exec postgres psql -U junkos -d junkos

# Show container status
status:
	@echo "Container Status:"
	@docker-compose ps
	@echo ""
	@echo "Resource Usage:"
	@docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
		junkos-backend junkos-frontend junkos-dashboard junkos-nginx junkos-postgres junkos-redis 2>/dev/null || true

# Create .env file from example if it doesn't exist
init:
	@if [ ! -f .env ]; then \
		echo "Creating .env file from example..."; \
		cp .env.example .env 2>/dev/null || echo "Warning: .env.example not found"; \
		echo "Please edit .env with your configuration."; \
	else \
		echo ".env file already exists."; \
	fi

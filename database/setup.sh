#!/bin/bash
# ============================================================================
# Umuve Database Setup Script
# ============================================================================
# Quick setup script for initializing the Umuve database
# Usage: ./setup.sh [options]
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DB_NAME="umuve"
DB_USER="${DB_USER:-postgres}"
INCLUDE_SEED_DATA=false
RESET_DATABASE=false

# Functions
print_header() {
    echo -e "\n${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}→${NC} $1"
}

check_dependencies() {
    print_header "Checking Dependencies"
    
    # Check PostgreSQL
    if ! command -v psql &> /dev/null; then
        print_error "PostgreSQL client (psql) not found"
        echo "Install PostgreSQL: https://www.postgresql.org/download/"
        exit 1
    fi
    print_success "PostgreSQL client found"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 not found"
        echo "Install Python: https://www.python.org/downloads/"
        exit 1
    fi
    print_success "Python 3 found"
    
    # Check Python dependencies
    if ! python3 -c "import psycopg2" 2>/dev/null; then
        print_warning "psycopg2 not installed"
        print_info "Installing Python dependencies..."
        pip3 install -r requirements.txt || {
            print_error "Failed to install Python dependencies"
            exit 1
        }
    fi
    print_success "Python dependencies installed"
}

setup_environment() {
    print_header "Environment Configuration"
    
    if [ ! -f .env ]; then
        print_info "Creating .env file from template..."
        cp .env.example .env
        print_warning ".env file created - please update with your credentials"
        print_info "Edit .env file: nano .env"
    else
        print_success ".env file exists"
    fi
}

initialize_database() {
    print_header "Initializing Database"
    
    if [ "$RESET_DATABASE" = true ]; then
        print_warning "Resetting database (all data will be lost)"
        read -p "Are you sure? Type 'yes' to confirm: " confirm
        if [ "$confirm" != "yes" ]; then
            print_info "Database reset cancelled"
            exit 0
        fi
        
        print_info "Dropping existing database..."
        psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true
    fi
    
    # Create database
    print_info "Creating database and extensions..."
    psql -U "$DB_USER" -f 01_create_database.sql || {
        print_error "Database creation failed"
        exit 1
    }
    print_success "Database created"
    
    # Create schema
    print_info "Creating database schema..."
    psql -U "$DB_USER" -d "$DB_NAME" -f 02_schema.sql || {
        print_error "Schema creation failed"
        exit 1
    }
    print_success "Schema created"
    
    # Load seed data (optional)
    if [ "$INCLUDE_SEED_DATA" = true ]; then
        print_info "Loading sample data..."
        psql -U "$DB_USER" -d "$DB_NAME" -f 03_seed_data.sql || {
            print_error "Seed data loading failed"
            exit 1
        }
        print_success "Sample data loaded"
    else
        print_info "Skipping sample data (use --seed to include)"
    fi
    
    # Create views
    print_info "Creating database views..."
    psql -U "$DB_USER" -d "$DB_NAME" -f 04_views.sql || {
        print_error "View creation failed"
        exit 1
    }
    print_success "Views created"
}

verify_setup() {
    print_header "Verifying Setup"
    
    # Check table count
    table_count=$(psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" | xargs)
    print_success "$table_count tables created"
    
    # Check view count
    view_count=$(psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM information_schema.views WHERE table_schema = 'public';" | xargs)
    print_success "$view_count views created"
    
    if [ "$INCLUDE_SEED_DATA" = true ]; then
        tenant_count=$(psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM tenants;" | xargs)
        user_count=$(psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM users;" | xargs)
        job_count=$(psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM jobs;" | xargs)
        
        print_success "$tenant_count tenants, $user_count users, $job_count jobs"
    fi
}

show_next_steps() {
    print_header "Setup Complete!"
    
    echo -e "${GREEN}✓ Database '$DB_NAME' is ready${NC}\n"
    
    echo "Next steps:"
    echo ""
    echo "  1. Test the connection:"
    echo "     ${BLUE}psql -U $DB_USER -d $DB_NAME${NC}"
    echo ""
    echo "  2. View sample data (if loaded):"
    echo "     ${BLUE}psql -U $DB_USER -d $DB_NAME -c 'SELECT * FROM v_active_jobs;'${NC}"
    echo ""
    echo "  3. Create a new migration:"
    echo "     ${BLUE}python migrate.py --create 'your migration name'${NC}"
    echo ""
    echo "  4. Check migration status:"
    echo "     ${BLUE}python migrate.py --status${NC}"
    echo ""
    echo "  5. Create a backup:"
    echo "     ${BLUE}pg_dump -U $DB_USER -d $DB_NAME -F c -f backup.dump${NC}"
    echo ""
    print_info "See README.md for detailed documentation"
    echo ""
}

show_usage() {
    echo "Umuve Database Setup Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --seed          Include sample data for testing"
    echo "  --reset         Reset database (WARNING: deletes all data)"
    echo "  --user USER     PostgreSQL user (default: postgres)"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Basic setup without sample data"
    echo "  $0 --seed             # Setup with sample data"
    echo "  $0 --reset --seed     # Reset and setup with sample data"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --seed)
            INCLUDE_SEED_DATA=true
            shift
            ;;
        --reset)
            RESET_DATABASE=true
            shift
            ;;
        --user)
            DB_USER="$2"
            shift 2
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
main() {
    print_header "Umuve Database Setup"
    
    check_dependencies
    setup_environment
    initialize_database
    verify_setup
    show_next_steps
}

# Run main function
main

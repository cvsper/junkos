import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration"""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.environ.get('FLASK_ENV', 'development') == 'development'
    
    # API Security
    API_KEY = os.environ.get('API_KEY', 'junkos-api-key-12345')
    
    # Database
    DATABASE_PATH = os.environ.get('DATABASE_PATH', 'junkos.db')
    
    # CORS - Allow iOS app origin
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')
    
    # Pricing
    BASE_PRICE = float(os.environ.get('BASE_PRICE', '50.0'))
    
    # Stripe
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

    # Twilio SMS
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
    TWILIO_FROM_NUMBER = os.environ.get('TWILIO_FROM_NUMBER', '')

    # SendGrid Email
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
    SENDGRID_FROM_EMAIL = os.environ.get('SENDGRID_FROM_EMAIL', 'bookings@junkos.com')

    # Server
    PORT = int(os.environ.get('PORT', '8080'))

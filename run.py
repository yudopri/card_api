from flask import Flask, jsonify
from flasgger import Swagger
from flask_cors import CORS
from app.core.config import Config
from app.core.extensions import db, jwt, bcrypt, migrate
from app.api.auth import auth_bp
from app.api.admin import admin_bp
from app.api.verify import verify_bp
from app.api.history import history_bp
from app.models.models import User
import sys
import os

# Add the current directory to sys.path to allow 'app' imports when running as a script
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Enable CORS for all routes and origins
    CORS(app)

    # Swagger configuration
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": 'apispec',
                "route": '/apispec.json',
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/apidocs/"
    }
    
    template = {
        "swagger": "2.0",
        "info": {
            "title": "E-KYC API",
            "description": "API for Identity Verification Mobile App",
            "version": "1.0.0"
        },
        "securityDefinitions": {
            "BearerAuth": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "Add 'Bearer <token>' exactly like that to authorize."
            }
        },
        "security": [
            {
                "BearerAuth": []
            }
        ]
    }
    
    Swagger(app, config=swagger_config, template=template)

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints with api/v1 prefix
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/v1/admin')
    app.register_blueprint(verify_bp, url_prefix='/api/v1/verify')
    app.register_blueprint(history_bp, url_prefix='/api/v1/history')

    # Basic error handling
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"msg": "Resource not found"}), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"msg": "File too large (max 16MB)"}), 413

    # Database initialization command
    @app.cli.command("init-db")
    def init_db():
        """Initializes the database and creates an admin user."""
        db.create_all()
        # Check if admin already exists
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            
            petugas = User(username='petugas', role='petugas')
            petugas.set_password('petugas123')
            db.session.add(petugas)
            
            db.session.commit()
            print("DB Initialized: Created admin (user/pass: admin/admin123) and petugas (user/pass: petugas/petugas123)")
        else:
            print("Database already exists")

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')

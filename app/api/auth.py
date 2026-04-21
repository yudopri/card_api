from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, 
    create_refresh_token, 
    jwt_required, 
    get_jwt_identity
)
from app.models.models import User
from app.core.extensions import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register_user():
    """
    User Registration (Account Signup)
    ---
    tags:
      - Authentication
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            username:
              type: string
              example: budi
            password:
              type: string
              example: rahasia123
            role:
              type: string
              enum: [admin, petugas]
              default: petugas
    responses:
      201:
        description: User created successfully
      400:
        description: User already exists or missing data
    """
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"msg": "Missing username or password"}), 400

    if User.query.filter_by(username=data.get('username')).first():
        return jsonify({"msg": "Username already exists"}), 400

    new_user = User(
        username=data.get('username'),
        role=data.get('role', 'petugas')
    )
    new_user.set_password(data.get('password'))
    
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"msg": "User registered successfully"}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    User Login
    ---
    tags:
      - Authentication
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            username:
              type: string
              example: admin
            password:
              type: string
              example: admin123
    responses:
      200:
        description: Login successful
        schema:
          type: object
          properties:
            access_token:
              type: string
            refresh_token:
              type: string
            role:
              type: string
      401:
        description: Invalid credentials
    """
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"msg": "Missing username or password"}), 400

    user = User.query.filter_by(username=data.get('username')).first()

    if user and user.check_password(data.get('password')):
        identity = str(user.id)
        access_token = create_access_token(
            identity=identity, 
            additional_claims={"role": user.role}
        )
        refresh_token = create_refresh_token(identity=identity)
        return jsonify(
            access_token=access_token, 
            refresh_token=refresh_token,
            role=user.role
        ), 200

    return jsonify({"msg": "Bad username or password"}), 401

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh Access Token
    ---
    tags:
      - Authentication
    security:
      - BearerAuth: []
    responses:
      200:
        description: New access token created
        schema:
          type: object
          properties:
            access_token:
              type: string
      401:
        description: Invalid refresh token
    """
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    access_token = create_access_token(
        identity=identity, 
        additional_claims={"role": user.role}
    )
    return jsonify(access_token=access_token), 200

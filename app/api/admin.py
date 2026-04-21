from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt
from werkzeug.utils import secure_filename
from app.models.models import IDCard, User
from app.core.extensions import db
from app.services.image_service import calculate_phash
import os

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/register-id', methods=['POST'])
@jwt_required()
def register_id():
    """
    Register a new ID Card (Admin Only)
    ---
    tags:
      - Admin
    security:
      - BearerAuth: []
    parameters:
      - name: fullname
        in: formData
        type: string
        required: true
      - name: nip
        in: formData
        type: string
        required: true
      - name: job_title
        in: formData
        type: string
        required: true
      - name: qr_code
        in: formData
        type: string
        required: true
      - name: id_card_photo
        in: formData
        type: file
        required: true
    responses:
      201:
        description: Registered successfully
      400:
        description: Missing data/QR code exists
      403:
        description: Admin role required
    """
    # Manual role check instead of custom decorator for better Swagger visibility
    claims = get_jwt()
    if claims.get("role") != 'admin':
        return jsonify({"msg": "Admin role required"}), 403

    fullname = request.form.get('fullname')
    nip = request.form.get('nip')
    job_title = request.form.get('job_title')
    qr_code = request.form.get('qr_code')
    file = request.files.get('id_card_photo')
    qr_code = request.form.get('qr_code')
    file = request.files.get('id_card_photo')

    if not all([fullname, qr_code, file]):
        return jsonify({"msg": "Missing fullname, qr_code or id_card_photo"}), 400

    # Ensure qr_code is unique
    if IDCard.query.filter_by(qr_code=qr_code).first():
        return jsonify({"msg": "QR Code already registered"}), 400

    filename = secure_filename(file.filename)
    # create timestamp for file uniqueness in production, but following simple upload path here
    # save path: /uploads/master/
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'master')
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
        
    image_path = os.path.join(upload_dir, f"{qr_code}_{filename}")
    file.save(image_path)

    # Calculate pHash
    phash_value = calculate_phash(image_path)
    if phash_value is None:
        return jsonify({"msg": "Failed to process image"}), 500

    # Current user ID from JWT
    from flask_jwt_extended import get_jwt_identity
    current_user_id = int(get_jwt_identity())

    new_card = IDCard(
        user_id=current_user_id,
        fullname=fullname,
        nip=nip,
        job_title=job_title,
        qr_code=qr_code,
        id_card_image_path=image_path,
        phash_value=phash_value
    )
    db.session.add(new_card)
    db.session.commit()

    return jsonify({"msg": "ID Card registered successfully", "phash": phash_value}), 201

@admin_bp.route('/id-cards', methods=['GET'])
@jwt_required()
def list_id_cards():
    """
    Get all registered ID Cards (Admin Only)
    ---
    tags:
      - Admin
    security:
      - BearerAuth: []
    responses:
      200:
        description: List of ID cards returned
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
              fullname:
                type: string
              nip:
                type: string
              job_title:
                type: string
              qr_code:
                type: string
              image_path:
                type: string
              phash:
                type: string
              created_at:
                type: string
      403:
        description: Admin role required
    """
    claims = get_jwt()
    if claims.get("role") != 'admin':
        return jsonify({"msg": "Admin role required"}), 403

    cards = IDCard.query.all()
    output = []
    for card in cards:
        output.append({
            "id": card.id,
            "fullname": card.fullname,
            "nip": card.nip,
            "job_title": card.job_title,
            "qr_code": card.qr_code,
            "image_path": card.id_card_image_path,
            "phash": card.phash_value,
            "created_at": card.created_at.isoformat()
        })
    return jsonify(output), 200

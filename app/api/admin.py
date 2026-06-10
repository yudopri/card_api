from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt
from werkzeug.utils import secure_filename
from app.models.models import IDCard, User
from app.core.extensions import db
from app.services.detection_service import detect_and_crop_with_model
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
      - name: unique_crop_photo
        in: formData
        type: file
        required: false
        description: Optional fallback crop image. If omitted, the API will try to crop automatically using best.pt.
    responses:
      201:
        description: Registered successfully
        schema:
          type: object
          properties:
            msg:
              type: string
            phash:
              type: string
            crop_path:
              type: string
            boxed_path:
              type: string
            crop_source:
              type: string
      400:
        description: Missing data/QR code exists
        schema:
          type: object
          properties:
            msg:
              type: string
            status:
              type: string
            error_code:
              type: string
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
    crop_file = request.files.get('unique_crop_photo')

    current_app.logger.debug(f"Register-ID request: fullname={fullname}, nip={nip}, job_title={job_title}, qr_code={qr_code}, has_file={file is not None}, has_crop={crop_file is not None}")

    if not all([fullname, qr_code, file]):
        return jsonify({
            "msg": "Missing fullname, qr_code, or id_card_photo",
            "received": {
                "fullname": fullname,
                "nip": nip,
                "job_title": job_title,
                "qr_code": qr_code,
                "has_photo": file is not None,
                "has_crop": crop_file is not None
            }
        }), 400

    # Ensure qr_code is unique (stripping whitespace)
    qr_code = qr_code.strip()
    existing_card = IDCard.query.filter_by(qr_code=qr_code).first()
    if existing_card:
        return jsonify({
            "msg": f"QR Code is already registered to {existing_card.fullname} (NIP: {existing_card.nip})",
            "status": "error",
            "error_code": "ALREADY_REGISTERED",
            "details": {
                "fullname": existing_card.fullname,
                "nip": existing_card.nip,
                "qr_code": qr_code
            }
        }), 400

    # Ensure qr_code folder name is safe
    safe_qr_code = "".join([c for c in qr_code if c.isalnum() or c in ('-', '_')]).strip()
    if not safe_qr_code:
        safe_qr_code = "unknown_qr"

    import uuid
    import time
    
    # Try to get a clean filename from the uploaded file
    original_filename = secure_filename(file.filename)
    
    # If the filename still looks like a URL or is empty, force a clean name
    if not original_filename or "://" in file.filename or original_filename == "":
        extension = file.content_type.split('/')[-1] if file.content_type else 'jpg'
        # Remove any potential query params or illegal chars from extension
        extension = "".join([c for c in extension if c.isalnum()])
        final_filename = f"upload_{int(time.time())}_{uuid.uuid4().hex[:8]}.{extension}"
    else:
        # Even with secure_filename, let's make sure it doesn't have path separators
        final_filename = f"{uuid.uuid4().hex[:8]}_{original_filename}"

    # save path: /uploads/master/
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'master')
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
        
    image_path = os.path.join(upload_dir, f"{safe_qr_code}_{final_filename}")
    file.save(image_path)

    # Generate crop using object detection first, then fall back to uploaded crop.
    crop_filename = f"crop_{final_filename}"
    boxed_filename = f"boxed_{final_filename}"
    crop_path = os.path.join(upload_dir, f"{safe_qr_code}_{crop_filename}")
    boxed_path = os.path.join(upload_dir, f"{safe_qr_code}_{boxed_filename}")
    detection_result = detect_and_crop_with_model(image_path, crop_path, boxed_path)
    crop_source = "model" if detection_result else "manual_or_original"
    if detection_result:
        crop_path = detection_result["crop_path"]
        boxed_path = detection_result["boxed_path"]
    else:
        boxed_path = None
        if crop_file:
            crop_file.save(crop_path)
        else:
            return jsonify({
                "msg": "Failed to create crop from id_card_photo. Please upload unique_crop_photo as fallback.",
                "crop_source": "none"
            }), 400

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
        unique_crop_path=crop_path,
        phash_value=phash_value
    )
    db.session.add(new_card)
    db.session.commit()

    return jsonify({
        "msg": "ID Card registered successfully",
        "phash": phash_value,
        "crop_path": crop_path,
        "boxed_path": boxed_path,
        "crop_source": crop_source
    }), 201

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

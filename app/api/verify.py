from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from app.models.models import IDCard, Logbook
from app.core.extensions import db
from app.services.image_service import calculate_phash, analyze_liveness
import os
import imagehash

verify_bp = Blueprint('verify', __name__)

@verify_bp.route('/scan', methods=['POST'])
@jwt_required()
def scan_verify():
    """
    Verify Scanned ID
    ---
    tags:
      - Verification
    security:
      - BearerAuth: []
    parameters:
      - name: qr_code
        in: formData
        type: string
        required: true
      - name: scanned_image
        in: formData
        type: file
        required: true
    responses:
      200:
        description: Verification result
        schema:
          type: object
          properties:
            status:
              type: string
              enum: [verified, fake, duplicate, failed]
            confidence_score:
              type: number
            fullname:
              type: string
      404:
        description: ID Not Found
    """
    qr_code = request.form.get('qr_code')
    scanned_image = request.files.get('scanned_image')

    if not all([qr_code, scanned_image]):
        return jsonify({"msg": "Missing qr_code or scanned_image"}), 400

    # a. Find IDCard by qr_code
    id_card = IDCard.query.filter_by(qr_code=qr_code).first()
    if not id_card:
        return jsonify({"msg": "ID Card not found"}), 404

    # b. Save scanned_image to /uploads/scans/
    import uuid
    import time
    
    # Sanitasi qr_code untuk jadi bagian nama file
    safe_qr_prefix = "".join([c for c in qr_code if c.isalnum() or c in ('-', '_')]).strip()
    
    # Cek apakah filename mengandung URL atau ilegal
    original_filename = secure_filename(scanned_image.filename)
    if not original_filename or "://" in scanned_image.filename or original_filename == "":
        extension = scanned_image.content_type.split('/')[-1] if scanned_image.content_type else 'jpg'
        extension = "".join([c for c in extension if c.isalnum()])
        final_filename = f"scan_{int(time.time())}_{uuid.uuid4().hex[:8]}.{extension}"
    else:
        final_filename = f"{uuid.uuid4().hex[:8]}_{original_filename}"

    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'scans')
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)

    save_path = os.path.join(upload_dir, f"{safe_qr_prefix}_{final_filename}")
    scanned_image.save(save_path)

    # c. Calculate pHash
    new_phash = calculate_phash(save_path)
    if not new_phash:
        return jsonify({"msg": "Failed to calculate image hash"}), 500

    # d. Compare it with the DB: If exact match with an existing log, flag as 'duplicate'
    # Actually, instructions indicate comparing pHash with existing DB entry's pHash
    # Let's perform pHash comparison logic:
    # If using absolute string comparison for "exact match"
    
    status = 'verified'
    
    # Check if this exact scan was ever uploaded before (checking logs for same phash)
    existing_duplicate = Logbook.query.filter_by(id_card_id=id_card.id).join(Logbook.id_card).filter(Logbook.status=='verified').all()
    # Let's refine: "Compare it with the DB". If the pHash matches ANY registered scan for that card, it might be a double entry.
    
    # But for simplicity as requested: "If exact match with an existing log, flag as 'duplicate'."
    is_duplicate = False
    for log in id_card.logs:
        # Re-calc or store hash in Logbook would be better, but let's re-hash previously saved files OR compare with original?
        # Let's assume user meant comparing with target IDCard's master hash or existing log hashes.
        # I'll compare against ALL logs for that card for identical scans.
        log_image_path = log.scan_image_path
        if log_image_path and os.path.exists(log_image_path):
             log_hash = calculate_phash(log_image_path)
             if log_hash == new_phash:
                 is_duplicate = True
                 status = 'duplicate'
                 break
    
    # e. Pass image to an AI Service stub
    confidence_score, ai_status = analyze_liveness(save_path)
    if ai_status != 'Real':
        status = 'fake'
    
    # f. Save to Logbook
    petugas_id = int(get_jwt_identity())
    new_log = Logbook(
        id_card_id=id_card.id,
        petugas_id=petugas_id,
        scan_image_path=save_path,
        status=status,
        ai_confidence_score=confidence_score
    )
    db.session.add(new_log)
    db.session.commit()

    # g. Return verification status and score
    return jsonify({
        "status": status,
        "ai_status": ai_status,
        "confidence_score": confidence_score,
        "fullname": id_card.fullname,
        "qr_code": id_card.qr_code
    }), 200

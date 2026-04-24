from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from app.models.models import IDCard, Logbook
from app.core.extensions import db
from app.services.image_service import calculate_phash, analyze_liveness
from app.services.matcher_service import compute_feature_match_score
import os

verify_bp = Blueprint("verify", __name__)

@verify_bp.route("/scan", methods=["POST"])
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
      404:
        description: ID Not Found
    """
    qr_code = request.form.get("qr_code")
    scanned_image = request.files.get("scanned_image")

    if not all([qr_code, scanned_image]):
        return jsonify({"msg": "Missing qr_code or scanned_image"}), 400

    id_card = IDCard.query.filter_by(qr_code=qr_code).first()
    if not id_card:
        return jsonify({"msg": "ID Card not found"}), 404

    import uuid
    import time
    
    safe_qr_prefix = "".join([c for c in qr_code if c.isalnum() or c in ("-", "_")]).strip()
    original_filename = secure_filename(scanned_image.filename)
    if not original_filename or "://" in scanned_image.filename or original_filename == "":
        extension = scanned_image.content_type.split("/")[-1] if scanned_image.content_type else "jpg"
        extension = "".join([c for c in extension if c.isalnum()])
        final_filename = f"scan_{int(time.time())}_{uuid.uuid4().hex[:8]}.{extension}"
    else:
        final_filename = f"{uuid.uuid4().hex[:8]}_{original_filename}"

    upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "scans")
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)

    save_path = os.path.join(upload_dir, f"{safe_qr_prefix}_{final_filename}")
    scanned_image.save(save_path)

    # PEMBARUAN: Gunakan unique_crop_path sebagai pembanding (Anchor)
    # karena scanned_image yang dikirim adalah hasil cropping juga.
    master_crop_path = id_card.unique_crop_path
    
    # Fallback ke id_card_image_path jika crop tidak ada (untuk kompatibilitas)
    if not master_crop_path or not os.path.exists(master_crop_path):
        master_crop_path = id_card.id_card_image_path

    if not master_crop_path or not os.path.exists(master_crop_path):
        return jsonify({"msg": "Reference image missing on server"}), 500
        
    match_score = compute_feature_match_score(master_crop_path, save_path)
    liveness_score, liveness_status = analyze_liveness(save_path)

    status = "verified"
    if match_score < 0.15:
        status = "fake"
    elif liveness_status.lower() != "real":
        status = "fake"

    current_user_id = int(get_jwt_identity())
    new_log = Logbook(
        id_card_id=id_card.id,
        petugas_id=current_user_id,
        scan_image_path=save_path,
        status=status,
        ai_confidence_score=match_score
    )
    db.session.add(new_log)
    db.session.commit()

    return jsonify({
        "status": status,
        "match_score": round(match_score, 4),
        "liveness_score": liveness_score,
        "fullname": id_card.fullname,
        "nip": id_card.nip
    }), 200

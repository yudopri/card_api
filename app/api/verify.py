from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from app.models.models import IDCard, Logbook
from app.core.extensions import db
from app.services.detection_service import detect_and_crop_with_model
from app.services.image_service import calculate_phash, analyze_liveness
from app.services.matcher_service import THRESHOLD_LULUS, compute_feature_match_score
import os

verify_bp = Blueprint("verify", __name__)

def get_image_url(absolute_path):
    if not absolute_path:
        return None
    # Convert absolute path to relative URL component
    # Handle both Windows and Unix paths by replacing backslashes and finding index of 'uploads'
    norm_path = os.path.normpath(absolute_path)
    upload_folder = os.path.normpath(current_app.config['UPLOAD_FOLDER'])
    
    if upload_folder in norm_path:
        relative_path = norm_path.split(upload_folder)[-1].replace('\\', '/').lstrip('/')
        return f"{request.host_url.rstrip('/')}/uploads/{relative_path}"
    return None

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
        schema:
          type: object
          properties:
            status:
              type: string
            fullname:
              type: string
            nip:
              type: string
            match_score:
              type: number
            liveness_score:
              type: number
            original_image_url:
              type: string
            scanned_image_url:
              type: string
            scanned_boxed_image_url:
              type: string
            scan_crop_source:
              type: string
      404:
        description: ID Not Found
      400:
        description: Missing qr_code or scanned_image
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

    scan_base, scan_ext = os.path.splitext(save_path)
    scan_crop_path = f"{scan_base}_crop{scan_ext or '.jpg'}"
    scan_boxed_path = f"{scan_base}_boxed{scan_ext or '.jpg'}"
    detection_result = detect_and_crop_with_model(save_path, scan_crop_path, scan_boxed_path)
    if detection_result:
        scan_compare_path = detection_result["crop_path"]
        scan_boxed_path = detection_result["boxed_path"]
        scan_crop_source = "model"
    else:
        return jsonify({
            "msg": "Failed to create crop from scanned_image",
            "scan_crop_source": "none"
        }), 400

    master_crop_path = id_card.unique_crop_path
    
    if not master_crop_path or not os.path.exists(master_crop_path):
        master_base, master_ext = os.path.splitext(id_card.id_card_image_path)
        master_crop_path = f"{master_base}_crop{master_ext or '.jpg'}"
        master_boxed_path = f"{master_base}_boxed{master_ext or '.jpg'}"
        master_detection_result = detect_and_crop_with_model(
            id_card.id_card_image_path,
            master_crop_path,
            master_boxed_path,
        )
        if master_detection_result:
            master_crop_path = master_detection_result["crop_path"]

    if not master_crop_path or not os.path.exists(master_crop_path):
        return jsonify({"msg": "Reference crop image missing on server"}), 500
        
    match_score = compute_feature_match_score(master_crop_path, scan_compare_path)
    liveness_score, liveness_status = analyze_liveness(save_path)

    if match_score >= THRESHOLD_LULUS:
        status = "verified"
    else:
        status = "fake"

    # Override with liveness status
    if liveness_status.lower() != "real":
        status = "fake"

    current_user_id = int(get_jwt_identity())
    new_log = Logbook(
        id_card_id=id_card.id,
        petugas_id=current_user_id,
        scan_image_path=scan_compare_path,
        status=status,
        match_score=float(match_score),
        liveness_score=float(liveness_score),
        ai_confidence_score=match_score
    )
    db.session.add(new_log)
    db.session.commit()

    return jsonify({
        "status": status,
        "fullname": id_card.fullname,
        "nip": id_card.nip,
        "match_score": float(match_score),
        "liveness_score": float(liveness_score),
        "original_image_url": get_image_url(master_crop_path),
        "scanned_image_url": get_image_url(scan_compare_path),
        "scanned_boxed_image_url": get_image_url(scan_boxed_path),
        "scan_crop_source": scan_crop_source
    }), 200

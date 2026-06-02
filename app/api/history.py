from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from app.models.models import Logbook, IDCard, User
import os

history_bp = Blueprint('history', __name__)

def get_image_url(absolute_path):
    if not absolute_path:
        return None
    norm_path = os.path.normpath(absolute_path)
    upload_folder = os.path.normpath(current_app.config['UPLOAD_FOLDER'])
    
    if upload_folder in norm_path:
        relative_path = norm_path.split(upload_folder)[-1].replace('\\', '/').lstrip('/')
        return f"{request.host_url.rstrip('/')}/uploads/{relative_path}"
    return None

@history_bp.route('/logs', methods=['GET'])
@jwt_required()
def get_history_logs():
    """
    Get Verification History Logs
    ---
    tags:
      - History
    security:
      - BearerAuth: []
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
      - name: per_page
        in: query
        type: integer
        default: 10
    responses:
      200:
        description: Paginated logs returned
        schema:
          type: object
          properties:
            total:
              type: integer
            pages:
              type: integer
            current_page:
              type: integer
            logs:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  id_card_fullname:
                    type: string
                  id_card_qr:
                    type: string
                  petugas_username:
                    type: string
                  scan_image_path:
                    type: string
                  status:
                    type: string
                  ai_confidence_score:
                    type: number
                  created_at:
                    type: string
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    # Paginated data using join
    logs_pagination = Logbook.query.join(IDCard).join(User, Logbook.petugas_id == User.id)\
        .order_by(Logbook.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    results = []
    for log in logs_pagination.items:
        results.append({
            "id": log.id,
            "id_card_fullname": log.id_card.fullname,
            "id_card_qr": log.id_card.qr_code,
            "status": log.status,
            "created_at": log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            "match_score": float(log.match_score) if log.match_score is not None else 0.0,
            "liveness_score": float(log.liveness_score) if log.liveness_score is not None else 0.0,
            "original_image_url": get_image_url(log.id_card.unique_crop_path or log.id_card.id_card_image_path),
            "scanned_image_url": get_image_url(log.scan_image_path)
        })

    return jsonify({
        "logs": results,
        "pages": logs_pagination.pages,
        "total": logs_pagination.total
    }), 200

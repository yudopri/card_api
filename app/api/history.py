from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.models.models import Logbook, IDCard, User

history_bp = Blueprint('history', __name__)

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
            "petugas_username": log.petugas.username,
            "scan_image_path": log.scan_image_path,
            "status": log.status,
            "ai_confidence_score": log.ai_confidence_score,
            "created_at": log.created_at.isoformat()
        })

    return jsonify({
        "total": logs_pagination.total,
        "pages": logs_pagination.pages,
        "current_page": logs_pagination.page,
        "logs": results
    }), 200

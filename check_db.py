from run import app
from app.models.models import IDCard

with app.app_context():
    cards = IDCard.query.all()
    print('--- Registered QR Codes ---')
    for c in cards:
        print(f"ID: {c.id} | QR: {c.qr_code} | Name: {c.fullname}")
    print('---------------------------')

from datetime import datetime
from app.core.extensions import db, bcrypt

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='petugas') # roles: 'admin', 'petugas'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

class IDCard(db.Model):
    __tablename__ = 'id_cards'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    fullname = db.Column(db.String(128), nullable=False)
    nip = db.Column(db.String(64), nullable=True)  
    job_title = db.Column(db.String(128), nullable=True)
    qr_code = db.Column(db.String(128), unique=True, nullable=False)
    id_card_image_path = db.Column(db.String(256))
    phash_value = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Logbook(db.Model):
    __tablename__ = 'logbooks'
    id = db.Column(db.Integer, primary_key=True)
    id_card_id = db.Column(db.Integer, db.ForeignKey('id_cards.id'))
    petugas_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    scan_image_path = db.Column(db.String(256))
    status = db.Column(db.String(20)) # statuses: 'verified', 'fake', 'duplicate', 'failed'
    ai_confidence_score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    id_card = db.relationship('IDCard', backref=db.backref('logs', lazy=True))
    petugas = db.relationship('User', backref=db.backref('logs_handled', lazy=True))

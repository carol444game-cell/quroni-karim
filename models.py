from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Ayah(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ayah_id = db.Column(db.String(50), unique=True, nullable=False)
    text = db.Column(db.Text, nullable=False)
    audio_file_id = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, unique=True, nullable=False)
    username = db.Column(db.String(50))
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

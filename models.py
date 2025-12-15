from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Ayah(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    ayah_uid = db.Column(db.String(150), unique=True, nullable=False)
    sura = db.Column(db.String(100), nullable=False)
    ayah_number = db.Column(db.String(20), nullable=False)

    text = db.Column(db.Text)
    audio_file_id = db.Column(db.String(255))

    channel_id = db.Column(db.String(50))
    message_id = db.Column(db.String(50))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "uid": self.ayah_uid,
            "sura": self.sura,
            "ayah": self.ayah_number,
            "text": self.text,
            "audio": self.audio_file_id
        }

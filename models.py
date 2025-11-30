from flask_sqlalchemy import SQLAlchemy
import uuid

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), nullable=True)

    def __repr__(self):
        return f'<User {self.uuid}>'

class Recipient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    image_filename = db.Column(db.String(255), nullable=True) # New column for avatar
    taken_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    taken_by = db.relationship('User', backref=db.backref('recipients', lazy=True))

    def __repr__(self):
        return f'<Recipient {self.name}>'

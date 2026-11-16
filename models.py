import secrets

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

NAME_MAX_LENGTH = 100
WISH_MAX_LENGTH = 500  # room for long shop links
WISH_COUNT = 3


def new_token():
    return secrets.token_urlsafe(16)


class Participant(db.Model):
    __table_args__ = (
        db.CheckConstraint('gives_to_id IS NULL OR gives_to_id <> id', name='no_self_pick'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(NAME_MAX_LENGTH), nullable=False)
    image_filename = db.Column(db.String(255), nullable=True)

    # Secret part of the personal link: /join/<token>
    token = db.Column(db.String(64), unique=True, nullable=False, default=new_token)
    # Set the first time the personal link is opened.
    joined_at = db.Column(db.DateTime, nullable=True)

    wish1 = db.Column(db.String(WISH_MAX_LENGTH), nullable=True)
    wish2 = db.Column(db.String(WISH_MAX_LENGTH), nullable=True)
    wish3 = db.Column(db.String(WISH_MAX_LENGTH), nullable=True)

    # The person this participant gives a gift to. Unique, so nobody can be
    # picked twice; a single column, so nobody can pick two people.
    gives_to_id = db.Column(db.Integer, db.ForeignKey('participant.id'), unique=True, nullable=True)
    gives_to = db.relationship('Participant', remote_side=[id], foreign_keys=[gives_to_id])

    @property
    def wish_slots(self):
        """All wish fields in order, with empty ones as ''."""
        return [self.wish1 or '', self.wish2 or '', self.wish3 or '']

    @property
    def wishes(self):
        """Only the filled-in wishes."""
        return [wish for wish in self.wish_slots if wish]

    def set_wishes(self, wishes):
        self.wish1, self.wish2, self.wish3 = (wish or None for wish in wishes)

    def __repr__(self):
        return f'<Participant {self.name}>'

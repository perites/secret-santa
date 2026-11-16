import os
import secrets
import uuid
from datetime import datetime
from functools import wraps

from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from config import Config
from models import NAME_MAX_LENGTH, WISH_COUNT, WISH_MAX_LENGTH, Participant, db, new_token

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
with app.app_context():
    db.create_all()

if not app.config['ADMIN_PIN']:
    app.logger.warning('ADMIN_PIN is not set, so the admin page is disabled. Add it to .env.')


# ---------------------------------------------------------------- deadline

def deadline_passed():
    return datetime.now() > app.config['DEADLINE']


def deadline_label():
    deadline = app.config['DEADLINE']
    return f'{deadline:%B} {deadline.day}, {deadline.year} at {deadline:%H:%M}'


def deadline_error(action):
    message = f'The deadline ({deadline_label()}) has passed, so you can no longer {action}.'
    return jsonify({'error': message}), 403


# ------------------------------------------------------------ participants

def current_participant():
    """The participant this browser is signed in as, or None. Cached per request."""
    if 'participant' not in g:
        g.participant = None
        participant_id = session.get('participant_id')
        if participant_id is not None:
            participant = db.session.get(Participant, participant_id)
            token = session.get('participant_token', '')
            if participant and secrets.compare_digest(participant.token, token):
                g.participant = participant
            else:
                # The participant was deleted or their link was regenerated.
                log_out_participant()
    return g.participant


def log_in_participant(participant):
    session['participant_id'] = participant.id
    session['participant_token'] = participant.token
    session.permanent = True
    g.participant = participant


def log_out_participant():
    session.pop('participant_id', None)
    session.pop('participant_token', None)
    g.participant = None


def participant_required(view):
    """Pass the signed-in participant to the view as its first argument."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        me = current_participant()
        if me is None:
            return jsonify({'error': 'Open your personal link from the organizer to continue.'}), 401
        return view(me, *args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get('admin_auth'):
            return jsonify({'error': 'Unauthorized'}), 401
        return view(*args, **kwargs)
    return wrapper


def image_url(participant):
    if not participant.image_filename:
        return None
    return url_for('static', filename=f'uploads/{participant.image_filename}')


def join_link(participant):
    public_url = app.config['PUBLIC_URL']
    if public_url:
        return public_url + url_for('join', token=participant.token)
    return url_for('join', token=participant.token, _external=True)


def public_info(participant, with_wishes=False):
    """What a participant may see about another participant.

    Wishes are only shared with the person who picked them, so nobody
    chooses based on who has the nicest wishlist.
    """
    info = {
        'id': participant.id,
        'name': participant.name,
        'image_url': image_url(participant),
    }
    if with_wishes:
        info['wishes'] = participant.wishes
    return info


def admin_info(participant):
    # Deliberately leaves out picks: the admin must not see who picked whom.
    return {
        'id': participant.id,
        'name': participant.name,
        'image_url': image_url(participant),
        'wishes': participant.wish_slots,
        'link': join_link(participant),
        'joined': participant.joined_at is not None,
    }


def taken_participant_ids():
    query = db.select(Participant.gives_to_id).where(Participant.gives_to_id.is_not(None))
    return set(db.session.execute(query).scalars())


def participants_by_name():
    query = db.select(Participant).order_by(func.lower(Participant.name))
    return db.session.execute(query).scalars().all()


# -------------------------------------------------------------- validation

def clean_name(raw):
    name = (raw or '').strip()
    if not name:
        return None, 'Name is required.'
    if len(name) > NAME_MAX_LENGTH:
        return None, f'Name must be at most {NAME_MAX_LENGTH} characters.'
    return name, None


def clean_wishes(raw):
    """Validate a list of up to WISH_COUNT wishes and pad it to WISH_COUNT items."""
    if not isinstance(raw, list) or not all(isinstance(wish, str) for wish in raw):
        return None, 'Wishes must be a list of text items.'
    if len(raw) > WISH_COUNT:
        return None, f'You can add at most {WISH_COUNT} wishes.'
    # Collapse whitespace so pasted line breaks don't end up in a wish.
    wishes = [' '.join(wish.split()) for wish in raw] + [''] * (WISH_COUNT - len(raw))
    if any(len(wish) > WISH_MAX_LENGTH for wish in wishes):
        return None, f'Each wish must be at most {WISH_MAX_LENGTH} characters.'
    return wishes, None


def save_image(file):
    """Save an uploaded image. Returns (filename, error); filename is None if nothing was sent."""
    if not file or not file.filename:
        return None, None
    extension = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if extension not in ALLOWED_EXTENSIONS:
        return None, 'Image must be a PNG, JPG, GIF or WebP file.'
    filename = f'{uuid.uuid4().hex}.{extension}'
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return filename, None


def delete_image(filename):
    if not filename:
        return
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    except FileNotFoundError:
        pass


# ------------------------------------------------------------------- pages

@app.context_processor
def template_globals():
    return {
        'me': current_participant(),
        'deadline_label': deadline_label(),
        'deadline_passed': deadline_passed(),
        'gift_budget': app.config['GIFT_BUDGET'],
        'name_max_length': NAME_MAX_LENGTH,
        'wish_max_length': WISH_MAX_LENGTH,
        'wish_count': WISH_COUNT,
    }


@app.errorhandler(HTTPException)
def handle_http_error(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': error.description}), error.code
    return error


@app.route('/')
def index():
    if current_participant() is None:
        return render_template('welcome.html')
    return render_template('index.html')


@app.route('/join/<token>')
def join(token):
    participant = db.session.execute(
        db.select(Participant).filter_by(token=token)
    ).scalar_one_or_none()
    if participant is None:
        return render_template('welcome.html', invalid_link=True), 404

    log_in_participant(participant)
    if participant.joined_at is None:
        participant.joined_at = datetime.now()
        db.session.commit()
    # Redirect so the secret link doesn't stay in the address bar.
    return redirect(url_for('index'))


@app.route('/logout', methods=['POST'])
def logout():
    log_out_participant()
    return redirect(url_for('index'))


@app.route('/admin')
def admin():
    return render_template('admin.html')


# ------------------------------------------------------- participant API

@app.route('/api/me')
@participant_required
def api_me(me):
    return jsonify({
        'id': me.id,
        'name': me.name,
        'image_url': image_url(me),
        'wishes': me.wish_slots,
        'gives_to': public_info(me.gives_to, with_wishes=True) if me.gives_to else None,
        'deadline_passed': deadline_passed(),
    })


@app.route('/api/me/wishes', methods=['POST'])
@participant_required
def api_save_wishes(me):
    if deadline_passed():
        return deadline_error('edit your wishlist')

    data = request.get_json(silent=True) or {}
    wishes, error = clean_wishes(data.get('wishes', []))
    if error:
        return jsonify({'error': error}), 400

    me.set_wishes(wishes)
    db.session.commit()
    return jsonify({'success': True, 'wishes': me.wish_slots})


@app.route('/api/participants')
@participant_required
def api_participants(me):
    taken_ids = taken_participant_ids()
    return jsonify([
        {
            **public_info(participant, with_wishes=participant.id == me.gives_to_id),
            'is_taken': participant.id in taken_ids,
            'taken_by_me': participant.id == me.gives_to_id,
        }
        for participant in participants_by_name()
        if participant.id != me.id
    ])


@app.route('/api/take/<int:target_id>', methods=['POST'])
@participant_required
def api_take(me, target_id):
    if deadline_passed():
        return deadline_error('pick or change your choice')

    target = db.get_or_404(Participant, target_id)
    if target.id == me.id:
        return jsonify({'error': "You can't pick yourself."}), 400
    if me.gives_to_id == target.id:
        return jsonify({'message': 'You already picked this person.'})
    if me.gives_to_id is not None:
        return jsonify({'error': 'You have already picked someone. Change your choice first.'}), 400
    if target.id in taken_participant_ids():
        return jsonify({'error': 'This person is already taken.'}), 400

    me.gives_to_id = target.id
    try:
        db.session.commit()
    except IntegrityError:
        # Someone else picked the same person a moment ago.
        db.session.rollback()
        return jsonify({'error': 'This person is already taken.'}), 400
    return jsonify({'success': True})


@app.route('/api/untake', methods=['POST'])
@participant_required
def api_untake(me):
    if deadline_passed():
        return deadline_error('pick or change your choice')
    if me.gives_to_id is None:
        return jsonify({'error': "You haven't picked anyone yet."}), 400

    me.gives_to_id = None
    db.session.commit()
    return jsonify({'success': True})


# ------------------------------------------------------------- admin API

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    expected_pin = app.config['ADMIN_PIN']
    if not expected_pin:
        return jsonify({'error': 'Admin PIN is not configured. Set ADMIN_PIN in .env and restart.'}), 503

    pin = (request.get_json(silent=True) or {}).get('pin')
    if isinstance(pin, str) and secrets.compare_digest(pin.encode(), expected_pin.encode()):
        session['admin_auth'] = True
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid PIN'}), 401


@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('admin_auth', None)
    return jsonify({'success': True})


@app.route('/api/admin/check_auth')
def admin_check_auth():
    return jsonify({'authenticated': bool(session.get('admin_auth'))})


@app.route('/api/admin/participants')
@admin_required
def admin_list_participants():
    participants = participants_by_name()
    return jsonify({
        'participants': [admin_info(participant) for participant in participants],
        # Only a total: per-person "has picked" flags, combined with the
        # "taken" badges on the main page, could reveal who picked whom.
        'picked_count': sum(participant.gives_to_id is not None for participant in participants),
    })


@app.route('/api/admin/participants', methods=['POST'])
@admin_required
def admin_add_participant():
    name, error = clean_name(request.form.get('name'))
    if error:
        return jsonify({'error': error}), 400
    wishes, error = clean_wishes(request.form.getlist('wishes'))
    if error:
        return jsonify({'error': error}), 400
    image_filename, error = save_image(request.files.get('image'))
    if error:
        return jsonify({'error': error}), 400

    participant = Participant(name=name, image_filename=image_filename)
    participant.set_wishes(wishes)
    db.session.add(participant)
    db.session.commit()
    return jsonify(admin_info(participant)), 201


@app.route('/api/admin/participants/<int:participant_id>', methods=['POST'])
@admin_required
def admin_edit_participant(participant_id):
    participant = db.get_or_404(Participant, participant_id)

    name, error = clean_name(request.form.get('name'))
    if error:
        return jsonify({'error': error}), 400
    wishes = None
    if 'wishes' in request.form:
        wishes, error = clean_wishes(request.form.getlist('wishes'))
        if error:
            return jsonify({'error': error}), 400
    image_filename, error = save_image(request.files.get('image'))
    if error:
        return jsonify({'error': error}), 400

    participant.name = name
    if wishes is not None:
        participant.set_wishes(wishes)
    if image_filename:
        delete_image(participant.image_filename)
        participant.image_filename = image_filename
    db.session.commit()
    return jsonify(admin_info(participant))


@app.route('/api/admin/participants/<int:participant_id>', methods=['DELETE'])
@admin_required
def admin_delete_participant(participant_id):
    participant = db.get_or_404(Participant, participant_id)
    # Whoever picked this person has to pick someone else.
    db.session.execute(
        db.update(Participant)
        .where(Participant.gives_to_id == participant.id)
        .values(gives_to_id=None)
    )
    image_filename = participant.image_filename
    db.session.delete(participant)
    db.session.commit()
    delete_image(image_filename)
    return jsonify({'success': True})


@app.route('/api/admin/participants/<int:participant_id>/regenerate', methods=['POST'])
@admin_required
def admin_regenerate_link(participant_id):
    participant = db.get_or_404(Participant, participant_id)
    # The old link stops working and signs out every browser that used it.
    participant.token = new_token()
    participant.joined_at = None
    db.session.commit()
    return jsonify(admin_info(participant))


if __name__ == '__main__':
    app.run(
        host=os.environ.get('HOST', '127.0.0.1'),
        port=int(os.environ.get('PORT', 5003)),
        debug=os.environ.get('FLASK_DEBUG') == '1',
    )

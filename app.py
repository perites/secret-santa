from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from models import db, User, Recipient
import os
from datetime import datetime
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///santa.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'super_secret_santa_key' 
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB max

db.init_app(app)

DEADLINE = datetime(2025, 12, 10)
ADMIN_PIN = "Tea&Cakes&After&Lessons"

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    with app.app_context():
        db.create_all()


@app.before_request
def check_auth():
    if request.endpoint == 'static' or request.endpoint == 'uploaded_file':
        return

    user_uuid = request.cookies.get('santa_uuid')
    
    if not user_uuid:
        new_uuid = str(uuid.uuid4())
        new_user = User(uuid=new_uuid, username=f"Elf_{new_uuid[:8]}")
        db.session.add(new_user)
        db.session.commit()
        session['user_id'] = new_user.id
        session['user_uuid'] = new_uuid
        request.set_auth_cookie = new_uuid
    else:
        user = User.query.filter_by(uuid=user_uuid).first()
        if not user:
            new_uuid = str(uuid.uuid4())
            new_user = User(uuid=new_uuid, username=f"Elf_{new_uuid[:8]}")
            db.session.add(new_user)
            db.session.commit()
            session['user_id'] = new_user.id
            session['user_uuid'] = new_uuid
            request.set_auth_cookie = new_uuid
        else:
            session['user_id'] = user.id
            session['user_uuid'] = user.uuid

@app.after_request
def set_cookie(response):
    if hasattr(request, 'set_auth_cookie'):
        response.set_cookie('santa_uuid', request.set_auth_cookie, max_age=60*60*24*365)
    return response

@app.route('/')
def index():
    deadline_passed = datetime.now() > DEADLINE
    return render_template('index.html', deadline_passed=deadline_passed)

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    pin = request.json.get('pin')
    if pin == ADMIN_PIN:
        session['admin_auth'] = True
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid PIN'}), 401

@app.route('/api/admin/check_auth')
def check_admin_auth():
    return jsonify({'authenticated': session.get('admin_auth', False)})

@app.route('/api/recipients')
def get_recipients():
    # Sort alphabetically by name
    recipients = Recipient.query.order_by(Recipient.name.asc()).all()
    data = []
    for r in recipients:
        is_taken = r.taken_by_user_id is not None
        taken_by_me = r.taken_by_user_id == session['user_id']
        
        data.append({
            'id': r.id,
            'name': r.name,
            'image_url': url_for('static', filename=f'uploads/{r.image_filename}') if r.image_filename else None,
            'is_taken': is_taken,
            'taken_by_me': taken_by_me
        })
    return jsonify(data)

@app.route('/api/take/<int:recipient_id>', methods=['POST'])
def take_recipient(recipient_id):
    if datetime.now() > DEADLINE:
        return jsonify({'error': 'The deadline for choosing a present has passed (Dec 10, 2025).'}), 403

    recipient = Recipient.query.get_or_404(recipient_id)
    
    if recipient.taken_by_user_id is not None:
        if recipient.taken_by_user_id == session['user_id']:
             return jsonify({'message': 'You already took this person.'})
        return jsonify({'error': 'This person is already taken.'}), 400
    
    current_user = User.query.get(session['user_id'])
    existing_gift = Recipient.query.filter_by(taken_by_user_id=current_user.id).first()
    if existing_gift:
         return jsonify({'error': 'You have already selected a person. Untake them first to switch.'}), 400

    recipient.taken_by_user_id = session['user_id']
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/untake/<int:recipient_id>', methods=['POST'])
def untake_recipient(recipient_id):
    if datetime.now() > DEADLINE:
        return jsonify({'error': 'The deadline for changing your choice has passed (Dec 10, 2025).'}), 403

    recipient = Recipient.query.get_or_404(recipient_id)
    
    if recipient.taken_by_user_id != session['user_id']:
        return jsonify({'error': 'You cannot untake a person you did not take.'}), 403
    
    recipient.taken_by_user_id = None
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/admin/add_recipient', methods=['POST'])
def add_recipient():
    if not session.get('admin_auth'):
        return jsonify({'error': 'Unauthorized'}), 401

    name = request.form.get('name')
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    
    image_filename = None
    if 'image' in request.files:
        file = request.files['image']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
            image_filename = unique_filename

    new_recipient = Recipient(name=name, image_filename=image_filename)
    db.session.add(new_recipient)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/admin/delete_recipient/<int:id>', methods=['DELETE'])
def delete_recipient(id):
    if not session.get('admin_auth'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    recipient = Recipient.query.get_or_404(id)
    db.session.delete(recipient)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/admin/edit_recipient/<int:id>', methods=['POST'])
def edit_recipient(id):
    if not session.get('admin_auth'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    recipient = Recipient.query.get_or_404(id)
    name = request.form.get('name')
    if name:
        recipient.name = name
    
    if 'image' in request.files:
        file = request.files['image']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
            recipient.image_filename = unique_filename
            
    db.session.commit()
    return jsonify({'success': True})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5003)

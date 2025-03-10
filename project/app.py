from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import boto3

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['S3_BUCKET_NAME'] = "testbucketpian"
app.config['S3_ACCESS_KEY'] = "AKIAY6QVY4LJ4SRR5THN"
app.config['S3_SECRET_KEY'] = "5hl8MbMql3McqIJVtuIGLJmeTtJhNbFLXqXaSaku"
app.config['S3_REGION'] = "eu-central-1"

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)

class Folder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parent = db.relationship('Folder', remote_side=[id], backref='subfolders')

class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=False)

def create_tables():
    db.create_all()

def upload_to_s3(file, filename):
    s3 = boto3.client(
        "s3",
        aws_access_key_id=app.config["S3_ACCESS_KEY"],
        aws_secret_access_key=app.config["S3_SECRET_KEY"],
        region_name=app.config["S3_REGION"]
    )
    
    s3.upload_fileobj(
        file,
        app.config["S3_BUCKET_NAME"],
        filename,
        ExtraArgs={"ACL": "public-read"}
    )
    
    return f"https://{app.config['S3_BUCKET_NAME']}.s3.amazonaws.com/{filename}"

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        
        if User.query.filter_by(username=username).first():
            return 'User already exists!'
        
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('photo_album'))
        return 'Invalid credentials'
    return render_template('login.html')

@app.route('/photo_album', methods=['GET', 'POST'])
def photo_album():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    folders = Folder.query.filter_by(user_id=user_id, parent_id=None).all()
    
    if request.method == 'POST':
        if 'folder_name' in request.form:
            folder_name = request.form['folder_name']
            new_folder = Folder(name=folder_name, user_id=user_id)
            db.session.add(new_folder)
            db.session.commit()
            return redirect(url_for('photo_album'))
    
    return render_template('photo_album.html', user_id=user_id, folders=folders)

@app.route('/delete_photo/<int:photo_id>', methods=['POST'])
def delete_photo(photo_id):
    # Ваш код для видалення фото
    return redirect(url_for('some_other_page'))

@app.route('/some_other_page')
def some_other_page():
    return render_template('photo_album.html')


@app.route('/delete_folder/<int:folder_id>', methods=['POST'])
def delete_folder(folder_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    folder = Folder.query.get_or_404(folder_id)
    if folder.user_id != session['user_id']:
        return 'Unauthorized', 403

    # Видалення всіх підпапок і фото в них
    def delete_recursive(folder):
        for subfolder in folder.subfolders:
            delete_recursive(subfolder)
        Photo.query.filter_by(folder_id=folder.id).delete()
        db.session.delete(folder)

    delete_recursive(folder)

    db.session.commit()
    return redirect(url_for('photo_album'))


@app.route('/folder/<int:folder_id>', methods=['GET', 'POST'])
def view_folder(folder_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    folder = Folder.query.get_or_404(folder_id)
    if folder.user_id != user_id:
        return 'Unauthorized', 403
    
    photos = Photo.query.filter_by(user_id=user_id, folder_id=folder_id).all()
    subfolders = Folder.query.filter_by(user_id=user_id, parent_id=folder_id).all()
    
    if request.method == 'POST':
        if 'folder_name' in request.form:
            folder_name = request.form['folder_name']
            new_folder = Folder(name=folder_name, parent_id=folder_id, user_id=user_id)
            db.session.add(new_folder)
            db.session.commit()
            return redirect(url_for('view_folder', folder_id=folder_id))
    
    return render_template('folder.html', folder=folder, photos=photos, subfolders=subfolders)

@app.route('/upload', methods=['POST'])
def upload_photo():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    folder_id = request.form.get('folder_id')
    if not folder_id:
        return 'Photo must be uploaded into a folder.', 400
    
    folder = Folder.query.get(folder_id)
    if not folder or folder.user_id != session['user_id']:
        return 'Invalid folder selection.', 403
    
    file = request.files['photo']
    if file:
        filename = secure_filename(file.filename)
        file_url = upload_to_s3(file, filename)
        
        new_photo = Photo(filename=file_url, user_id=session['user_id'], folder_id=folder_id)
        db.session.add(new_photo)
        db.session.commit()
        return redirect(url_for('view_folder', folder_id=folder_id))
    
    return 'Upload failed', 400

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        create_tables()
    app.run(debug=True)

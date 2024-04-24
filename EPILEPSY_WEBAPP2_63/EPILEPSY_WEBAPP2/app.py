from flask import Flask, request, render_template, redirect, session, url_for
from flask_sqlalchemy import SQLAlchemy
import bcrypt
import numpy as np
import os
from keras.preprocessing.image import load_img
from keras.preprocessing.image import img_to_array
from keras.models import load_model
import pandas as pd
from datetime import datetime

# Load model
model = load_model("model_mobilenet.h5")
print('@@ Model loaded')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)
app.secret_key = 'secret_key'


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))

    def __init__(self, email, password, name):
        self.name = name
        self.email = email
        self.password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))


with app.app_context():
    db.create_all()


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return render_template('register.html', error='Email already exists. Please use a different email.')

        new_user = User(email=email, password=password, name=name)
        db.session.add(new_user)
        db.session.commit()

        return redirect('/login')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            session['email'] = user.email
            session['username'] = user.name
            return redirect('/index')
        else:
            return render_template('login.html', error='Invalid email or password.')

    return render_template('login.html')


@app.route('/index', methods=['GET'])
def index():
    if 'email' not in session:
        return redirect(url_for('login'))
    username = session['username']  # Get the username from the session
    return render_template('index.html', username=username, result="")


def pred_epilepsy(epilepsy_or_not):
    test_image = load_img(epilepsy_or_not, target_size=(224, 224))
    print("@@ Got Image for prediction")

    test_image = img_to_array(test_image) / 255
    test_image = np.expand_dims(test_image, axis=0)

    result = model.predict(test_image).round(3)
    print('@@ Raw result = ', result)

    pred = np.argmax(result)
    confidence = float(result[0][pred])

    if pred == 0:
        print('Predicted class: Not Affected')
    else:
        print('Predicted class: Affected')
    print('Confidence:', confidence)  # Print confidence here

    return "Not Affected" if pred == 0 else "Affected", confidence


def save_to_excel(username, email, prediction, uploaded_image):
    data = {
        'Date': [datetime.now().strftime('%Y-%m-%d')],
        'Time': [datetime.now().strftime('%H:%M:%S')],
        'Name': [username],
        'Gmail': [email],
        'Uploaded Image': [uploaded_image],
        'Predicted Result': [prediction]
    }

    df = pd.DataFrame(data)
    if os.path.isfile('Registration_History.xlsx'):
        df_existing = pd.read_excel('Registration_History.xlsx')
        df = pd.concat([df_existing, df], ignore_index=True)
    df.to_excel('Registration_History.xlsx', index=False)


@app.route("/predict", methods=['POST'])
def predict():
    if request.method == 'POST':
        file = request.files['image']
        filename = file.filename
        print("@@ Input posted = ", filename)

        file_path = os.path.join('static/user_uploaded', filename)
        file.save(file_path)

        print("@@ Predicting class and accuracy...")
        pred, confidence = pred_epilepsy(epilepsy_or_not=file_path)

        # Save prediction data to Excel
        save_to_excel(session['username'], session['email'], pred, os.path.basename(file_path))

        return render_template('predict.html', pred_output=pred, confidence=confidence, user_image=file_path)


@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect('/login')


if __name__ == '__main__':
    app.run(debug=True)

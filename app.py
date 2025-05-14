import secrets
import datetime
import pymysql
import os
import mysql.connector
from flask import Flask, render_template, request, url_for, redirect, session, flash, jsonify
from flask_mail import Mail, Message
from flask import session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_wtf.file import FileField, FileAllowed
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo

app = Flask(__name__)
app.secret_key = "your_secret_key_here"
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = "akshayacrao1105@gmail.com"
app.config['MAIL_PASSWORD'] = "fahn wsnq onhm dark"
app.config['MAIL_DEFAULT_SENDER'] = "akshayacrao1105@gmail.com"

mail = Mail(app)

# 🔗 Database Connection
def get_db_connection():
    try:
        conn = pymysql.connect(
            host='localhost',
            user='root',
            password="akshaya11*",
            database='mamas_nest',
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except pymysql.MySQLError as e:
        print("Database connection failed:", e)
        return None

class SignUpForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    role = SelectField('Role', choices=[('user', 'User'), ('doctor', 'Doctor')], validators=[DataRequired()])
    license = FileField('Upload Medical License', validators=[FileAllowed(['pdf', 'jpg', 'jpeg', 'png'], 'PDF or image only')])
    photo = FileField('Upload Profile Photo', validators=[FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')])
    

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignUpForm()

    if request.method == 'POST':
        if not form.validate_on_submit():
            print("❌ Form Validation Failed:", form.errors)
            flash("Please fix the form errors.", "danger")
            return render_template('signup.html', form=form)

        name = form.name.data.strip()
        email = form.email.data.strip().lower()
        password = form.password.data
        role = form.role.data
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        if not conn:
            flash("Database connection error!", "danger")
            return render_template('signup.html', form=form)

        cursor = conn.cursor()

        # Check if email exists in any table
        for table in ['users', 'doctors', 'admins']:
            cursor.execute(f"SELECT id FROM {table} WHERE email = %s", (email,))
            if cursor.fetchone():
                flash(f"Email already exists in {table.title()}!", "danger")
                cursor.close()
                conn.close()
                return render_template('signup.html', form=form)

        try:
            if role == 'user':
                cursor.execute("""
                    INSERT INTO users (name, email, password, role)
                    VALUES (%s, %s, %s, %s)
                """, (name, email, hashed_password, role))
                conn.commit()

                cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                user = cursor.fetchone()

                session['user_id'] = user['id']
                session['name'] = user['name']
                session['role'] = role
                flash("Signup successful!", "success")
                return redirect(url_for('dashboard'))

            elif role == 'doctor':
                license_file = form.license.data
                photo_file = form.photo.data
                license_filename = None
                photo_filename = None

                if license_file:
                    license_filename = secure_filename(license_file.filename)
                    license_file.save(os.path.join(app.config['UPLOAD_FOLDER'], license_filename))

                if photo_file:
                    photo_filename = secure_filename(photo_file.filename)
                    photo_file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))

                cursor.execute("""
                    INSERT INTO doctors (name, email, password, license_path, photo_path, status, is_verified)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (name, email, hashed_password, license_filename, photo_filename, 'active', 0))
                conn.commit()

                cursor.execute("SELECT * FROM doctors WHERE email = %s", (email,))
                doctor = cursor.fetchone()

                session['user_id'] = doctor['id']
                session['name'] = doctor['name']
                session['role'] = role
                flash("Please complete your profile to proceed.", "info")
                return redirect(url_for('complete_doctor_profile'))

        except Exception as e:
            conn.rollback()
            print("❌ Exception in signup:", e)
            flash("Something went wrong during signup.", "danger")
        finally:
            cursor.close()
            conn.close()

    return render_template('signup.html', form=form)


# Keep the rest of the routes unchanged unless explicitly requested

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'user':
            return redirect(url_for('already_logged_in'))
        elif role == 'doctor':
            return redirect(url_for('doctor_dashboard'))
        elif role == 'admin':
            return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password']

        conn = get_db_connection()
        if not conn:
            flash("Database connection error!", "danger")
            return render_template('login.html')

        cursor = conn.cursor()

        # Check users
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        role = 'user'

        if user:
            if user.get('role') == 'disabled':
                flash("Your account has been disabled by the admin.", "danger")
                cursor.close()
                conn.close()
                return render_template('login.html')
        else:
            # Check doctors
            cursor.execute("SELECT * FROM doctors WHERE email = %s", (email,))
            user = cursor.fetchone()
            role = 'doctor'

            if user:
                if user.get('status') == 'disabled':
                    flash("Your doctor account has been disabled by the admin.", "danger")
                    cursor.close()
                    conn.close()
                    return render_template('login.html')

                if not user.get("is_verified", True):
                    flash("Doctor account not verified yet.", "warning")
                    cursor.close()
                    conn.close()
                    return render_template('login.html')
            else:
                # Check admin
                cursor.execute("SELECT * FROM admins WHERE email = %s", (email,))
                user = cursor.fetchone()
                role = 'admin'

        cursor.close()
        conn.close()

        if user:
            if role == 'admin':
                if user['password'] == password:
                    session['user_id'] = user['id']  # ✅ Set session
                    session['name'] = user['name']
                    session['role'] = role
                    return redirect(url_for('admin_dashboard'))
            else:
                if check_password_hash(user['password'], password):
                    session['user_id'] = user['id']  # ✅ Set session
                    session['name'] = user['name']
                    session['role'] = role
                    if role == 'user':
                        return redirect(url_for('dashboard'))
                    elif role == 'doctor':
                        return redirect(url_for('doctor_dashboard'))

        flash("Invalid email or password!", "danger")

    return render_template('login.html')


@app.route('/already-logged-in')
def already_logged_in():
    name = session.get('name')
    role = session.get('role')
    return render_template('already_logged_in.html', name=name, role=role)


@app.route('/check-email')
def check_email():
    email = request.args.get('email')

    conn = get_db_connection()
    cursor = conn.cursor()

    # 🔍 Check users
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    # 🔍 Check doctors if not in users
    if not user:
        cursor.execute("SELECT id FROM doctors WHERE email = %s", (email,))
        user = cursor.fetchone()

    # 🔍 Check admins if not in doctors
    if not user:
        cursor.execute("SELECT id FROM admins WHERE email = %s", (email,))
        user = cursor.fetchone()

    cursor.close()
    conn.close()

    # ✅ Return true if exists in any table
    return jsonify({"exists": bool(user)})

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        try:
            email = request.form.get('email')

            conn = get_db_connection()
            if not conn:
                flash("Database connection error!", "danger")
                return redirect(url_for('forgot_password'))

            cursor = conn.cursor()

            cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
            user = cursor.fetchone()

            if user:
                reset_token = secrets.token_urlsafe(20)
                expiry_time = (datetime.datetime.now() + datetime.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute(
                    "UPDATE users SET reset_token=%s, reset_token_expiry=%s WHERE id=%s",
                    (reset_token, expiry_time, user["id"])
                )
                conn.commit()

                reset_link = url_for('reset_password', token=reset_token, _external=True)
                msg = Message("Password Reset Request", recipients=[email])
                msg.body = f"Click the link to reset your password:\n{reset_link}\n\nThis link expires in 1 hour."

                try:
                    mail.send(msg)
                    flash("✅ A password reset link has been sent to your email.", "info")
                except Exception as e:
                    print("❌ Error sending email:", e)
                    flash("⚠️ Unable to send reset email. Please try again later.", "danger")
            else:
                flash("⚠️ Email not found.", "warning")

            cursor.close()
            conn.close()

        except Exception as err:
            import traceback
            print("🔥 ERROR OCCURRED IN FORGOT PASSWORD:")
            traceback.print_exc()
            flash("Something went wrong! Please try again later.", "danger")

        return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    conn = get_db_connection()
    if not conn:
        flash("Database connection error!", "danger")
        return redirect(url_for('forgot_password'))

    cursor = conn.cursor()

    # You can choose to check users/doctors/admins here too
    cursor.execute("SELECT id, reset_token_expiry FROM users WHERE reset_token=%s", (token,))
    user = cursor.fetchone()
    print("🔐 Token received from URL:", token)
    cursor.execute("SELECT reset_token, reset_token_expiry FROM users WHERE reset_token=%s", (token,))
    debug = cursor.fetchone()
    print("📦 Token in DB:", debug)

    if not user:
        flash("Invalid or expired token.", "danger")
        return redirect(url_for('forgot_password'))

    expiry_time = user["reset_token_expiry"]
    if datetime.datetime.now() > expiry_time:

        flash("Token expired! Request a new one.", "danger")
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form['password']
        confirm_password = request.form['confirm_password']

        if new_password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('reset_password', token=token))

        hashed_password = generate_password_hash(new_password)

        cursor.execute(
            "UPDATE users SET password=%s, reset_token=NULL, reset_token_expiry=NULL WHERE id=%s",
            (hashed_password, user["id"])
        )
        conn.commit()

        flash("Password successfully reset. You can now log in.", "success")
        return redirect(url_for('login'))

    cursor.close()
    conn.close()
    return render_template('reset_password.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('role') != 'user':
        flash("Access denied!", "danger")
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/doctor-dashboard')
def doctor_dashboard():
    if 'user_id' not in session or session.get('role') != 'doctor':
        flash("Access denied!", "danger")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM appointments
        WHERE doctor_id = %s
        ORDER BY appointment_date, appointment_time
    """, (session['user_id'],))
    appointments = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('doctor_dashboard.html', appointments=appointments)

@app.route('/doctor-patients')
def doctor_patients():
    if 'user_id' not in session or session.get('role') != 'doctor':
        return redirect(url_for('login'))

    doctor_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            patient_name,
            patient_email,
            MAX(appointment_date) AS last_appointment,
            MAX(phone) AS phone
        FROM appointments
        WHERE doctor_id = %s
        GROUP BY patient_name, patient_email
        ORDER BY last_appointment DESC
    """, (doctor_id,))

    patients = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('doctor_patients.html', patients=patients)

@app.route('/doctor/edit-profile', methods=['GET', 'POST'])
def doctor_profile():
    if 'user_id' not in session or session.get('role') != 'doctor':
        return redirect(url_for('login'))

    doctor_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        hospital = request.form['hospital_name']
        experience = request.form['experience']
        specialization = request.form['specialization']
        days = request.form['availability_days']
        time = request.form['availability_time']

        photo = request.files.get('photo')
        if photo and photo.filename:
            filename = secure_filename(photo.filename)
            photo_path = f"uploads/{filename}"
            photo.save(os.path.join(app.static_folder, 'uploads', filename))
            cursor.execute("""UPDATE doctors SET name=%s, hospital_name=%s,
                              experience=%s, specialization=%s, availability_days=%s,
                              availability_time=%s, photo_path=%s WHERE id=%s""",
                           (name, hospital, experience, specialization, days, time, photo_path, doctor_id))
        else:
            cursor.execute("""UPDATE doctors SET name=%s,  hospital_name=%s,
                              experience=%s, specialization=%s, availability_days=%s,
                              availability_time=%s WHERE id=%s""",
                           (name,  hospital, experience, specialization, days, time, doctor_id))

        conn.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for('doctor_profile'))

    cursor.execute("SELECT * FROM doctors WHERE id = %s", (doctor_id,))
    doctor = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('doctor_profile.html', doctor=doctor)

@app.route('/admin-dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Access denied!", "danger")
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html')

@app.route('/admin/users')
def manage_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('manage_users.html', users=users)

# Route to disable user
@app.route('/admin/users/disable/<int:user_id>', methods=['POST'])
def disable_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role = 'disabled' WHERE id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("User disabled successfully!", "info")
    return redirect(url_for('manage_users'))


# Route to enable user
@app.route('/admin/users/enable/<int:user_id>', methods=['POST'])
def enable_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role = 'user' WHERE id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("User enabled successfully!", "success")
    return redirect(url_for('manage_users'))

@app.route('/manage_doctors')
def manage_doctors():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Access denied!", "danger")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM doctors")
    doctors = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('manage_doctors.html', doctors=doctors)
@app.route('/disable_doctor/<int:doctor_id>')
def disable_doctor(doctor_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE doctors SET status = 'disabled' WHERE id = %s", (doctor_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Doctor disabled successfully.", "info")
    return redirect(url_for('manage_doctors'))

@app.route('/enable_doctor/<int:doctor_id>')
def enable_doctor(doctor_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE doctors SET status = 'active' WHERE id = %s", (doctor_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Doctor enabled successfully.", "success")
    return redirect(url_for('manage_doctors'))

@app.route('/verify_doctor/<int:doctor_id>')
def verify_doctor(doctor_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE doctors SET is_verified = 1 WHERE id = %s", (doctor_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Doctor verified successfully.", "success")
    return redirect(url_for('manage_doctors'))
@app.route('/admin/doctor/<int:doctor_id>')
def view_doctor_profile(doctor_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM doctors WHERE id = %s", (doctor_id,))
        doctor = cursor.fetchone()
    conn.close()

    if not doctor:
        return "Doctor not found", 404

    return render_template('admin_doctor_profile.html', doctor=doctor)


@app.route('/admin/settings', methods=['GET', 'POST'])
def admin_settings():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        email = request.form.get('email')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        cursor.execute("SELECT * FROM admins WHERE id = %s", (session['user_id'],))
        admin = cursor.fetchone()

        if admin['password'] != current_password:
            flash("Current password is incorrect.", "danger")
        elif new_password != confirm_password:
            flash("New passwords do not match.", "warning")
        else:
            update_query = "UPDATE admins SET password = %s"
            params = [new_password]

            if email:
                update_query += ", email = %s"
                params.append(email)

            update_query += " WHERE id = %s"
            params.append(session['user_id'])

            cursor.execute(update_query, tuple(params))
            conn.commit()
            flash("Admin details updated successfully!", "success")

    cursor.close()
    conn.close()

    return render_template("admin_settings.html")
@app.route('/admin/report')
def admin_report():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Basic Metrics
    cursor.execute("SELECT COUNT(*) AS total FROM users")
    total_users = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) AS total FROM doctors")
    total_doctors = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) AS verified FROM doctors WHERE is_verified = 1")
    verified_doctors = cursor.fetchone()['verified']

    cursor.execute("SELECT COUNT(*) AS messages FROM contact_messages")
    total_messages = cursor.fetchone()['messages']

    cursor.close()
    conn.close()

    return render_template("admin_report.html",
        total_users=total_users,
        total_doctors=total_doctors,
        verified_doctors=verified_doctors,
        total_messages=total_messages
    )

@app.route('/admin/messages')
def admin_messages():
    # Optionally check for admin session
    # if not session.get('is_admin'): return redirect(url_for('login'))

    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="akshaya11*",
        database="mamas_nest"
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM contact_messages ORDER BY submitted_at DESC")
    messages = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('admin_messages.html', messages=messages)
# Add these imports at the top if not already present
import os
from werkzeug.utils import secure_filename

# Configure upload folder for product images
UPLOAD_FOLDER = 'static/products'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/admin/product')
def admin_product():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM products")
        products = cursor.fetchall()
    conn.close()
    return render_template('admin_product.html', products=products)





# Add Exercise
@app.route('/admin/add-exercise', methods=['GET', 'POST'])
def add_exercise():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description')
        trimester = request.form.get('trimester')
        video = request.files.get('video')
        video_path = None
        if video and video.filename:
            filename = secure_filename(video.filename)
            video.save(os.path.join('static/exercise/videos', filename))
            video_path = f"exercise/videos/{filename}"
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO exercise_videos (title, description, video_path, trimester) VALUES (%s, %s, %s, %s)",
            (title, description, video_path, trimester)
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash('Exercise video added!', 'success')
        return redirect(url_for('manage_wellness'))
    return render_template('admin_add_exercise.html')

# Edit Exercise
@app.route('/admin/edit-exercise/<int:video_id>', methods=['GET', 'POST'])
def edit_exercise(video_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM exercise_videos WHERE id = %s", (video_id,))
    exercise = cursor.fetchone()
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description')
        trimester = request.form.get('trimester')
        video = request.files.get('video')
        video_path = exercise['video_path']
        if video and video.filename:
            filename = secure_filename(video.filename)
            video.save(os.path.join('static/exercise/videos', filename))
            video_path = f"exercise/videos/{filename}"
        cursor.execute(
            "UPDATE exercise_videos SET title=%s, description=%s, video_path=%s, trimester=%s WHERE id=%s",
            (title, description, video_path, trimester, video_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash('Exercise video updated!', 'success')
        return redirect(url_for('manage_wellness'))
    cursor.close()
    conn.close()
    return render_template('admin_edit_exercise.html', exercise=exercise)

# Delete Exercise
@app.route('/admin/delete-exercise/<int:video_id>', methods=['POST'])
def delete_exercise(video_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM exercise_videos WHERE id = %s", (video_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Exercise video deleted!', 'info')
    return redirect(url_for('manage_wellness'))

@app.route('/manage_wellness')
def manage_wellness():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM ebooks ORDER BY uploaded_at DESC")
    ebooks = cursor.fetchall()

    cursor.execute("SELECT * FROM exercise_videos ORDER BY uploaded_at DESC")
    exercises = cursor.fetchall()

    cursor.execute("SELECT * FROM music_tracks ORDER BY uploaded_at DESC")
    music = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('manage_wellness.html', ebooks=ebooks, exercises=exercises, music=music)

# Add E-Book
@app.route('/admin/add-ebook', methods=['GET', 'POST'])
def add_ebook():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description')
        content = request.form.get('content')
        image = request.files.get('image')
        image_path = None
        if image and image.filename:
            filename = secure_filename(image.filename)
            image.save(os.path.join('static/ebooks/images', filename))
            image_path = f"ebooks/images/{filename}"
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO ebooks (title, description, image_path, content) VALUES (%s, %s, %s, %s)",
            (title, description, image_path, content)
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash('E-Book added!', 'success')
        return redirect(url_for('manage_wellness'))
    return render_template('admin_add_ebook.html')

# Edit E-Book
@app.route('/admin/edit-ebook/<int:ebook_id>', methods=['GET', 'POST'])
def edit_ebook(ebook_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ebooks WHERE id = %s", (ebook_id,))
    ebook = cursor.fetchone()
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description')
        content = request.form.get('content')
        image = request.files.get('image')
        image_path = ebook['image_path']
        if image and image.filename:
            filename = secure_filename(image.filename)
            image.save(os.path.join('static/ebooks/images', filename))
            image_path = f"ebooks/images/{filename}"
        cursor.execute(
            "UPDATE ebooks SET title=%s, description=%s, image_path=%s, content=%s WHERE id=%s",
            (title, description, image_path, content, ebook_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash('E-Book updated!', 'success')
        return redirect(url_for('manage_wellness'))
    cursor.close()
    conn.close()
    return render_template('admin_edit_ebook.html', ebook=ebook)

# Delete E-Book
@app.route('/admin/delete-ebook/<int:ebook_id>', methods=['POST'])
def delete_ebook(ebook_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ebooks WHERE id = %s", (ebook_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('E-Book deleted!', 'info')
    return redirect(url_for('manage_wellness'))

# Add Music
@app.route('/admin/add-music', methods=['GET', 'POST'])
def add_music():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description')
        audio = request.files.get('audio')
        audio_path = None
        if audio and audio.filename:
            filename = secure_filename(audio.filename)
            audio.save(os.path.join('static/music/audio', filename))
            audio_path = f"music/audio/{filename}"
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO music_tracks (title, description, audio_path) VALUES (%s, %s, %s)",
            (title, description, audio_path)
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash('Music track added!', 'success')
        return redirect(url_for('manage_wellness'))
    return render_template('admin_add_music.html')

# Edit Music
@app.route('/admin/edit-music/<int:music_id>', methods=['GET', 'POST'])
def edit_music(music_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM music_tracks WHERE id = %s", (music_id,))
    music = cursor.fetchone()
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description')
        audio = request.files.get('audio')
        audio_path = music['audio_path']
        if audio and audio.filename:
            filename = secure_filename(audio.filename)
            audio.save(os.path.join('static/music/audio', filename))
            audio_path = f"music/audio/{filename}"
        cursor.execute(
            "UPDATE music_tracks SET title=%s, description=%s, audio_path=%s WHERE id=%s",
            (title, description, audio_path, music_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash('Music track updated!', 'success')
        return redirect(url_for('manage_wellness'))
    cursor.close()
    conn.close()
    return render_template('admin_edit_music.html', music=music)

# Delete Music
@app.route('/admin/delete-music/<int:music_id>', methods=['POST'])
def delete_music(music_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM music_tracks WHERE id = %s", (music_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Music track deleted!', 'info')
    return redirect(url_for('manage_wellness'))
@app.route('/admin/add-product', methods=['GET', 'POST'])
def add_new_product():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Access denied!", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        price = request.form.get('price')
        original_price = request.form.get('original_price')
        discount = request.form.get('discount')
        sizes = request.form.get('sizes')
        description = request.form.get('description')
        image_file = request.files.get('image')

        if not name or not price or not category or not image_file:
            flash("All required fields must be filled.", "warning")
            return redirect(url_for('add_new_product'))

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)
        else:
            flash("Invalid image format!", "danger")
            return redirect(url_for('add_new_product'))

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO products (name, image, price, original_price, discount, category, sizes, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (name, filename, price, original_price, discount, category, sizes, description))
            conn.commit()
            cursor.close()
            conn.close()
            flash("✅ Product added successfully!", "success")
            return redirect(url_for('admin_product'))

        except Exception as e:
            print("❌ DB error:", e)
            flash("Something went wrong while adding product.", "danger")

    return render_template('admin_add_product.html')
@app.route('/admin/edit-product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Access denied!", "danger")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch product to edit
    cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
    product = cursor.fetchone()

    if not product:
        flash("Product not found!", "warning")
        return redirect(url_for('admin_product'))

    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        price = request.form['price']
        original_price = request.form.get('original_price')
        discount = request.form.get('discount')
        sizes = request.form.get('sizes')
        description = request.form.get('description')
        image_file = request.files.get('image')

        # Handle optional image upload
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)
            cursor.execute("""
                UPDATE products SET name=%s, category=%s, price=%s,
                original_price=%s, discount=%s, sizes=%s, description=%s, image=%s
                WHERE id=%s
            """, (name, category, price, original_price, discount, sizes, description, filename, product_id))
        else:
            cursor.execute("""
                UPDATE products SET name=%s, category=%s, price=%s,
                original_price=%s, discount=%s, sizes=%s, description=%s
                WHERE id=%s
            """, (name, category, price, original_price, discount, sizes, description, product_id))

        conn.commit()
        cursor.close()
        conn.close()
        flash("✅ Product updated successfully!", "success")
        return redirect(url_for('admin_product'))

    cursor.close()
    conn.close()
    return render_template('admin_edit_product.html', product=product)
@app.route('/admin/delete-product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Access denied!", "danger")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
    conn.commit()

    cursor.close()
    conn.close()
    flash("🗑️ Product deleted successfully!", "info")
    return redirect(url_for('admin_product'))

@app.route('/')
def home():
    return render_template('dashboard.html')

@app.route('/about')
def about():
    return render_template('about.html')

# 🏠 Dashboard Routes

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        if 'user_id' not in session:
            flash("Please log in to send a message.", "warning")
            return redirect(url_for('login'))

        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')

        print("📥 Form submitted:", name, email, message)

        try:
            conn = mysql.connector.connect(
                host="localhost",
                user="root",
                password="akshaya11*",
                database="mamas_nest"
            )
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO contact_messages (name, email, message)
                VALUES (%s, %s, %s)
            """, (name, email, message))
            conn.commit()
            print("✅ Inserted into DB successfully.")
            cursor.close()
            conn.close()
        except Exception as e:
            print("❌ DB Insert Error:", e)

        flash("Message sent successfully!", "success")
        return redirect(url_for('contact'))

    return render_template('contact.html')

from flask import flash, redirect, url_for

@app.route('/appointment', methods=['GET', 'POST'])
def appointment():
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='akshaya11*',
        database='mamas_nest'
    )
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        phone = request.form['phone'].strip()
        date = request.form['date']
        time = request.form['time']
        notes = request.form['notes'].strip()
        doctor_id = request.form['doctor_id']

        if not name or not email or not phone or not date or not time or not doctor_id:
            flash("⚠️ All fields are required.", "danger")
            return redirect(url_for('appointment'))

        if not phone.isdigit() or len(phone) != 10:
            flash("📞 Phone number must be exactly 10 digits.", "danger")
            return redirect(url_for('appointment'))

        # Check for duplicate booking
        cursor.execute("""
            SELECT COUNT(*) AS count FROM appointments
            WHERE doctor_id = %s AND appointment_date = %s AND appointment_time = %s
            AND status IN ('Pending', 'Accepted')
        """, (doctor_id, date, time))
        existing = cursor.fetchone()

        if existing and existing['count'] > 0:
            flash("❌ This slot is already booked. Please choose another time.", "danger")
            return redirect(url_for('appointment'))

        # Save appointment
        cursor.execute("""
            INSERT INTO appointments (patient_name, patient_email, phone, appointment_date,
                                      appointment_time, notes, doctor_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pending')
        """, (name, email, phone, date, time, notes, doctor_id))
        conn.commit()
        conn.close()

        flash("✅ Appointment booked successfully!", "success")
        return redirect(url_for('appointment'))

    # GET handling
    cursor.execute("SELECT * FROM doctors WHERE is_verified = 1 AND status = 'active'")
    doctors = cursor.fetchall()
    for doc in doctors:
        cursor.execute(
            "SELECT appointment_date, appointment_time FROM appointments WHERE doctor_id=%s AND status IN ('Pending', 'Accepted')",
            (doc['id'],)
        )
        bookings = cursor.fetchall()
        doc['booked_slots'] = ';'.join([f"{b['appointment_date']}_{b['appointment_time']}" for b in bookings])

    cursor.execute("""
        SELECT doctor_id, appointment_date, appointment_time FROM appointments
        WHERE status IN ('Pending', 'Accepted')
    """)
    booked_data = cursor.fetchall()
    conn.close()

    booked_slots = {}
    for row in booked_data:
        key = str(row['doctor_id'])
        slot = f"{row['appointment_date']}_{row['appointment_time']}"
        booked_slots.setdefault(key, []).append(slot)

    return render_template("appointment.html", doctors=doctors, booked_slots=booked_slots)

@app.route('/my_appointments')
def my_appointments():
    if 'user_id' not in session or session.get('role') != 'user':
        flash("Access denied! Please login as User.", "danger")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch appointments for the logged-in user
    cursor.execute("""
    SELECT a.id, a.appointment_date, a.appointment_time, a.status, a.notes,
           d.name AS doctor_name, d.specialization, d.hospital_name
    FROM appointments a
    JOIN users u ON a.patient_email = u.email
    JOIN doctors d ON d.id = a.doctor_id
    WHERE u.id = %s
    ORDER BY a.appointment_date DESC
""", (session['user_id'],))


    appointments = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('my_appointments.html', appointments=appointments)

@app.route('/user/appointments/cancel/<int:appointment_id>', methods=['POST'])
def cancel_appointment(appointment_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # 🔥 Update status to Cancelled instead of deleting
    cursor.execute("UPDATE appointments SET status = 'Cancelled' WHERE id = %s", (appointment_id,))
    conn.commit()

    cursor.close()
    conn.close()

    flash("Appointment cancelled successfully!", "info")
    return redirect(url_for('my_appointments'))


@app.route('/doctor/appointments/accept/<int:appointment_id>')
def accept_appointment(appointment_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE appointments SET status = 'Confirmed' WHERE id = %s", (appointment_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Appointment accepted successfully!", "success")
    return redirect(url_for('doctor_appointments'))
@app.route('/doctor/appointments/reject/<int:appointment_id>')
def reject_appointment(appointment_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE appointments SET status = 'Rejected' WHERE id = %s", (appointment_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Appointment rejected.", "info")
    return redirect(url_for('doctor_appointments'))

@app.route('/doctor/appointments', methods=['GET', 'POST'])
def doctor_appointments():
    if 'user_id' not in session or session.get('role') != 'doctor':
        flash("Access denied!", "danger")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        appointment_id = request.form.get('appointment_id')
        action = request.form.get('action')
        if appointment_id and action:
            if action == 'accept':
                cursor.execute("UPDATE appointments SET status = 'Accepted' WHERE id = %s", (appointment_id,))
            elif action == 'reject':
                cursor.execute("UPDATE appointments SET status = 'Rejected' WHERE id = %s", (appointment_id,))
            conn.commit()

    cursor.execute("""
        SELECT * FROM appointments
        WHERE doctor_id = %s
        ORDER BY appointment_date, appointment_time
    """, (session['user_id'],))
    appointments = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('doctor_appointments.html', appointments=appointments)



    # Show form
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name,photo_path FROM doctors WHERE is_verified = 1 AND status = 'active'")
    doctors = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('appointment.html', doctors=doctors)
@app.route('/doctor/profile', methods=['GET', 'POST'])
def complete_doctor_profile():
    if 'user_id' not in session or session.get('role') != 'doctor':
        flash("Access denied!", "danger")
        return redirect(url_for('login'))

    doctor_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        experience = request.form.get('experience')
        specialization = request.form.get('specialization')
        availability_days = request.form.get('availability_days')
        availability_time = request.form.get('availability_time')
        hospital_name = request.form.get('hospital_name')

        cursor.execute("""
            UPDATE doctors SET 
            experience = %s, 
            specialization = %s,
            availability_days = %s,
            availability_time = %s,
            hospital_name = %s
            WHERE id = %s
        """, (experience, specialization, availability_days, availability_time, hospital_name, doctor_id))
        conn.commit()
        flash("Profile updated successfully!", "success")
        session.clear()
        flash("Profile completed. Admin will verify your account shortly.", "info")
        return redirect(url_for('login'))

        return redirect(url_for('login'))

    cursor.execute("SELECT * FROM doctors WHERE id = %s", (doctor_id,))
    doctor = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('complete_doctor_profile.html', doctor=doctor)


@app.route('/guide')
def guide():
    return render_template('guide.html')

@app.route('/ebook')
def ebook():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT title, image_path, content, description FROM ebooks ORDER BY id ASC")
    stories = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('ebook.html', stories=stories)


@app.route('/in')
def landing_page():
    return render_template('in.html')

@app.route('/exercise')
def exercise_page():
    return render_template('exercise.html')

@app.route('/music')
def music_page():
    return render_template('music.html')


@app.route('/store')
def ecommerce():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM products")
        all_products = cursor.fetchall()

    categorized_products = {}
    for product in all_products:
        category = product['category']
        if category not in categorized_products:
            categorized_products[category] = []
        categorized_products[category].append(product)

    view_all_category = request.args.get('view_all')
    cart_count = sum(item.get('quantity',1) for item in session.get('cart', []))

    return render_template(
        'ecommerce.html',
        categorized_products=categorized_products,
        all_products=all_products,
        view_all_category=view_all_category,
        cart_count=cart_count
    )



@app.route('/add_to_wishlist', methods=['POST'])
def add_to_wishlist():
    product_name = request.form['name']
    product = get_product_by_name(product_name)
    if product:
        session.setdefault('wishlist', []).append(product)
    return redirect(url_for('ecommerce'))

@app.route('/buy_now', methods=['POST'])
def buy_now():
    product_name = request.form['name']
    product = get_product_by_name(product_name)
    if product:
        session['cart'] = [product]  # Overwrite with single product
    return redirect(url_for('checkout'))

def get_product_by_name(name):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM products WHERE name = %s", (name,))
        result = cursor.fetchone()
    conn.close()
    return result

@app.route('/cart')
def cart():
    cart_items = session.get('cart', [])
    for item in cart_items:
        if 'quantity' not in item:
            item['quantity'] = 1
    total = sum(float(item['price']) * item['quantity'] for item in cart_items)
    session['cart'] = cart_items  # update session
    return render_template('cart.html', cart_items=cart_items, total=round(total, 2))

from decimal import Decimal

def to_serializable(product):
    # Convert Decimal and any non-serializable types
    return {
        'id': product['id'],
        'name': product['name'],
        'price': float(product['price']) if isinstance(product['price'], Decimal) else product['price'],
        'image': product['image'],
        'category': product['category'],
        'sizes': product.get('sizes', ''),
        'material': product.get('material', ''),
        'quantity': 1
    }

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product_name = request.form['name']
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM products WHERE name = %s", (product_name,))
        db_product = cursor.fetchone()
    conn.close()

    if not db_product:
        return jsonify(success=False)

    cart = session.get('cart', [])
    for item in cart:
        if item['name'] == product_name:
            item['quantity'] = item.get('quantity', 1) + 1
            break
    else:
        cart.append(to_serializable(db_product))

    session['cart'] = cart
    session.modified = True  # ✅ ensure Flask saves session
    return jsonify(success=True, cart_count=sum(i['quantity'] for i in cart))

@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    name = request.form.get('name')
    cart = session.get('cart', [])

    updated_cart = []
    for item in cart:
        if item['name'] == name:
            if item.get('quantity', 1) > 1:
                item['quantity'] -= 1
                updated_cart.append(item)
            # else skip the item to remove it entirely
        else:
            updated_cart.append(item)

    session['cart'] = updated_cart
    return redirect(url_for('cart'))



@app.route('/wishlist')
def wishlist():
    return render_template('wishlist.html', wishlist_items=session.get('wishlist', []))

@app.route('/checkout')
def checkout():
    cart_items = session.get('cart', [])
    total = sum(float(item['price']) for item in cart_items)
    return render_template('checkout.html', cart_items=cart_items, total=round(total, 2))
@app.route('/payment', methods=['POST'])
def payment():
    cart_items = session.get('cart', [])
    total = sum(float(item['price']) * item.get('quantity', 1) for item in cart_items)
    return render_template('payment.html', cart_items=cart_items, total=round(total, 2))

@app.route('/confirm_order', methods=['POST'])
def confirm_order():
    name = request.form['fullname']
    email = request.form['email']
    phone = request.form['phone']
    address = request.form['address']
    method = request.form['payment_method']

    cart_items = session.get('cart', [])
    total = sum(float(item['price']) * item.get('quantity', 1) for item in cart_items)

    # Insert order into the orders table
    if 'user_id' in session and cart_items:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO orders (user_id, order_date, status, total_amount, shipping_address, payment_method) VALUES (%s, NOW(), %s, %s, %s, %s)",
            (session['user_id'], 'Placed', total, address, method)
        )
        order_id = cursor.lastrowid
        # Optionally, insert order items into an order_items table here
        conn.commit()
        cursor.close()
        conn.close()

    # Clear cart
    session.pop('cart', None)

    return render_template('order_success.html', name=name, method=method)

@app.route('/my_account')
def my_account():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('my_account.html', user=user)

@app.route('/orders')
def orders():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE user_id = %s ORDER BY order_date DESC", (session['user_id'],))
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('orders.html', orders=orders)

@app.route('/settings', methods=['GET', 'POST'])
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    # Handle POST for updating user info if needed
    cursor.close()
    conn.close()
    return render_template('settings.html', user=user)

@app.route('/addresses')
def addresses():
    # Your addresses view logic
    return render_template('addresses.html')
@app.route('/order/<int:order_id>')
def order_details(order_id):
    # Fetch order details from DB if needed
    return f"Order details for order #{order_id}"
import json

@app.route('/moms-circle')
def moms_circle():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, content, rating FROM moms_stories ORDER BY submitted_at DESC")
    stories = cursor.fetchall()
    cursor.close()
    conn.close()

    # Convert Python data to JSON string
    stories_json = json.dumps(stories)
    return render_template('moms_circle.html', stories_json=stories_json)

@app.route('/add_story', methods=['POST'])
def add_story():
    name = request.form.get('name')
    content = request.form.get('content')
    rating = int(request.form.get('rating', 0))

    if name and content and rating:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO moms_stories (name, content, rating) VALUES (%s, %s, %s)",
            (name, content, rating)
        )
        conn.commit()
        cursor.close()
        conn.close()

    return redirect(url_for('moms_circle'))


@app.route('/delete_story/<int:index>', methods=['POST'])
def delete_story(index):
    if 0 <= index < len(stories):
        stories.pop(index)
    return redirect('/moms-circle')

@app.route('/tracker')
def tracker():
    return render_template('tracker.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')
    
# ✅ Test Route
@app.route('/test')
def test():
    return "Flask is working!"

# 🚀 Run the App
if __name__ == '__main__':
    app.run(debug=True)


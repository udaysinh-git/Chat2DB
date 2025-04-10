from flask import Blueprint, render_template, request, redirect, session, url_for

login_bp = Blueprint('login', __name__)

@login_bp.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        root_password = request.form.get('root_password')
        # For demo, assume any non-empty password is accepted.
        if root_password:
            session['root_password'] = root_password
            return redirect(url_for('dashboard.dashboard'))
    return render_template('login.html')

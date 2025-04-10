from flask import Blueprint, render_template, redirect, session, url_for

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
def dashboard():
    if 'root_password' not in session:
        return redirect(url_for('login.login'))
    return render_template('dashboard.html')

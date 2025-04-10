from flask import Blueprint, render_template, redirect, session, url_for

current_chat_bp = Blueprint('current_chat', __name__)

@current_chat_bp.route('/current_chat')
def current_chat():
    if 'root_password' not in session:
        return redirect(url_for('login.login'))
    return render_template('index.html')

from flask import Flask
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Register blueprints
from routes.login import login_bp
from routes.dashboard import dashboard_bp
from routes.view_databases import view_databases_bp
from routes.create_database import create_database_bp
from routes.schema import schema_bp
from routes.current_chat import current_chat_bp
from routes.main_routes import main_bp  # added import

app.register_blueprint(login_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(view_databases_bp)
app.register_blueprint(create_database_bp)
app.register_blueprint(schema_bp)
app.register_blueprint(current_chat_bp)
app.register_blueprint(main_bp)  # register main routes

if __name__ == '__main__':
    app.run(debug=True)

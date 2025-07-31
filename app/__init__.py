import os
from flask import Flask
from .routes import main


def create_app():
    # Create Flask application instance
    app = Flask(__name__, static_folder='../static')

    # Configuration
    app.config['SECRET_KEY'] = 'demo'

    # The path to upload files
    app.config['UPLOAD_FOLDER'] = 'uploads'

    # Maximum size
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

    # Allowed file extensions
    app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'xlsx', 'xls', 'docx'}

    # Create upload directories if they don't exist
    upload_dirs = ['uploads/pdf', 'uploads/excel', 'uploads/docx', 'data']
    for directory in upload_dirs:
        if not os.path.exists(directory):
            os.makedirs(directory)

    app.register_blueprint(main)

    return app
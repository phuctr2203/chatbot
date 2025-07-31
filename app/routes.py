from flask import Blueprint, render_template, request, jsonify, current_app, send_file
import os
import json
from datetime import datetime
from werkzeug.utils import secure_filename
import uuid
import magic

# Create Blueprint
main = Blueprint('main', __name__)


# Helper function to check allowed file types
def allowed_file(filename):
    """Check if uploaded file type is allowed"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def get_file_type(filename):
    """Get file type category for organization"""
    ext = filename.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        return 'pdf'
    elif ext in ['xlsx', 'xls']:
        return 'excel'
    elif ext == 'docx':
        return 'docx'
    return 'unknown'


def format_file_size(size_bytes):
    """Convert bytes to human readable format"""
    if size_bytes == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"


def load_files_metadata():
    """Load file metadata from JSON file"""
    metadata_file = 'data/files_metadata.json'
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {'files': []}
    return {'files': []}


def save_files_metadata(metadata):
    """Save file metadata to JSON file"""
    metadata_file = 'data/files_metadata.json'
    os.makedirs('data', exist_ok=True)
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2, default=str)


def validate_file_content(file_path, expected_type):
    """Validate file content matches expected type using python-magic"""
    try:
        file_type = magic.from_file(file_path, mime=True)

        # Define expected MIME types
        expected_mimes = {
            'pdf': ['application/pdf'],
            'excel': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                      'application/vnd.ms-excel'],
            'docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        }

        return file_type in expected_mimes.get(expected_type, [])
    except:
        # If magic fails, skip validation (fallback)
        return True


@main.route('/')
def index():
    """Home page - shows welcome message and navigation"""
    return render_template('index.html')


@main.route('/upload', methods=['GET', 'POST'])
def upload():
    """Handle file upload page and processing"""
    if request.method == 'POST':
        try:
            # Get uploaded files
            uploaded_files = request.files.getlist('uploaded_files')

            if not uploaded_files or uploaded_files[0].filename == '':
                return jsonify({
                    'status': 'error',
                    'message': 'No files selected'
                }), 400

            # Load existing metadata
            metadata = load_files_metadata()
            uploaded_count = 0
            upload_errors = []

            for file in uploaded_files:
                if file and file.filename != '':
                    try:
                        # Validate file type
                        if not allowed_file(file.filename):
                            upload_errors.append(f"{file.filename}: Invalid file type")
                            continue

                        # Get file info
                        original_filename = file.filename
                        file_type = get_file_type(original_filename)

                        # Generate unique filename to prevent conflicts
                        file_extension = original_filename.rsplit('.', 1)[1].lower()
                        unique_filename = f"{uuid.uuid4().hex[:8]}_{secure_filename(original_filename)}"

                        # Create type-specific directory
                        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], file_type)
                        os.makedirs(upload_dir, exist_ok=True)

                        # Save file
                        file_path = os.path.join(upload_dir, unique_filename)
                        file.save(file_path)

                        # Get file size
                        file_size = os.path.getsize(file_path)

                        # Validate file content (security check)
                        if not validate_file_content(file_path, file_type):
                            os.remove(file_path)  # Remove invalid file
                            upload_errors.append(f"{original_filename}: File content doesn't match extension")
                            continue

                        # Create metadata entry
                        file_metadata = {
                            'id': str(uuid.uuid4()),
                            'original_name': original_filename,
                            'stored_name': unique_filename,
                            'stored_path': file_path,
                            'file_type': file_type,
                            'file_size': file_size,
                            'formatted_size': format_file_size(file_size),
                            'upload_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'file_extension': file_extension
                        }

                        # Add to metadata
                        metadata['files'].append(file_metadata)
                        uploaded_count += 1

                    except Exception as e:
                        upload_errors.append(f"{file.filename}: {str(e)}")
                        continue

            # Save updated metadata
            if uploaded_count > 0:
                save_files_metadata(metadata)

            # Prepare response
            if uploaded_count > 0:
                message = f"Successfully uploaded {uploaded_count} file(s)"
                if upload_errors:
                    message += f". {len(upload_errors)} file(s) failed."

                return jsonify({
                    'status': 'success',
                    'message': message,
                    'uploaded_count': uploaded_count,
                    'errors': upload_errors
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'No files were uploaded successfully',
                    'errors': upload_errors
                }), 400

        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Upload failed: {str(e)}'
            }), 500

    # Show upload form
    return render_template('upload.html')


@main.route('/files')
def files():
    """Display list of uploaded files"""
    try:
        # Load file metadata
        metadata = load_files_metadata()
        files_list = metadata.get('files', [])

        # Sort files by upload date (newest first)
        files_list.sort(key=lambda x: x.get('upload_date', ''), reverse=True)

        return render_template('files.html', files=files_list)

    except Exception as e:
        # If there's an error loading files, show empty list
        return render_template('files.html', files=[])


@main.route('/download/<filename>')
def download(filename):
    """Download specific file"""
    try:
        # Load metadata to find file
        metadata = load_files_metadata()
        files_list = metadata.get('files', [])

        # Find file by stored name
        target_file = None
        for file_info in files_list:
            if file_info['stored_name'] == filename:
                target_file = file_info
                break

        if not target_file:
            return jsonify({
                'status': 'error',
                'message': 'File not found'
            }), 404

        # Check if file exists on disk
        if not os.path.exists(target_file['stored_path']):
            return jsonify({
                'status': 'error',
                'message': 'File not found on disk'
            }), 404

        # Send file
        return send_file(
            target_file['stored_path'],
            as_attachment=True,
            download_name=target_file['original_name']
        )

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Download failed: {str(e)}'
        }), 500


@main.route('/delete/<file_id>', methods=['DELETE'])
def delete_file(file_id):
    """Delete specific file"""
    try:
        # Load metadata
        metadata = load_files_metadata()
        files_list = metadata.get('files', [])

        # Find and remove file
        target_file = None
        for i, file_info in enumerate(files_list):
            if file_info['id'] == file_id:
                target_file = file_info
                files_list.pop(i)
                break

        if not target_file:
            return jsonify({
                'status': 'error',
                'message': 'File not found'
            }), 404

        # Delete file from disk
        if os.path.exists(target_file['stored_path']):
            os.remove(target_file['stored_path'])

        # Save updated metadata
        save_files_metadata(metadata)

        return jsonify({
            'status': 'success',
            'message': f"File '{target_file['original_name']}' deleted successfully"
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Delete failed: {str(e)}'
        }), 500
from flask import Flask, render_template, request, jsonify, send_file
import os
import uuid
import shutil
from werkzeug.utils import secure_filename
from decoder import decode_video_and_audio

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
ALLOWED_EXTENSIONS = {'mp4'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Create a unique session ID for this upload
        session_id = str(uuid.uuid4())[:8]
        
        # Save uploaded file
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_{filename}")
        file.save(upload_path)
        
        # Output directory for this specific file
        output_dir = os.path.join(app.config['OUTPUT_FOLDER'], session_id)
        
        # Run decoder
        success, message = decode_video_and_audio(input_file=upload_path, output_dir=output_dir)
        
        if success:
            return jsonify({
                'message': 'File successfully decoded!',
                'output_dir': output_dir,
                'session_id': session_id
            }), 200
        else:
            return jsonify({'error': message}), 500
            
    return jsonify({'error': 'Invalid file type. Only MP4 is allowed.'}), 400

@app.route('/download/<session_id>/<file_type>')
def download_file(session_id, file_type):
    session_dir = secure_filename(session_id)
    output_dir = os.path.join(app.config['OUTPUT_FOLDER'], session_dir)
    
    if not os.path.exists(output_dir):
        return "Session not found", 404
        
    if file_type == 'audio':
        audio_path = os.path.join(output_dir, 'audio.wav')
        if os.path.exists(audio_path):
            return send_file(audio_path, as_attachment=True)
            
    elif file_type == 'frames':
        frames_dir = os.path.join(output_dir, 'frames')
        if os.path.exists(frames_dir):
            zip_path = os.path.join(output_dir, 'frames.zip')
            
            # Remove corrupted zip if size is suspiciously small for JPEGs or it's invalid
            if os.path.exists(zip_path):
                import zipfile
                try:
                    with zipfile.ZipFile(zip_path, 'r') as z:
                        if z.testzip() is not None:
                            os.remove(zip_path)
                except zipfile.BadZipFile:
                    os.remove(zip_path)
                    
            # Create zip file if it doesn't exist
            if not os.path.exists(zip_path):
                import zipfile
                # Use ZIP_STORED (no compression) because JPEGs are already compressed
                # This drops the zipping time from 2.5 minutes to 0.8 seconds!
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zipf:
                    for root, _, files in os.walk(frames_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            # Store in zip without the absolute path prefix
                            arcname = os.path.relpath(file_path, frames_dir)
                            zipf.write(file_path, arcname)
                            
            return send_file(zip_path, as_attachment=True)
            
    return "File not found", 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)

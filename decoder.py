import cv2
import os
import subprocess
import json
from pathlib import Path
import imageio_ffmpeg

def decode_video_and_audio(input_file="input.mp4", output_dir="output", extraction_type="both", status_file=None):
    """
    Decodes video into frames and extracts audio into a WAV file.
    Saves timestamps for both to allow synchronization.
    extraction_type can be "audio", "frames", or "both".
    """

    def update_status(state, msg, error=None):
        if status_file:
            try:
                data = {"status": state, "message": msg}
                if error:
                    data["error"] = error
                with open(status_file, "w") as sf:
                    json.dump(data, sf)
            except Exception as e:
                print(f"Failed to write status: {e}")

    if not os.path.exists(input_file):
        msg = f"Error: {input_file} not found. Please provide a valid MP4 file."
        print(msg)
        update_status("error", "File not found", msg)
        return False, msg

    # Create output directories
    frames_dir = Path(output_dir) / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    
    audio_path = Path(output_dir) / "audio.wav"
    metadata_path = Path(output_dir) / "metadata.json"
    
    metadata = {
        "frames": [],
        "audio": {}
    }

    if extraction_type in ["audio", "both"]:
        metadata["audio"] = {
            "file": str(audio_path),
            "sample_rate": 16000,
            "channels": 1
        }

    print(f"--- Starting Decoding Process for {input_file} ---")
    update_status("processing", "Starting decoding process...")

    # 1. Video Decoder (OpenCV)
    if extraction_type in ["frames", "both"]:
        print("\n[1/2] Decoding Video Streams -> Frames...")
        video = cv2.VideoCapture(input_file)
        
        # Get FPS to calculate exact time or we can use CAP_PROP_POS_MSEC
        fps = video.get(cv2.CAP_PROP_FPS)
        print(f"Video FPS: {fps}")

        frame_id = 0
        while True:
            ok, frame = video.read()
            if not ok:
                break

            # Get timestamp in milliseconds and convert to seconds
            timestamp_ms = video.get(cv2.CAP_PROP_POS_MSEC)
            timestamp_sec = timestamp_ms / 1000.0

            frame_filename = f"frame_{frame_id:06d}.jpg"
            frame_filepath = frames_dir / frame_filename
            
            # Save frame
            cv2.imwrite(str(frame_filepath), frame)
            
            # Save metadata
            metadata["frames"].append({
                "frame_id": frame_id,
                "filename": frame_filename,
                "timestamp_sec": round(timestamp_sec, 3)
            })

            if frame_id % 100 == 0:
                print(f"Extracted {frame_id} frames...", end="\r")
                update_status("processing", f"Extracted {frame_id} frames...")

            frame_id += 1

        video.release()
        print(f"\nTotal video frames extracted: {frame_id}")

    # 2. Audio Decoder (FFmpeg)
    if extraction_type in ["audio", "both"]:
        print("\n[2/2] Decoding Audio Stream -> PCM WAV...")
        update_status("processing", "Extracting audio...")
    
    # ffmpeg -i input.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le audio.wav -y
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_cmd = [
        ffmpeg_exe, 
        "-i", input_file, 
        "-vn",                      # No video
        "-ac", "1",                 # Mono
        "-ar", "16000",             # 16 kHz sample rate
        "-c:a", "pcm_s16le",        # PCM 16-bit little-endian
        "-y",                       # Overwrite if exists
        str(audio_path)
    ]
    
    if extraction_type in ["audio", "both"]:
        try:
            subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"Audio extracted successfully to {audio_path}")
        except subprocess.CalledProcessError as e:
            msg = f"Error extracting audio: {e}. Make sure FFmpeg is installed."
            print(msg)
            update_status("error", "Error extracting audio", msg)
            return False, msg
        except FileNotFoundError:
            msg = "Error: FFmpeg is not installed or not in your system's PATH. Please install FFmpeg to extract audio."
            print(msg)
            update_status("error", "FFmpeg not found", msg)
            return False, msg

    # 3. Save Metadata (Timestamps)
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=4)
        
    print(f"\n--- Decoding Complete ---")
    print(f"All data and timestamps saved in: {output_dir}")
    print(f"Check {metadata_path} for frame and audio timestamps mapping.")
    
    update_status("completed", "File successfully decoded!")
    return True, f"Successfully processed. Saved to {output_dir}"


if __name__ == "__main__":
    # Ensure you have a sample MP4 file named "input.mp4" in the directory
    # or pass the filename to the function.
    decode_video_and_audio("input.mp4", "output")

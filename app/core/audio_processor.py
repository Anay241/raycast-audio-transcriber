#app/core/audio_processor.py

from typing import Optional, Set, List
import os
import time
import wave
from datetime import datetime
from threading import Thread
import logging
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import pyperclip
from pynput import keyboard
import rumps
import atexit
import gc
import multiprocessing
import multiprocessing.resource_tracker
import signal
import sys
from pathlib import Path

from app.models.model_manager import ModelManager
from app.core.text_processor import process_text
from app.common.notifier import AudioNotifier

# Set up logging
logger = logging.getLogger(__name__)

class AudioProcessor:
    """Handle audio recording and processing."""
    
    def __init__(self, app):
        """Initialize the audio processing system."""
        logger.debug("Initializing AudioProcessor")
        self.app = app
        
        # Reverting to original working audio settings
        self.sample_rate: int = 44100
        self.channels: int = 1
        self.dtype = np.int16
        self.blocksize: int = 8192
        
        # Recording state
        self.is_recording: bool = False
        self.ready_to_record: bool = True
        self.frames: List[np.ndarray] = []
        
        # Model management
        self.model_manager = ModelManager()
        
        # Thread tracking
        self.transcription_thread = None
        
        # Setup keyboard listener
        self.keys_pressed: Set = set()
        self.listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release)
        self.listener.start()
        logger.debug("Keyboard listener started")
        
        # Register cleanup function to be called at exit
        atexit.register(self.cleanup)
        logger.debug("Registered cleanup function with atexit")

    def ensure_model_loaded(self) -> WhisperModel:
        """Get a loaded model for transcription."""
        try:
            return self.model_manager.get_model()
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            self.icon_state = "❌"
            AudioNotifier.play_sound('error')
            raise

    def transcribe_audio(self, audio_data: np.ndarray) -> Optional[str]:
        """
        Transcribe audio using Whisper.
        
        Args:
            audio_data: The audio data to transcribe
            
        Returns:
            Transcription text or None if transcription failed
        """
        try:
            logger.info("Starting transcription")
            self.icon_state = "💭"  # Thinking emoji
            
            # Get model for transcription
            model = self.ensure_model_loaded()
            
            # Save temporary audio file
            temp_file = "temp_recording.wav"
            with wave.open(temp_file, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data.tobytes())
            
            # Transcribe using Faster Whisper
            try:
                segments, _ = model.transcribe(
                    temp_file,
                    beam_size=5,
                    word_timestamps=True,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500)
                )
                
                # Process segments
                text_segments = []
                for segment in segments:
                    # Clean up the segment text
                    segment_text = segment.text.strip()
                    if segment_text:
                        text_segments.append(segment_text)
                
                # Join and process the text
                if text_segments:
                    text = ' '.join(text_segments)
                    processed_text = process_text(text)
                    logger.info(f"Transcription successful: {processed_text}")
                    
                    # Check if we should unload the model
                    self.model_manager.check_timeout()
                    
                    return processed_text
                else:
                    logger.warning("No speech detected in audio")
                    return None
                    
            finally:
                # Ensure temporary file is always cleaned up
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    
        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            return None
        finally:
            self.icon_state = "🎤"  # Reset icon

    def on_press(self, key: keyboard.Key) -> None:
        """Handle key press events."""
        try:
            # Add the key to the set of pressed keys
            self.keys_pressed.add(key)
            
            # Check for Command+Shift+9 combination
            if (keyboard.Key.cmd in self.keys_pressed and 
                keyboard.Key.shift in self.keys_pressed and 
                hasattr(key, 'char') and key.char == '9'):
                # Toggle recording
                self.toggle_recording()
        except Exception as e:
            logger.error(f"Error in key press handler: {e}")

    def on_release(self, key: keyboard.Key) -> None:
        """Handle key release events."""
        try:
            # Remove the key from the set of pressed keys if it's there
            self.keys_pressed.discard(key)
        except Exception as e:
            logger.error(f"Error in key release handler: {e}")

    def toggle_recording(self) -> None:
        """Toggle recording state."""
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self) -> None:
        """Start recording audio."""
        if self.is_recording or not self.ready_to_record:
            logger.warning("Cannot start recording: already recording or not ready")
            return
            
        try:
            logger.info("Starting recording")
            self.ready_to_record = False  # Prevent multiple starts
            
            # Clear previous frames and ensure we're starting fresh
            if hasattr(self, 'frames'):
                self.frames.clear()
            self.frames = []
            
            # Close any existing stream before creating a new one
            self._close_stream()
            
            self.is_recording = True
            
            # Update app state
            self.app.set_state('recording')
            
            # Start recording stream
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                blocksize=self.blocksize,
                callback=self.callback
            )
            self.stream.start()
            logger.info("Audio stream started successfully")
            
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            self.is_recording = False
            self._close_stream()  # Ensure stream is closed on error
            AudioNotifier.play_sound('error')
        finally:
            self.ready_to_record = True  # Ready for next recording

    def _close_stream(self) -> None:
        """Safely close the audio stream if it exists."""
        try:
            if hasattr(self, 'stream') and self.stream:
                if hasattr(self.stream, 'active') and self.stream.active:
                    logger.debug("Stopping active audio stream")
                    self.stream.stop()
                
                logger.debug("Closing audio stream")
                self.stream.close()
                self.stream = None
                logger.debug("Audio stream closed successfully")
        except Exception as e:
            logger.error(f"Error closing audio stream: {e}")

    def callback(self, indata: np.ndarray, frames: int, time_info: dict, status: sd.CallbackFlags) -> None:
        """Callback for audio stream to collect frames."""
        if status:
            logger.warning(f"Audio callback status: {status}")
        self.frames.append(indata.copy())

    def stop_recording(self) -> None:
        """Stop recording and process the audio."""
        if not self.is_recording:
            logger.warning("Cannot stop recording: not currently recording")
            return
            
        try:
            logger.info("Stopping recording")
            self.is_recording = False
            
            # Stop the audio stream
            self._close_stream()
            
            # Update app state
            self.app.set_state('processing')
            
            # Play sound notification
            AudioNotifier.play_sound('stop')
            
            # Check if we have any frames
            if not self.frames:
                logger.warning("No audio frames recorded")
                self.app.set_state('idle')
                return
                
            # Save audio to temporary file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_filename = f"recording_{timestamp}.wav"
            
            # Process in a separate thread to keep UI responsive
            def transcribe_thread():
                try:
                    # Save audio to file
                    audio_data = self.save_audio(temp_filename)
                    if audio_data is None:
                        logger.error("Failed to save audio")
                        self.app.set_state('idle')
                        return
                        
                    # Transcribe audio
                    transcription = self.transcribe_audio(audio_data)
                    if transcription:
                        # Process text (format, copy to clipboard)
                        processed_text = process_text(transcription)
                        pyperclip.copy(processed_text)
                        
                        # Play success sound
                        AudioNotifier.play_sound('success')
                        
                        # Update app state
                        self.app.set_state('completed')
                        logger.info("Transcription completed and copied to clipboard")
                    else:
                        logger.error("Transcription failed")
                        self.app.set_state('idle')
                        AudioNotifier.play_sound('error')
                except Exception as e:
                    logger.error(f"Error in transcription thread: {e}")
                    self.app.set_state('idle')
                    AudioNotifier.play_sound('error')
                finally:
                    # Clean up temporary file
                    try:
                        if os.path.exists(temp_filename):
                            os.remove(temp_filename)
                            logger.debug(f"Removed temporary file: {temp_filename}")
                    except Exception as e:
                        logger.error(f"Error removing temporary file: {e}")
            
            # Start transcription in a separate thread
            self.transcription_thread = Thread(target=transcribe_thread)
            self.transcription_thread.daemon = True  # Allow app to exit even if thread is running
            self.transcription_thread.start()
            
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            self.app.set_state('idle')
            AudioNotifier.play_sound('error')

    def save_audio(self, filename: str) -> Optional[np.ndarray]:
        """
        Save recorded audio to a WAV file.
        
        Args:
            filename: The filename to save the audio to
            
        Returns:
            The audio data as a numpy array, or None if saving failed
        """
        if not self.frames:
            logger.warning("No audio frames to save")
            return None
            
        # Create a full path for the file
        try:
            filepath = Path(filename)
            
            # Ensure parent directory exists
            if filepath.parent != Path('.'):
                filepath.parent.mkdir(parents=True, exist_ok=True)
                
            logger.debug(f"Saving audio to {filepath.absolute()}")
        except Exception as e:
            logger.error(f"Error preparing file path: {e}")
            return None
            
        # Combine all frames
        try:
            audio_data = np.concatenate(self.frames, axis=0)
            logger.debug(f"Combined {len(self.frames)} frames, total samples: {len(audio_data)}")
        except Exception as e:
            logger.error(f"Error combining audio frames: {e}")
            return None
            
        # Save to WAV file
        wf = None
        try:
            wf = wave.open(str(filepath), 'wb')
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit audio
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data.tobytes())
            
            logger.info(f"Audio saved to {filepath} ({os.path.getsize(filepath) / 1024:.1f} KB)")
            return audio_data
        except Exception as e:
            logger.error(f"Error saving audio: {e}")
            return None
        finally:
            # Ensure wave file is closed
            if wf:
                try:
                    wf.close()
                except Exception as e:
                    logger.error(f"Error closing wave file: {e}")

    def cleanup(self):
        """Clean up resources when the application exits."""
        logger.info("Cleaning up AudioProcessor resources")
        
        # Track cleanup status for each resource type
        cleanup_status = {
            "keyboard_listener": False,
            "audio_stream": False,
            "transcription_thread": False,
            "model": False,
            "temp_files": False
        }
        
        # 1. Stop keyboard listener if active
        try:
            if hasattr(self, 'listener') and self.listener:
                logger.info("Stopping keyboard listener")
                self.listener.stop()
                cleanup_status["keyboard_listener"] = True
        except Exception as e:
            logger.error(f"Error stopping keyboard listener: {e}")
        
        # 2. Stop audio stream if active
        try:
            if hasattr(self, 'stream') and self.stream:
                if hasattr(self.stream, 'active') and self.stream.active:
                    logger.info("Stopping active audio stream")
                    self.stream.stop()
                
                logger.info("Closing audio stream")
                self.stream.close()
                self.stream = None  # Remove reference to allow garbage collection
                cleanup_status["audio_stream"] = True
        except Exception as e:
            logger.error(f"Error stopping audio stream: {e}")
        
        # 3. Stop transcription thread if active
        try:
            if hasattr(self, 'transcription_thread') and self.transcription_thread and self.transcription_thread.is_alive():
                logger.info("Waiting for transcription thread to complete")
                # Give the thread a chance to complete naturally
                self.transcription_thread.join(timeout=2.0)
                
                # Check if thread is still alive after timeout
                if self.transcription_thread.is_alive():
                    logger.warning("Transcription thread did not complete within timeout")
                else:
                    logger.info("Transcription thread completed successfully")
                    cleanup_status["transcription_thread"] = True
            else:
                cleanup_status["transcription_thread"] = True  # No thread to clean up
        except Exception as e:
            logger.error(f"Error handling transcription thread: {e}")
        
        # 4. Unload model if loaded
        try:
            if hasattr(self, 'model_manager') and self.model_manager:
                logger.info("Unloading Whisper model")
                self.model_manager.unload_model()
                
                # Verify model was unloaded
                if hasattr(self.model_manager, 'model') and self.model_manager.model is None:
                    cleanup_status["model"] = True
                    logger.info("Model unloaded successfully")
                else:
                    logger.warning("Model may not have been fully unloaded")
        except Exception as e:
            logger.error(f"Error unloading model: {e}")
        
        # 5. Clean up temporary audio files
        try:
            logger.info("Cleaning up temporary audio files")
            import glob
            
            # Find all temporary recording files with absolute paths
            temp_patterns = ["temp_recording*.wav", "recording_*.wav"]
            temp_files = []
            
            for pattern in temp_patterns:
                # Search in current directory
                temp_files.extend(glob.glob(pattern))
                
                # Also search in the project directory if different
                project_dir = Path(__file__).resolve().parent.parent.parent
                if project_dir != Path.cwd():
                    temp_files.extend(glob.glob(str(project_dir / pattern)))
            
            # Remove duplicates
            temp_files = list(set(temp_files))
            
            if temp_files:
                logger.info(f"Found {len(temp_files)} temporary audio files to clean up")
                
                for file_path in temp_files:
                    try:
                        Path(file_path).unlink()
                        logger.info(f"Deleted temporary audio file: {file_path}")
                    except Exception as e:
                        logger.error(f"Error deleting temporary audio file {file_path}: {e}")
                
                cleanup_status["temp_files"] = True
            else:
                logger.info("No temporary audio files found to clean up")
                cleanup_status["temp_files"] = True
        except Exception as e:
            logger.error(f"Error during audio file cleanup: {e}")
        
        # 6. Clear any remaining audio frames to free memory
        try:
            if hasattr(self, 'frames') and self.frames:
                logger.info(f"Clearing {len(self.frames)} audio frames from memory")
                self.frames.clear()
        except Exception as e:
            logger.error(f"Error clearing audio frames: {e}")
        
        # 7. Force garbage collection
        try:
            logger.info("Forcing garbage collection")
            gc.collect()
        except Exception as e:
            logger.error(f"Error during garbage collection: {e}")
        
        # Log cleanup summary
        successful = sum(1 for status in cleanup_status.values() if status)
        logger.info(f"AudioProcessor cleanup completed: {successful}/{len(cleanup_status)} resources cleaned successfully")
        
        # Log details of any failed cleanups
        failed_resources = [resource for resource, status in cleanup_status.items() if not status]
        if failed_resources:
            logger.warning(f"Failed to clean up these resources: {', '.join(failed_resources)}")
        
        return successful == len(cleanup_status)  # Return True if all cleanups were successful 
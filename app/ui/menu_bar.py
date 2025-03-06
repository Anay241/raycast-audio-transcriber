#app/ui/menu_bar.py

import logging
import rumps # type: ignore
import time
import atexit
import signal
import sys
import gc
import multiprocessing
import multiprocessing.resource_tracker
import os
from app.core.audio_processor import AudioProcessor
from app.common.notifier import AudioNotifier
from utils.logger import cleanup_logs
from threading import Thread

# Set up logging
logger = logging.getLogger(__name__)

# App states and their icons
APP_STATES = {
    'idle': '🎤',
    'recording': '🔴',
    'processing': '⏳',
    'completed': '✅'
}

class AudioTranscriberApp(rumps.App):
    def __init__(self):
        logger.debug("Initializing AudioTranscriberApp")
        super().__init__(
            "Audio Transcriber",     # App name
            title=APP_STATES['idle'],  # Menu bar icon
            quit_button=None        # Disable default quit button to prevent accidental quits
        )
        
        # Initialize state
        self.current_state = 'idle'
        self.last_state_change = time.time()
        
        # Initialize audio processor
        self.processor = AudioProcessor(self)
        
        # Menu items with separator to ensure clickability
        self.menu = [
            rumps.MenuItem("Start/Stop Recording (⌘+⇧+9)", callback=self.toggle_recording),
            None,  # Separator
            rumps.MenuItem("Quit", callback=self.quit_app)
        ]
        
        # Set up periodic icon refresh
        rumps.Timer(self.refresh_icon, 0.5).start()  # Refresh icon every half second
        
        # Register cleanup for exit
        atexit.register(self.stop)
        
        # Set up signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        logger.info("Audio Transcriber running in background")
        logger.info("Use Command+Shift+9 from any application to start/stop recording")
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        logger.info("Setting up signal handlers")
        
        def handle_signal(sig, frame):
            """Handle termination signals by cleaning up and exiting."""
            signal_name = signal.Signals(sig).name
            logger.info(f"Received {signal_name} signal, shutting down gracefully")
            
            # Clean up resources
            self.stop()
            
            # Force exit after cleanup
            logger.info("Exiting application")
            sys.exit(0)
        
        # Register signal handlers for common termination signals
        signal.signal(signal.SIGINT, handle_signal)   # Ctrl+C
        signal.signal(signal.SIGTERM, handle_signal)  # Termination request
        
        # Additional signals that can be caught on macOS
        try:
            signal.signal(signal.SIGHUP, handle_signal)   # Terminal closed
            signal.signal(signal.SIGQUIT, handle_signal)  # Quit from keyboard (Ctrl+\)
            logger.info("Additional signal handlers registered")
        except (AttributeError, ValueError) as e:
            # Some signals might not be available on all platforms
            logger.warning(f"Could not register some signal handlers: {e}")

    def set_state(self, state):
        """Set the application state and update the icon."""
        if state in APP_STATES:
            self.current_state = state
            self.title = APP_STATES[state]
            self.last_state_change = time.time()
            logger.debug(f"App state changed to: {state}")
            
            # Play sound notification for state changes
            if state == 'recording':
                AudioNotifier.play_sound('start')
            elif state == 'completed':
                AudioNotifier.play_sound('success')
                # No need to schedule a separate timer - we'll handle this in refresh_icon

    def refresh_icon(self, _):
        """Refresh the icon based on current state."""
        # Check if we need to reset from completed to idle
        if self.current_state == 'completed':
            elapsed = time.time() - self.last_state_change
            if elapsed >= 3.0:  # Reset after 3 seconds
                logger.debug(f"Auto-resetting from completed to idle after {elapsed:.1f} seconds")
                self.current_state = 'idle'
                self.title = APP_STATES['idle']
                self.last_state_change = time.time()
                return
        
        # Add animation for processing state
        if self.current_state == 'processing':
            elapsed = time.time() - self.last_state_change
            animation_chars = ['⏳', '⌛']
            self.title = animation_chars[int(elapsed * 2) % len(animation_chars)]
        
        # Blink for recording state
        elif self.current_state == 'recording':
            elapsed = time.time() - self.last_state_change
            if int(elapsed * 2) % 2 == 0:
                self.title = APP_STATES['recording']
            else:
                self.title = '⚫'
        
        # For completed state, ensure it stays visible until timeout
        elif self.current_state == 'completed':
            self.title = APP_STATES['completed']

    def quit_app(self, _):
        """Quit the application."""
        logger.info("Quitting application")
        
        # Stop all processes and clean up resources
        self.stop()
        
        # Force garbage collection
        logger.info("Forcing garbage collection")
        gc.collect()
        
        # Give cleanup processes time to complete
        # This small delay ensures the cleanup thread has time to start
        time.sleep(0.2)
        
        logger.info("Application shutdown complete")
        rumps.quit_application()

    def stop(self):
        """Stop all processes and clean up resources."""
        logger.info("Stopping all processes")
        
        # Clean up audio processor
        if hasattr(self, 'processor'):
            logger.info("Cleaning up audio processor")
            self.processor.cleanup()
        
        # Clean up log files
        logger.info("Preparing for log cleanup")
        
        # We need to flush the logs before cleanup to ensure all messages are written
        for handler in logging.getLogger().handlers:
            handler.flush()
        
        # Direct cleanup approach for normal termination
        # This ensures logs are cleaned up even if atexit handlers don't run
        try:
            # Import here to avoid circular imports
            from utils.logger import cleanup_logs
            
            # Schedule the cleanup to happen after this function returns
            # This allows the current log messages to be written
            def delayed_cleanup():
                # Small delay to ensure logs are fully written
                time.sleep(0.1)
                cleanup_logs(force_cleanup=True)
                
            # Start a thread to perform the cleanup after a short delay
            # This is more reliable than atexit for menu bar apps that might be force-quit
            cleanup_thread = Thread(target=delayed_cleanup, daemon=False)
            cleanup_thread.start()
            
            logger.info("Log cleanup scheduled")
        except Exception as e:
            logger.error(f"Error scheduling log cleanup: {e}")
        
        # Force garbage collection
        gc.collect()
        
        logger.info("All processes stopped")

    def toggle_recording(self, _):
        """Toggle recording state."""
        self.processor.toggle_recording()

def main():
    """Run the audio transcriber application."""
    app = AudioTranscriberApp()
    app.run()
    
    return app 
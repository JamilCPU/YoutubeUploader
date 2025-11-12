"""
Main entry point for the YouTube Uploader application.
This is the central hub that orchestrates the file watcher and handler.
"""
import time
from pathlib import Path
from watchdog.observers import Observer

from fileHandler import NewFileHandler
from uploader import Uploader


class YouTubeUploader:
    """
    Central hub for the YouTube uploader application.
    Manages the file watcher and coordinates between components.
    """
    
    def __init__(self, watchDirectory=None, checkInterval=300):
        """
        Initialize the YouTube uploader.
        
        Args:
            watchDirectory: Directory to watch for new files (default: ~/Videos)
            checkInterval: Seconds between checks for finished files (default: 300 = 5 minutes)
        """
        if watchDirectory is None:
            watchDirectory = Path.home() / "Videos"
        
        self.watchDirectory = Path(watchDirectory)
        self.checkInterval = checkInterval
        self.observer = None
        self.eventHandler = None
        self.uploader = None
        
        # Initialize YouTube uploader (uses environment variables)
        self.uploader = Uploader()
    
    def start(self):
        """
        Start watching for files and begin the upload process.
        """
        print(f"Starting YouTube Uploader...")
        print(f"Watching directory: {self.watchDirectory}")
        
        # Create the event handler with uploader
        self.eventHandler = NewFileHandler(
            checkInterval=self.checkInterval,
            uploader=self.uploader
        )
        
        # Set up the file watcher
        self.observer = Observer()
        self.observer.schedule(
            self.eventHandler, 
            str(self.watchDirectory), 
            recursive=False
        )
        
        # Start watching
        self.observer.start()
        print("File watcher started. Press Ctrl+C to stop...")
        
        try:
            # Keep the application running
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """
        Stop watching for files and clean up resources.
        """
        print("\nStopping YouTube Uploader...")
        
        if self.observer:
            self.observer.stop()
            self.observer.join()
        
        if self.eventHandler:
            self.eventHandler.running = False
        
        print("Stopped.")


def main():
    """
    Main entry point for the application.
    """
    # Create and start the uploader
    uploader = YouTubeUploader()
    uploader.start()


if __name__ == "__main__":
    main()


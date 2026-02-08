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
    
    def __init__(self, watchDirectory=None, checkInterval=60, guiMode=False):
        """
        Initialize the YouTube uploader.
        
        Args:
            watchDirectory: Directory to watch for new files (default: ~/Videos)
            checkInterval: Seconds between checks for finished files (default: 300 = 5 minutes)
            guiMode: If True, start() returns immediately without blocking (for GUI)
        """
        if watchDirectory is None:
            watchDirectory = Path(r"F:\Recordings")
        
        self.watchDirectory = Path(watchDirectory)
        self.checkInterval = checkInterval
        self.guiMode = guiMode
        self.observer = None
        self.eventHandler = None
        self.uploader = None
        
        # Initialize YouTube uploader (uses environment variables)
        self.uploader = Uploader()
    
    def start(self, statusCallback=None, fileSizeCallback=None, progressCallback=None):
        """
        Start watching for files and begin the upload process.
        
        Args:
            statusCallback: Optional callback for status changes
            fileSizeCallback: Optional callback for file size updates
            progressCallback: Optional callback for upload progress
        """
        print(f"Starting YouTube Uploader...")
        print(f"Watching directory: {self.watchDirectory}")
        
        # Set up uploader with progress callback
        if progressCallback:
            self.uploader.progressCallback = progressCallback
        
        # Create the event handler with uploader and callbacks
        self.eventHandler = NewFileHandler(
            checkInterval=self.checkInterval,
            uploader=self.uploader,
            statusCallback=statusCallback,
            fileSizeCallback=fileSizeCallback
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
        
        if self.guiMode:
            # In GUI mode, return immediately without blocking
            return
        
        try:
            # Keep the application running
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def startWatchingDirectory(self, directory, statusCallback=None, fileSizeCallback=None, progressCallback=None):
        """
        Start watching a specific directory (for GUI mode).
        
        Args:
            directory: Directory path to watch
            statusCallback: Optional callback for status changes
            fileSizeCallback: Optional callback for file size updates
            progressCallback: Optional callback for upload progress
        """
        self.watchDirectory = Path(directory)
        self.start(statusCallback, fileSizeCallback, progressCallback)
    
    def startWatchingFile(self, filePath, statusCallback=None, fileSizeCallback=None, progressCallback=None):
        """
        Start watching a specific file directly (for GUI file picker mode).
        
        Args:
            filePath: File path to watch
            statusCallback: Optional callback for status changes
            fileSizeCallback: Optional callback for file size updates
            progressCallback: Optional callback for upload progress
        """
        # Set up uploader with progress callback
        if progressCallback:
            self.uploader.progressCallback = progressCallback
        
        # Create the event handler with uploader and callbacks
        self.eventHandler = NewFileHandler(
            checkInterval=self.checkInterval,
            uploader=self.uploader,
            statusCallback=statusCallback,
            fileSizeCallback=fileSizeCallback
        )
        
        # Manually set the file to track
        self.eventHandler.setFileToTrack(filePath)
    
    def getStatus(self):
        """
        Get current status for GUI polling.
        
        Returns:
            Dictionary with current status information
        """
        if self.eventHandler:
            return {
                'status': self.eventHandler.status,
                'file': self.eventHandler.currentFilePath,
                'fileSize': self.eventHandler.getFileSize()
            }
        return {
            'status': 'idle',
            'file': None,
            'fileSize': None
        }
    
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
    import sys
    
    # Check if GUI mode is requested
    if len(sys.argv) > 1 and sys.argv[1] == '--gui':
        from PySide6.QtWidgets import QApplication
        from gui import YouTubeUploaderGUI
        
        # Create QApplication first (required before any widgets)
        app = QApplication(sys.argv)
        window = YouTubeUploaderGUI()
        window.run()
        sys.exit(app.exec())
    else:
        # Create and start the uploader in CLI mode
        uploader = YouTubeUploader()
        uploader.start()


if __name__ == "__main__":
    main()


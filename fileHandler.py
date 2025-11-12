import threading
import time
from watchdog.events import FileSystemEventHandler


class NewFileHandler(FileSystemEventHandler):
    """
    Handles file system events. This class tracks a single file being written to
    and only triggers actions when that file has finished being written.

    """
    
    def __init__(self, checkInterval=300, uploader=None):
        """
        Initialize the handler.
        
        Args:
            checkInterval: Number of seconds between checks (default: 300 = 5 minutes)
            uploader: Uploader instance to use for uploading finished files (optional)
        """
        super().__init__()
        self.checkInterval = checkInterval
        self.uploader = uploader

        self.currentFile = None
        self.lastModified = None
        self.lastCheckTime = None
        self.lock = threading.Lock()
        self.running = True
        self.pollThread = threading.Thread(target=self._pollFile, daemon=True)
        self.pollThread.start()
    
    def _pollFile(self):
        """
        Background thread that checks the file every checkInterval seconds.
        """
        while self.running:
            time.sleep(self.checkInterval)
            if self.running:  # Check again in case we stopped during sleep
                self._checkFile()
    
    def _checkFile(self):
        """
        Check if the file has been modified since our last check.
        If modified, wait another checkInterval.
        If not modified, proceed with upload.
        """
        with self.lock:
            if self.currentFile is None:
                return  # No file being tracked
            
            currentTime = time.time()
            timeSinceLastMod = currentTime - self.lastModified
            
            # Check if file was modified since we last checked
            if self.lastModified > self.lastCheckTime:
                # File was modified, update check time and wait another interval
                self.lastCheckTime = currentTime
                print(f"File still being written: {self.currentFile}")
                print(f"  Last modified: {timeSinceLastMod:.1f}s ago, will check again in {self.checkInterval} seconds")
            else:
                # File hasn't been modified, it's finished
                filePath = self.currentFile
                self.currentFile = None
                self.lastModified = None
                self.lastCheckTime = None
                
                print(f"File finished! No modifications for {timeSinceLastMod:.1f}s")
                # Process outside the lock
                self._onFileFinished(filePath)
    
    def _onFileFinished(self, filePath):
        """
        Called when a file has finished being written to.
        Uploads the file to YouTube if an uploader is configured.
        """
        print(f"Recording finished: {filePath}")
        
        if self.uploader:
            # Generate title from current date in MM/DD/YYYY format
            from datetime import datetime
            currentDate = datetime.now()
            title = currentDate.strftime("%m/%d/%Y")
            
            # Upload to YouTube
            print(f"Starting upload to YouTube...")
            videoId = self.uploader.uploadVideo(
                videoPath=filePath,
                title=title,
                description=f"Auto-uploaded recording: {title}",
                privacyStatus="private"  # Start as private, user can change later
            )
            
            if videoId:
                print(f"Successfully uploaded video: {videoId}")
            else:
                print("Failed to upload video")
        else:
            print("No uploader configured, skipping upload")
    
    def on_created(self, event):
        """
        Called when a new file or directory is created.
        OBS creates the file when recording starts.
        """
        if not event.is_directory:
            filePath = event.src_path
            print(f"Recording started: {filePath}")
            
            with self.lock:
                # If we're already tracking a file, warn and replace it
                if self.currentFile is not None:
                    print(f"Warning: Already tracking {self.currentFile}, switching to {filePath}")
                
                # Start tracking this file with current timestamp
                currentTime = time.time()
                self.currentFile = filePath
                self.lastModified = currentTime
                self.lastCheckTime = currentTime
                print(f"Tracking file. Will check in {self.checkInterval} seconds if recording is finished.")
    
    def on_modified(self, event):
        """
        Called when a file is modified. Just update the last modified timestamp
        if it's the file we're tracking.
        """
        if not event.is_directory:
            filePath = event.src_path
            with self.lock:
                if filePath == self.currentFile:
                    # Update the timestamp - very cheap operation
                    self.lastModified = time.time()


import logging
import threading
import time
from pathlib import Path
from watchdog.events import FileSystemEventHandler

# Set up logger
logger = logging.getLogger(__name__)


class NewFileHandler(FileSystemEventHandler):
    """
    Handles file system events. This class tracks a single file being written to
    and only triggers actions when that file has finished being written.

    """
    
    def __init__(self, checkInterval=120, uploader=None, statusCallback=None, fileSizeCallback=None):
        """
        Initialize the handler.
        
        Args:
            checkInterval: Number of seconds between checks (default: 300 = 5 minutes)
            uploader: Uploader instance to use for uploading finished files (optional)
            statusCallback: Callback function(status) called when status changes
            fileSizeCallback: Callback function(filePath, size) called when file size updates
        """
        super().__init__()
        self.checkInterval = checkInterval
        self.uploader = uploader
        self.statusCallback = statusCallback
        self.fileSizeCallback = fileSizeCallback

        self.currentFile = None
        self.lastModified = None
        self.lastCheckTime = None
        self._status = "idle"  # idle, watching, uploading, finished
        self.lock = threading.Lock()
        self.running = True
        self.pollThread = threading.Thread(target=self._pollFile, daemon=True)
        self.pollThread.start()
        
        logger.info(f"FileHandler initialized with checkInterval={checkInterval} seconds")
    
    @property
    def status(self):
        """Get current status."""
        with self.lock:
            return self._status
    
    @property
    def currentFilePath(self):
        """Get current file path being tracked."""
        with self.lock:
            return self.currentFile
    
    def getFileSize(self):
        """
        Get the current size of the file being tracked.
        
        Returns:
            File size in bytes, or None if no file is being tracked
        """
        with self.lock:
            if self.currentFile is None:
                return None
            
            try:
                filePath = Path(self.currentFile)
                if filePath.exists():
                    size = filePath.stat().st_size
                    logger.debug(f"File size check: {self.currentFile} = {size} bytes")
                    return size
                logger.warning(f"File does not exist: {self.currentFile}")
                return None
            except Exception as e:
                logger.error(f"Error getting file size for {self.currentFile}: {e}")
                return None
    
    def setFileToTrack(self, filePath):
        """
        Manually set a file to track (for file picker mode).
        
        Args:
            filePath: Path to the file to track (string or Path)
        """
        filePath = str(filePath)
        logger.info(f"Setting file to track: {filePath}")
        
        # Get the file's actual modification time
        try:
            filePathObj = Path(filePath)
            if not filePathObj.exists():
                logger.error(f"File does not exist: {filePath}")
                raise FileNotFoundError(f"File does not exist: {filePath}")
            
            actualModTime = filePathObj.stat().st_mtime
        except Exception as e:
            logger.error(f"Error getting file modification time for {filePath}: {e}")
            raise
        
        with self.lock:
            if self.currentFile is not None:
                logger.warning(f"Already tracking {self.currentFile}, switching to {filePath}")
                print(f"Warning: Already tracking {self.currentFile}, switching to {filePath}")
            
            currentTime = time.time()
            self.currentFile = filePath
            self.lastModified = actualModTime  # Use actual file modification time
            self.lastCheckTime = currentTime  # Use current time for check reference
            self._status = "watching"
            
            logger.info(f"Started tracking file: {filePath} (checkInterval={self.checkInterval}s, modTime={actualModTime})")
            print(f"Tracking file: {filePath}")
            
            # Call callbacks outside the lock to avoid blocking
            statusCallback = self.statusCallback
            fileSizeCallback = self.fileSizeCallback
        
        # Call callbacks outside the lock to prevent blocking GUI thread
        if statusCallback:
            statusCallback("watching")
        
        # Get initial file size
        if fileSizeCallback:
            size = self.getFileSize()
            if size is not None:
                logger.info(f"Initial file size: {filePath} = {size} bytes")
                fileSizeCallback(filePath, size)
    
    def _setStatus(self, newStatus):
        """Set status and notify callback if available."""
        with self.lock:
            if self._status != newStatus:
                oldStatus = self._status
                self._status = newStatus
                logger.info(f"Status changed: {oldStatus} -> {newStatus}")
                if self.statusCallback:
                    self.statusCallback(newStatus)
    
    def checkFileNow(self):
        """
        Manually trigger a file check (for GUI button).
        This allows users to check if the file is still being written without waiting for the interval.
        """
        logger.info("Manual file check triggered")
        self._checkFile()
        # Also update file size if callback is available
        if self.fileSizeCallback:
            with self.lock:
                if self.currentFile is not None:
                    size = self.getFileSize()
                    if size is not None:
                        logger.debug(f"Manual file size update: {self.currentFile} = {size} bytes")
                        self.fileSizeCallback(self.currentFile, size)
    
    def _pollFile(self):
        """
        Background thread that checks the file every checkInterval seconds.
        """
        logger.info(f"Polling thread started (checkInterval={self.checkInterval}s)")
        try:
            while self.running:
                time.sleep(self.checkInterval)
                if self.running:  # Check again in case we stopped during sleep
                    logger.info(f"Performing periodic check (interval={self.checkInterval}s)")
                    fileStatus =self._checkFile()
                    logger.info(f"File checked.")
                    logger.info(fileStatus)
                    # Update file size callback every check interval
                    # Get file info outside lock to avoid blocking
                    fileSizeCallback = self.fileSizeCallback
                    currentFile = None
                    with self.lock:
                        currentFile = self.currentFile
                    
                    # Call callback outside lock to prevent blocking
                    if fileSizeCallback and currentFile is not None:
                        try:
                            size = self.getFileSize()
                            if size is not None:
                                logger.debug(f"Periodic file size update: {currentFile} = {size} bytes")
                                fileSizeCallback(currentFile, size)
                        except Exception as e:
                            logger.error(f"Error updating file size in polling thread: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Polling thread error: {e}", exc_info=True)
            logger.error("Polling thread has stopped - file monitoring may not work correctly")
    
    def _checkFile(self):
        """
        Check if the file has been modified since our last check.
        If modified, wait another checkInterval.
        If not modified, proceed with upload.
        """
        # Get file path outside lock to avoid holding lock during I/O
        currentFile = None
        lastModified = None
        lastCheckTime = None
        with self.lock:
            if self.currentFile is None:
                logger.info("No file being tracked, skipping check")
                return  # No file being tracked
            currentFile = self.currentFile
            lastModified = self.lastModified
            lastCheckTime = self.lastCheckTime
        
        logger.info(f"Checking file: {currentFile}")
        
        # Perform file I/O operations outside the lock (these can be slow)
        try:
            filePath = Path(currentFile)
            if not filePath.exists():
                logger.warning(f"File no longer exists: {currentFile}")
                return
            
            # Get the file's actual modification time (I/O operation - do outside lock)
            actualModTime = filePath.stat().st_mtime
            currentTime = time.time()
            timeSinceLastMod = currentTime - actualModTime
            
            logger.debug(f"Checking file: {currentFile}, actualModTime={actualModTime}, lastCheckTime={lastCheckTime}, lastModified={lastModified}")
            
            # Now acquire lock only for state updates
            with self.lock:
                # Re-check if file is still being tracked (might have changed)
                if self.currentFile != currentFile:
                    return
                
                # Check if file was modified since we last checked
                # Compare actual file mod time with last known mod time
                if actualModTime > self.lastModified:
                    # File was modified, update mod time and check time, wait another interval
                    self.lastModified = actualModTime
                    self.lastCheckTime = currentTime
                    logger.info(f"File still being written: {currentFile} (modified {timeSinceLastMod:.1f}s ago, will check again in {self.checkInterval}s)")
                    print(f"File still being written: {currentFile}")
                    print(f"  Last modified: {timeSinceLastMod:.1f}s ago, will check again in {self.checkInterval} seconds")
                else:
                    # File hasn't been modified, but check if it's actually been written to
                    # If file was just created and never modified, it might be empty or not ready
                    fileSize = self.getFileSize()
                    if fileSize is not None and fileSize > 0:
                        # File has content and hasn't been modified - it's finished
                        finishedFilePath = self.currentFile
                        self.currentFile = None
                        self.lastModified = None
                        self.lastCheckTime = None
                        self._status = "finished"
                        
                        logger.info(f"File finished writing: {finishedFilePath} (no modifications for {timeSinceLastMod:.1f}s, size={fileSize} bytes)")
                        print(f"File finished! No modifications for {timeSinceLastMod:.1f}s")
                        # Process outside the lock
                        self._onFileFinished(finishedFilePath)
                    else:
                        # File is empty or doesn't exist - wait another interval
                        logger.debug(f"File appears empty or doesn't exist, waiting another interval: {currentFile}")
                        self.lastCheckTime = currentTime
        except Exception as e:
            logger.error(f"Error checking file {currentFile}: {e}", exc_info=True)
            return
    
    def _onFileFinished(self, filePath):
        """
        Called when a file has finished being written to.
        Uploads the file to YouTube if an uploader is configured.
        """
        logger.info(f"Recording finished: {filePath}")
        print(f"Recording finished: {filePath}")
        
        # Verify file exists and has content before attempting upload
        try:
            filePathObj = Path(filePath)
            if not filePathObj.exists():
                logger.warning(f"File does not exist, skipping upload: {filePath}")
                print(f"File does not exist: {filePath}")
                self._setStatus("idle")
                return
            
            fileSize = filePathObj.stat().st_size
            if fileSize == 0:
                logger.warning(f"File is empty, skipping upload: {filePath}")
                print(f"File is empty, skipping upload: {filePath}")
                self._setStatus("idle")
                return
        except Exception as e:
            logger.error(f"Error checking file before upload: {e}")
            print(f"Error checking file: {e}")
            self._setStatus("idle")
            return
        
        if self.uploader:
            # Notify UI that upload is starting
            self._setStatus("uploading")
            
            # Generate title from current date and time in MM/DD/YYYY - HH:MMam/pm format
            from datetime import datetime
            currentDate = datetime.now()
            title = currentDate.strftime("%m/%d/%Y - %I:%M%p").replace("AM", "am").replace("PM", "pm")
            
            # Upload to YouTube (authentication happens here, not earlier)
            logger.info(f"Starting upload to YouTube: {filePath} (size: {fileSize} bytes)")
            print(f"Starting upload to YouTube...")
            try:
                videoId = self.uploader.uploadVideo(
                    videoPath=filePath,
                    title=title,
                    description=f"Auto-uploaded recording: {title}",
                    privacyStatus="private"  # Start as private, user can change later
                )
                
                if videoId:
                    logger.info(f"Successfully uploaded video: {videoId}")
                    print(f"Successfully uploaded video: {videoId}")
                    self._setStatus("finished")
                else:
                    logger.error(f"Upload failed for: {filePath}")
                    print("Failed to upload video")
                    self._setStatus("idle")
            except Exception as e:
                logger.error(f"Exception during upload: {e}", exc_info=True)
                print(f"Error during upload: {e}")
                self._setStatus("idle")
        else:
            logger.warning("No uploader configured, skipping upload")
            print("No uploader configured, skipping upload")
            self._setStatus("idle")
    
    def on_created(self, event):
        """
        Called when a new file or directory is created.
        OBS creates the file when recording starts.
        """
        if not event.is_directory:
            filePath = event.src_path
            logger.info(f"New file created (directory watch): {filePath}")
            print(f"Recording started: {filePath}")
            
            # Get the file's actual modification time (I/O operation - do outside lock)
            try:
                filePathObj = Path(filePath)
                if not filePathObj.exists():
                    logger.warning(f"File does not exist yet: {filePath}, will retry on next check")
                    return
                
                actualModTime = filePathObj.stat().st_mtime
            except Exception as e:
                logger.error(f"Error getting file modification time for {filePath}: {e}")
                # Continue anyway - will be caught on next check
                actualModTime = time.time()
            
            with self.lock:
                # If we're already tracking a file, warn and replace it
                if self.currentFile is not None:
                    logger.warning(f"Already tracking {self.currentFile}, switching to {filePath}")
                    print(f"Warning: Already tracking {self.currentFile}, switching to {filePath}")
                
                # Start tracking this file with current timestamp
                currentTime = time.time()
                self.currentFile = filePath
                self.lastModified = actualModTime  # Use actual file modification time
                self.lastCheckTime = currentTime  # Use current time for check reference
                self._status = "watching"
                
                logger.info(f"Started tracking file from directory watch: {filePath} (checkInterval={self.checkInterval}s, modTime={actualModTime})")
                print(f"Tracking file. Will check in {self.checkInterval} seconds if recording is finished.")
                
                # Get callbacks outside lock to avoid blocking
                statusCallback = self.statusCallback
                fileSizeCallback = self.fileSizeCallback
            
            # Call callbacks outside the lock to prevent blocking
            if statusCallback:
                statusCallback("watching")
            
            # Get initial file size
            if fileSizeCallback:
                size = self.getFileSize()
                if size is not None:
                    logger.info(f"Initial file size from directory watch: {filePath} = {size} bytes")
                    fileSizeCallback(filePath, size)
            
            # Immediately check the file to verify it's being tracked correctly
            logger.info(f"Performing immediate check on newly detected file: {filePath}")
            self._checkFile()
    
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
                    oldTime = self.lastModified
                    self.lastModified = time.time()
                    logger.debug(f"File modified event: {filePath} (timestamp updated: {oldTime} -> {self.lastModified})")
                    
                    # Optionally update file size on modification
                    if self.fileSizeCallback:
                        size = self.getFileSize()
                        if size is not None:
                            logger.debug(f"File size update from modification event: {filePath} = {size} bytes")
                            self.fileSizeCallback(filePath, size)

"""
PySide6 GUI for YouTube Uploader application.
Provides a modern desktop interface for selecting files/directories to watch
and monitoring upload progress.
"""
import logging
import sys
import ctypes
import ctypes.wintypes
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QRadioButton, QButtonGroup, QGroupBox,
    QFileDialog, QProgressDialog, QMessageBox, QTextEdit, QSystemTrayIcon, QMenu
)
from PySide6.QtCore import QTimer, Qt, Signal, QObject, QThread
from PySide6.QtGui import QFont, QIcon, QScreen, QCloseEvent, QPixmap, QPainter, QColor, QPoint, QPolygon, QPoint, QPolygon

from main import YouTubeUploader
from fileHandler import NewFileHandler

# Set up logger
logger = logging.getLogger(__name__)


class StatusSignals(QObject):
    """Qt signals for thread-safe UI updates."""
    statusChanged = Signal(str)
    fileSizeChanged = Signal(str, int)
    uploadProgress = Signal(int)


class UploadThread(QThread):
    """Thread for uploading videos in the background."""
    uploadProgress = Signal(int)
    uploadAccepted = Signal(str, str, str)  # filePath, title, uploadUrl (when YouTube accepts)
    uploadComplete = Signal(str, str)  # videoId, filePath
    uploadError = Signal(str, str)  # error message, filePath
    
    def __init__(self, filePath, uploader):
        """
        Initialize upload thread.
        
        Args:
            filePath: Path to file to upload
            uploader: Uploader instance to use
        """
        super().__init__()
        self.filePath = filePath
        self.uploader = uploader
        
        # Set up progress callback
        self.uploader.progressCallback = self._progressCallback
        # Set up upload accepted callback
        self.uploader.uploadAcceptedCallback = self._uploadAcceptedCallback
    
    def _progressCallback(self, progress):
        """Thread-safe progress callback."""
        self.uploadProgress.emit(progress)
    
    def _uploadAcceptedCallback(self):
        """Thread-safe callback when YouTube accepts upload."""
        from pathlib import Path
        from datetime import datetime
        currentDate = datetime.now()
        title = currentDate.strftime("%m/%d/%Y - %I:%M%p").replace("AM", "am").replace("PM", "pm")
        # Emit signal with file path, title, and a placeholder for upload URL
        self.uploadAccepted.emit(str(self.filePath), title, "YouTube upload session established")
    
    def run(self):
        """Execute upload in background thread."""
        try:
            from datetime import datetime
            # Generate title from current date and time
            currentDate = datetime.now()
            title = currentDate.strftime("%m/%d/%Y - %I:%M%p").replace("AM", "am").replace("PM", "pm")
            
            logger.info(f"Starting direct upload: {self.filePath}")
            logger.info(f"Upload title: {title}")
            
            # Call uploadVideo and capture detailed logging
            videoId = self.uploader.uploadVideo(
                videoPath=self.filePath,
                title=title,
                description=f"Direct upload: {title}",
                privacyStatus="private"
            )
            
            if videoId:
                logger.info(f"Direct upload successful: {self.filePath} -> Video ID: {videoId}")
                logger.info(f"Video URL: https://www.youtube.com/watch?v={videoId}")
                self.uploadComplete.emit(videoId, str(self.filePath))
            else:
                errorMsg = "Upload failed - no video ID returned"
                logger.error(f"Direct upload failed: {self.filePath}")
                self.uploadError.emit(errorMsg, str(self.filePath))
        except Exception as e:
            errorMsg = f"Upload error: {str(e)}"
            logger.error(f"Direct upload exception: {self.filePath} - {e}", exc_info=True)
            self.uploadError.emit(errorMsg, str(self.filePath))


class YouTubeUploaderGUI(QMainWindow):
    """
    Main GUI window for YouTube Uploader.
    """
    
    def __init__(self):
        super().__init__()
        self.uploader = None
        self.eventHandler = None
        self.observer = None
        self.currentFile = None
        self.currentFileSize = 0
        self.currentStatus = "idle"
        self.currentProgress = 0  # Track upload progress percentage
        self.uploadDialog = None
        
        # Upload tracking for direct uploads
        self.uploadThread = None
        self.uploadingFiles = set()  # Track files currently being uploaded
        
        # System tray
        self.trayIcon = None
        self.showAction = None
        self.hideAction = None
        self.quitAction = None
        self.normalIcon = None
        self.uploadIcon = None
        self.uploadPulseTimer = None
        self.pulseOpacity = 0.5
        self.pulseDirection = 1  # 1 for increasing, -1 for decreasing
        
        # Create signals object for thread-safe communication
        self.signals = StatusSignals()
        self.signals.statusChanged.connect(self._onStatusChanged)
        self.signals.fileSizeChanged.connect(self._onFileSizeChanged)
        self.signals.uploadProgress.connect(self._onUploadProgress)
        
        # Initialize uploader
        self.uploader = YouTubeUploader(guiMode=True)
        
        # Set up UI
        self.initUI()
        
        # Create system tray icon
        self._createTrayIcon()
        
        # Set up timer for file size updates (every 5 minutes = 300000 ms)
        self.sizeUpdateTimer = QTimer()
        self.sizeUpdateTimer.timeout.connect(self.updateFileSize)
        self.sizeUpdateTimer.start(300000)  # 5 minutes
    
    def initUI(self):
        """Initialize the user interface."""
        self.setWindowTitle("YouTube Uploader")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        # Position window at bottom-right (but don't show yet)
        self._positionWindowBottomRight()
        
        # Central widget
        centralWidget = QWidget()
        self.setCentralWidget(centralWidget)
        layout = QVBoxLayout()
        centralWidget.setLayout(layout)
        
        # Title
        titleLabel = QLabel("YouTube Uploader")
        titleFont = QFont()
        titleFont.setPointSize(16)
        titleFont.setBold(True)
        titleLabel.setFont(titleFont)
        titleLabel.setAlignment(Qt.AlignCenter)
        layout.addWidget(titleLabel)
        
        # Mode selection group
        modeGroup = QGroupBox("Mode Selection")
        modeLayout = QVBoxLayout()
        
        self.modeButtonGroup = QButtonGroup()
        self.directoryRadio = QRadioButton("Watch Directory")
        self.fileRadio = QRadioButton("Watch File")
        self.directoryRadio.setChecked(True)
        
        self.modeButtonGroup.addButton(self.directoryRadio, 0)
        self.modeButtonGroup.addButton(self.fileRadio, 1)
        
        modeLayout.addWidget(self.directoryRadio)
        modeLayout.addWidget(self.fileRadio)
        modeGroup.setLayout(modeLayout)
        layout.addWidget(modeGroup)
        
        # Selection buttons
        buttonLayout = QHBoxLayout()
        self.selectDirectoryBtn = QPushButton("Watch Directory")
        self.selectFileBtn = QPushButton("Watch File")
        self.uploadFileBtn = QPushButton("Upload File")
        self.selectDirectoryBtn.clicked.connect(self.selectDirectory)
        self.selectFileBtn.clicked.connect(self.selectFile)
        self.uploadFileBtn.clicked.connect(self.uploadFile)
        buttonLayout.addWidget(self.selectDirectoryBtn)
        buttonLayout.addWidget(self.selectFileBtn)
        buttonLayout.addWidget(self.uploadFileBtn)
        layout.addLayout(buttonLayout)
        
        # Selected path display
        self.pathLabel = QLabel("No directory/file selected")
        self.pathLabel.setWordWrap(True)
        self.pathLabel.setStyleSheet("padding: 5px; background-color: #f0f0f0; border-radius: 3px;")
        layout.addWidget(self.pathLabel)
        
        # Status group
        statusGroup = QGroupBox("Current Status")
        statusLayout = QVBoxLayout()
        
        self.fileLabel = QLabel("File: None")
        self.sizeLabel = QLabel("Size: N/A")
        self.statusLabel = QLabel("Status: Idle")
        self.progressLabel = QLabel("")  # For upload progress
        
        statusLayout.addWidget(self.fileLabel)
        statusLayout.addWidget(self.sizeLabel)
        statusLayout.addWidget(self.statusLabel)
        statusLayout.addWidget(self.progressLabel)
        statusGroup.setLayout(statusLayout)
        layout.addWidget(statusGroup)
        
        # Control buttons
        controlLayout = QHBoxLayout()
        self.startBtn = QPushButton("Start")
        self.stopBtn = QPushButton("Stop")
        self.checkNowBtn = QPushButton("Check Now")
        self.testCredentialsBtn = QPushButton("Test Credentials")
        self.startBtn.clicked.connect(self.startWatching)
        self.stopBtn.clicked.connect(self.stopWatching)
        self.checkNowBtn.clicked.connect(self.checkFileNow)
        self.testCredentialsBtn.clicked.connect(self.testCredentials)
        self.stopBtn.setEnabled(False)
        self.checkNowBtn.setEnabled(False)
        
        controlLayout.addWidget(self.startBtn)
        controlLayout.addWidget(self.stopBtn)
        controlLayout.addWidget(self.checkNowBtn)
        layout.addLayout(controlLayout)
        
        # Test credentials button (separate row)
        testLayout = QHBoxLayout()
        testLayout.addWidget(self.testCredentialsBtn)
        testLayout.addStretch()
        layout.addLayout(testLayout)
        
        # Add stretch to push everything to top
        layout.addStretch()
    
    def _createTrayIcon(self):
        """Create and configure the system tray icon and menu."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray is not available on this system")
            return
        
        # Create system tray icon
        self.trayIcon = QSystemTrayIcon(self)
        
        # Set icon - try to use a theme icon, fallback to a simple icon
        icon = QIcon.fromTheme("video-x-generic")
        if icon.isNull():
            # Fallback: create a simple icon or use application icon
            icon = self.style().standardIcon(self.style().StandardPixmap.SP_MediaPlay)
            if icon.isNull():
                # Last resort: use a default icon
                icon = QIcon()
        
        self.trayIcon.setIcon(icon)
        self.trayIcon.setToolTip("YouTube Uploader")
        
        # Store the normal icon
        self.normalIcon = icon
        
        # Initialize upload icon (will be created on first upload)
        self.uploadIcon = None
        
        # Set up pulse timer for upload animation
        self.uploadPulseTimer = QTimer()
        self.uploadPulseTimer.timeout.connect(self._updateUploadIconAnimation)
        
        # Create context menu
        trayMenu = QMenu()
        
        # Show/Hide action (will be toggled)
        self.showAction = trayMenu.addAction("Show Window")
        self.showAction.triggered.connect(self.showWindow)
        
        self.hideAction = trayMenu.addAction("Hide Window")
        self.hideAction.triggered.connect(self.hideWindow)
        self.hideAction.setVisible(False)  # Initially hidden since window starts hidden
        
        trayMenu.addSeparator()
        
        # Quit action
        self.quitAction = trayMenu.addAction("Quit")
        self.quitAction.triggered.connect(QApplication.instance().quit)
        
        self.trayIcon.setContextMenu(trayMenu)
        
        # Handle tray icon activation (double-click)
        self.trayIcon.activated.connect(self._onTrayIconActivated)
        
        # Show the tray icon
        self.trayIcon.show()
        logger.info("System tray icon created and shown")
    
    def _createUploadIcon(self):
        """Create a light green upload icon with pulsing animation support."""
        # Create pixmap at multiple sizes for high DPI support
        sizes = [16, 32, 64]
        icon = QIcon()
        
        for size in sizes:
            pixmap = QPixmap(size, size)
            pixmap.fill(QColor(0, 0, 0, 0))  # Transparent background
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Draw light green circle (#90EE90 - light green)
            lightGreen = QColor(144, 238, 144)  # #90EE90
            painter.setBrush(lightGreen)
            painter.setPen(QColor(0, 0, 0, 0))  # No border
            
            # Draw circle with some padding
            padding = 2
            painter.drawEllipse(padding, padding, size - 2 * padding, size - 2 * padding)
            
            # Draw upload arrow (white or darker green)
            arrowColor = QColor(255, 255, 255)  # White arrow
            painter.setPen(arrowColor)
            painter.setBrush(arrowColor)
            
            # Draw upward arrow in center
            centerX = size // 2
            centerY = size // 2
            arrowSize = size // 4
            
            # Create arrow path (triangle pointing up)
            arrow = QPolygon([
                QPoint(centerX, centerY - arrowSize // 2),  # Top point
                QPoint(centerX - arrowSize // 2, centerY + arrowSize // 4),  # Bottom left
                QPoint(centerX + arrowSize // 2, centerY + arrowSize // 4),  # Bottom right
            ])
            painter.drawPolygon(arrow)
            
            painter.end()
            
            icon.addPixmap(pixmap)
        
        return icon
    
    def _updateUploadIconAnimation(self):
        """Update the upload icon with pulsing animation."""
        # Update opacity based on direction
        opacityStep = 0.1
        minOpacity = 0.3
        maxOpacity = 1.0
        
        self.pulseOpacity += opacityStep * self.pulseDirection
        
        # Reverse direction at boundaries
        if self.pulseOpacity >= maxOpacity:
            self.pulseOpacity = maxOpacity
            self.pulseDirection = -1
        elif self.pulseOpacity <= minOpacity:
            self.pulseOpacity = minOpacity
            self.pulseDirection = 1
        
        # Create animated icon with current opacity
        sizes = [16, 32, 64]
        animatedIcon = QIcon()
        
        for size in sizes:
            pixmap = QPixmap(size, size)
            pixmap.fill(QColor(0, 0, 0, 0))  # Transparent background
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Draw light green circle with opacity
            lightGreen = QColor(144, 238, 144)  # #90EE90
            lightGreen.setAlphaF(self.pulseOpacity)
            painter.setBrush(lightGreen)
            painter.setPen(QColor(0, 0, 0, 0))  # No border
            
            # Draw circle with some padding
            padding = 2
            painter.drawEllipse(padding, padding, size - 2 * padding, size - 2 * padding)
            
            # Draw upload arrow (white with opacity)
            arrowColor = QColor(255, 255, 255)
            arrowColor.setAlphaF(self.pulseOpacity)
            painter.setPen(arrowColor)
            painter.setBrush(arrowColor)
            
            # Draw upward arrow in center
            centerX = size // 2
            centerY = size // 2
            arrowSize = size // 4
            
            # Create arrow path (triangle pointing up)
            arrow = QPolygon([
                QPoint(centerX, centerY - arrowSize // 2),  # Top point
                QPoint(centerX - arrowSize // 2, centerY + arrowSize // 4),  # Bottom left
                QPoint(centerX + arrowSize // 2, centerY + arrowSize // 4),  # Bottom right
            ])
            painter.drawPolygon(arrow)
            
            painter.end()
            
            animatedIcon.addPixmap(pixmap)
        
        # Update tray icon
        if self.trayIcon:
            self.trayIcon.setIcon(animatedIcon)
    
    def _makeTrayIconAlwaysVisible(self):
        """Use Windows API to try to keep the tray icon always visible."""
        if sys.platform != 'win32':
            # Only works on Windows
            return
        
        try:
            # Windows API constants
            NIM_SETVERSION = 0x00000004
            NOTIFYICON_VERSION_4 = 4
            
            # Get the window handle (HWND) from Qt
            hwnd = int(self.winId())
            
            # Load shell32.dll
            shell32 = ctypes.windll.shell32
            
            # Define NOTIFYICONDATA structure
            class NOTIFYICONDATA(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.wintypes.DWORD),
                    ("hWnd", ctypes.wintypes.HWND),
                    ("uID", ctypes.c_uint),
                    ("uFlags", ctypes.c_uint),
                    ("uCallbackMessage", ctypes.c_uint),
                    ("hIcon", ctypes.wintypes.HANDLE),
                    ("szTip", ctypes.c_char * 128),
                    ("dwState", ctypes.wintypes.DWORD),
                    ("dwStateMask", ctypes.wintypes.DWORD),
                    ("szInfo", ctypes.c_char * 256),
                    ("uVersion", ctypes.c_uint),
                    ("szInfoTitle", ctypes.c_char * 64),
                    ("dwInfoFlags", ctypes.wintypes.DWORD),
                    ("guidItem", ctypes.c_char * 16),
                    ("hBalloonIcon", ctypes.wintypes.HANDLE),
                ]
            
            # Create NOTIFYICONDATA structure
            nid = NOTIFYICONDATA()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
            nid.hWnd = hwnd
            nid.uID = 1  # Icon ID
            nid.uVersion = NOTIFYICON_VERSION_4
            
            # Call Shell_NotifyIcon with NIM_SETVERSION
            result = shell32.Shell_NotifyIconW(NIM_SETVERSION, ctypes.byref(nid))
            
            if result:
                logger.info("Successfully set tray icon to version 4 (always visible)")
            else:
                logger.warning("Failed to set tray icon version (may still be hidden)")
                
        except Exception as e:
            logger.warning(f"Could not set tray icon to always visible: {e}")
            # Fallback: Try to keep icon active by updating tooltip
            if self.trayIcon:
                self.trayIcon.setToolTip("YouTube Uploader - Uploading...")
    
    def _onTrayIconActivated(self, reason):
        """Handle tray icon activation (left-click to show window, double-click to toggle)."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Left-click: show window if hidden
            if not self.isVisible():
                self.showWindow()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            # Double-click: toggle window visibility
            if self.isVisible():
                self.hideWindow()
            else:
                self.showWindow()
    
    def _updateTrayMenu(self):
        """Update tray menu text based on window visibility."""
        if self.trayIcon is None:
            return
        
        isVisible = self.isVisible()
        if self.showAction:
            self.showAction.setVisible(not isVisible)
        if self.hideAction:
            self.hideAction.setVisible(isVisible)
    
    def _positionWindowBottomRight(self):
        """Position the window at the bottom-right of the primary screen."""
        screen = QApplication.primaryScreen()
        if screen is None:
            logger.warning("Could not get primary screen, using default position")
            return
        
        screenGeometry = screen.geometry()
        
        # Ensure window has a size (use minimum size if not yet set)
        windowSize = self.size()
        if windowSize.width() <= 0 or windowSize.height() <= 0:
            # Use minimum size or default size
            windowSize = self.minimumSize()
            if windowSize.width() <= 0 or windowSize.height() <= 0:
                windowSize = self.sizeHint()
            if windowSize.width() > 0 and windowSize.height() > 0:
                self.resize(windowSize)
        
        # Calculate bottom-right position
        x = screenGeometry.width() - windowSize.width()
        y = screenGeometry.height() - windowSize.height()
        
        # Move window to calculated position
        self.move(x, y)
        logger.debug(f"Positioned window at bottom-right: ({x}, {y})")
    
    def showWindow(self):
        """Show and position the window at bottom-right."""
        self._positionWindowBottomRight()
        self.show()
        self.raise_()
        self.activateWindow()
        self._updateTrayMenu()
        logger.info("Window shown from system tray")
    
    def hideWindow(self):
        """Hide the window to tray."""
        self.hide()
        self._updateTrayMenu()
        logger.info("Window hidden to system tray")
    
    def closeEvent(self, event: QCloseEvent):
        """Override close event to hide window instead of closing."""
        # Stop animation timer if running
        if self.uploadPulseTimer and self.uploadPulseTimer.isActive():
            self.uploadPulseTimer.stop()
        
        event.ignore()
        self.hideWindow()
    
    def selectDirectory(self):
        """Open directory selection dialog."""
        logger.info("Opening directory selection dialog")
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Directory to Watch",
            str(Path.home())
        )
        if directory:
            self.selectedPath = Path(directory)
            logger.info(f"Directory selected: {self.selectedPath}")
            self.pathLabel.setText(f"Directory: {self.selectedPath}")
            self.directoryRadio.setChecked(True)
        else:
            logger.debug("Directory selection cancelled")
    
    def selectFile(self):
        """Open file selection dialog."""
        logger.info("Opening file selection dialog")
        filePath, _ = QFileDialog.getOpenFileName(
            self,
            "Select File to Watch",
            str(Path.home()),
            "Video Files (*.mp4 *.avi *.mov *.mkv *.webm);;All Files (*)"
        )
        if filePath:
            self.selectedPath = Path(filePath)
            logger.info(f"File selected: {self.selectedPath}")
            self.pathLabel.setText(f"File: {self.selectedPath.name}")
            self.fileRadio.setChecked(True)
        else:
            logger.debug("File selection cancelled")
    
    def startWatching(self):
        """Start watching the selected file or directory."""
        if not hasattr(self, 'selectedPath'):
            logger.warning("Attempted to start watching without selecting a file or directory")
            QMessageBox.warning(self, "No Selection", "Please select a file or directory first.")
            return
        
        try:
            if self.directoryRadio.isChecked():
                # Directory watching mode
                logger.info(f"Starting directory watch mode: {self.selectedPath}")
                self.uploader.startWatchingDirectory(
                    str(self.selectedPath),
                    statusCallback=self._statusCallback,
                    fileSizeCallback=self._fileSizeCallback,
                    progressCallback=self._progressCallback
                )
                self.observer = self.uploader.observer
                self.eventHandler = self.uploader.eventHandler
                logger.info(f"Directory watch started successfully: {self.selectedPath}")
            else:
                # File watching mode
                logger.info(f"Starting file watch mode: {self.selectedPath}")
                self.uploader.startWatchingFile(
                    str(self.selectedPath),
                    statusCallback=self._statusCallback,
                    fileSizeCallback=self._fileSizeCallback,
                    progressCallback=self._progressCallback
                )
                self.eventHandler = self.uploader.eventHandler
                self.observer = None  # No observer in file mode
                self.currentFile = str(self.selectedPath)
                logger.info(f"File watch started successfully: {self.selectedPath}")
                self.updateFileSize()
            
            self.startBtn.setEnabled(False)
            self.stopBtn.setEnabled(True)
            self.checkNowBtn.setEnabled(True)
            self.selectDirectoryBtn.setEnabled(False)
            self.selectFileBtn.setEnabled(False)
            self.directoryRadio.setEnabled(False)
            self.fileRadio.setEnabled(False)
            
        except Exception as e:
            logger.error(f"Failed to start watching: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to start watching: {str(e)}")
    
    def checkFileNow(self):
        """Manually trigger a file check."""
        if not self.eventHandler:
            logger.warning("Attempted to check file but no event handler is active")
            QMessageBox.warning(self, "Not Watching", "Please start watching a file or directory first.")
            return
        
        logger.info("Manual file check triggered by user")
        try:
            self.eventHandler.checkFileNow()
            # Update file size display immediately
            self.updateFileSize()
            QMessageBox.information(self, "Check Complete", "File check completed. See status display for results.")
        except Exception as e:
            logger.error(f"Error during manual file check: {e}", exc_info=True)
            QMessageBox.critical(self, "Check Error", f"Error checking file: {str(e)}")
    
    def testCredentials(self):
        """Test YouTube API credentials and connection."""
        logger.info("Testing YouTube API credentials")
        
        # Disable button during test to prevent multiple clicks
        self.testCredentialsBtn.setEnabled(False)
        self.testCredentialsBtn.setText("Testing...")
        
        try:
            # Create a temporary uploader instance for testing (don't use the main one)
            from uploader import Uploader
            testUploader = Uploader()
            
            # Test credentials
            success, message = testUploader.testCredentials()
            
            if success:
                QMessageBox.information(self, "Credentials Valid", message)
                logger.info(f"Credentials test successful: {message}")
            else:
                QMessageBox.warning(self, "Credentials Invalid", message)
                logger.warning(f"Credentials test failed: {message}")
                
        except Exception as e:
            errorMsg = f"Error testing credentials: {str(e)}"
            logger.error(errorMsg, exc_info=True)
            QMessageBox.critical(self, "Test Error", errorMsg)
        finally:
            # Re-enable button
            self.testCredentialsBtn.setEnabled(True)
            self.testCredentialsBtn.setText("Test Credentials")
    
    def stopWatching(self):
        """Stop watching and clean up."""
        logger.info("Stopping file/directory watch")
        
        if self.observer:
            logger.debug("Stopping directory observer")
            self.observer.stop()
            self.observer.join()
            self.observer = None
        
        if self.eventHandler:
            logger.debug("Stopping event handler")
            self.eventHandler.running = False
            self.eventHandler = None
        
        self.currentFile = None
        self.currentFileSize = 0
        self.currentStatus = "idle"
        self.updateStatusDisplay()
        
        logger.info("Watch stopped successfully")
        
        self.startBtn.setEnabled(True)
        self.stopBtn.setEnabled(False)
        self.checkNowBtn.setEnabled(False)
        self.selectDirectoryBtn.setEnabled(True)
        self.selectFileBtn.setEnabled(True)
        self.directoryRadio.setEnabled(True)
        self.fileRadio.setEnabled(True)
    
    def _statusCallback(self, status):
        """Thread-safe status callback."""
        self.signals.statusChanged.emit(status)
    
    def _fileSizeCallback(self, filePath, size):
        """Thread-safe file size callback."""
        self.signals.fileSizeChanged.emit(filePath, size)
    
    def _progressCallback(self, progress):
        """Thread-safe progress callback."""
        self.signals.uploadProgress.emit(progress)
    
    def _onStatusChanged(self, status):
        """Handle status change in UI thread."""
        self.currentStatus = status
        
        if status == "uploading":
            # Reset progress when starting upload
            self.currentProgress = 0
            # Update status display for upload
            if self.currentFile:
                self.progressLabel.setText("Preparing upload...")
            
            # Update tray icon to upload icon with animation
            if self.trayIcon:
                # Create upload icon if not already created
                if self.uploadIcon is None:
                    self.uploadIcon = self._createUploadIcon()
                
                # Start pulse animation (every 150ms)
                self.pulseOpacity = 0.5  # Start at mid-brightness
                self.pulseDirection = 1  # Start increasing
                self.uploadPulseTimer.start(150)
                
                # Set initial upload icon
                self.trayIcon.setIcon(self.uploadIcon)
                
                # Try to make icon always visible
                self._makeTrayIconAlwaysVisible()
                
                logger.info("Tray icon changed to upload mode (light green, animated)")
        elif status == "finished" or status == "idle":
            # Stop animation and restore normal icon
            if self.uploadPulseTimer and self.uploadPulseTimer.isActive():
                self.uploadPulseTimer.stop()
            
            if self.trayIcon and self.normalIcon:
                self.trayIcon.setIcon(self.normalIcon)
                logger.info("Tray icon restored to normal mode")
            
            if status == "finished":
                # Update status display after upload completes
                self.progressLabel.setText("Upload complete!")
                # Reset after a moment
                QTimer.singleShot(5000, self._resetUploadStatus)
        
        self.updateStatusDisplay()
    
    def _onFileSizeChanged(self, filePath, size):
        """Handle file size change in UI thread."""
        self.currentFile = filePath
        self.currentFileSize = size
        self.updateStatusDisplay()
    
    def _onUploadProgress(self, progress):
        """Handle upload progress in UI thread."""
        self.currentProgress = progress
        self.progressLabel.setText(f"Uploading: {progress}%")
        self.updateStatusDisplay()
    
    def updateFileSize(self):
        """Manually update file size (called by timer)."""
        if self.eventHandler and self.eventHandler.currentFilePath:
            size = self.eventHandler.getFileSize()
            if size is not None:
                logger.debug(f"Timer-based file size update: {self.eventHandler.currentFilePath} = {size} bytes")
                self.currentFileSize = size
                self.currentFile = self.eventHandler.currentFilePath
                self.updateStatusDisplay()
    
    def updateStatusDisplay(self):
        """Update the status display labels."""
        if self.currentFile:
            filePath = Path(self.currentFile)
            self.fileLabel.setText(f"File: {filePath.name}")
            
            # Format file size
            sizeStr = self.formatFileSize(self.currentFileSize)
            self.sizeLabel.setText(f"Size: {sizeStr}")
        else:
            self.fileLabel.setText("File: None")
            self.sizeLabel.setText("Size: N/A")
        
        # Update status label with progress if uploading
        statusText = self.currentStatus.capitalize()
        if self.currentStatus == "uploading" and self.currentProgress > 0:
            self.statusLabel.setText(f"Status: {statusText} ({self.currentProgress}%)")
        else:
            self.statusLabel.setText(f"Status: {statusText}")
        
        # Show/hide progress label based on status
        if self.currentStatus == "uploading":
            self.progressLabel.setVisible(True)
        elif self.currentStatus == "finished":
            self.progressLabel.setVisible(True)
        else:
            # Hide progress label when not uploading
            if not self.progressLabel.text():
                self.progressLabel.setVisible(False)
    
    def formatFileSize(self, sizeBytes):
        """Format file size in human-readable format."""
        if sizeBytes is None:
            return "N/A"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if sizeBytes < 1024.0:
                return f"{sizeBytes:.2f} {unit}"
            sizeBytes /= 1024.0
        return f"{sizeBytes:.2f} PB"
    
    def showUploadDialog(self, filename):
        """Show upload progress dialog."""
        if self.uploadDialog:
            return
        
        self.uploadDialog = QProgressDialog(
            f"Uploading: {filename}",
            None,  # No cancel button for now
            0,
            100,
            self
        )
        self.uploadDialog.setWindowTitle("Uploading Video")
        self.uploadDialog.setWindowModality(Qt.WindowModal)
        self.uploadDialog.setAutoClose(False)
        self.uploadDialog.setAutoReset(False)
        self.uploadDialog.show()
    
    def uploadFile(self):
        """Select a file and upload it directly to YouTube."""
        logger.info("Opening file selection dialog for direct upload")
        filePath, _ = QFileDialog.getOpenFileName(
            self,
            "Select File to Upload",
            str(Path.home()),
            "Video Files (*.mp4 *.avi *.mov *.mkv *.webm);;All Files (*)"
        )
        
        if not filePath:
            logger.debug("File selection cancelled for direct upload")
            return
        
        filePath = Path(filePath)
        normalizedPath = str(filePath.resolve())
        
        # Check if file is already being uploaded
        if normalizedPath in self.uploadingFiles:
            logger.warning(f"Attempted to upload file that is already uploading: {normalizedPath}")
            QMessageBox.warning(
                self,
                "Already Uploading",
                f"This file is already being uploaded:\n{filePath.name}\n\nPlease wait for the current upload to complete."
            )
            return
        
        # Verify file exists and has content
        if not filePath.exists():
            QMessageBox.warning(self, "File Not Found", f"File does not exist: {filePath}")
            return
        
        try:
            fileSize = filePath.stat().st_size
            if fileSize == 0:
                QMessageBox.warning(self, "Empty File", f"File is empty: {filePath.name}")
                return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error checking file: {str(e)}")
            return
        
        # Add to uploading set
        self.uploadingFiles.add(normalizedPath)
        logger.info(f"Starting direct upload: {normalizedPath}")
        
        # Create a new Uploader instance for this upload (to avoid conflicts)
        from uploader import Uploader
        uploader = Uploader()
        
        # Create upload thread
        self.uploadThread = UploadThread(normalizedPath, uploader)
        self.uploadThread.uploadProgress.connect(self._onDirectUploadProgress)
        self.uploadThread.uploadAccepted.connect(self._onDirectUploadAccepted)
        self.uploadThread.uploadComplete.connect(self._onDirectUploadComplete)
        self.uploadThread.uploadError.connect(self._onDirectUploadError)
        
        # Update status display to show upload starting
        self.currentFile = str(filePath)
        self.currentFileSize = filePath.stat().st_size
        self.currentStatus = "uploading"
        self.currentProgress = 0  # Reset progress when starting upload
        self.updateStatusDisplay()
        self.progressLabel.setText("Preparing upload...")
        
        # Update tray icon to upload icon with animation
        if self.trayIcon:
            # Create upload icon if not already created
            if self.uploadIcon is None:
                self.uploadIcon = self._createUploadIcon()
            
            # Start pulse animation (every 150ms)
            self.pulseOpacity = 0.5  # Start at mid-brightness
            self.pulseDirection = 1  # Start increasing
            self.uploadPulseTimer.start(150)
            
            # Set initial upload icon
            self.trayIcon.setIcon(self.uploadIcon)
            
            # Try to make icon always visible
            self._makeTrayIconAlwaysVisible()
            
            logger.info("Tray icon changed to upload mode for direct upload (light green, animated)")
        
        # Start upload in background thread
        self.uploadThread.start()
    
    def _onDirectUploadAccepted(self, filePath, title, uploadUrl):
        """Handle when YouTube accepts the upload request."""
        logger.info(f"YouTube accepted upload request for: {filePath}")
        self.progressLabel.setText("Upload accepted by YouTube - transferring...")
        self.updateStatusDisplay()
    
    def _onDirectUploadProgress(self, progress):
        """Handle direct upload progress updates."""
        self.currentProgress = progress
        self.progressLabel.setText(f"Uploading: {progress}%")
        self.updateStatusDisplay()
    
    def _onDirectUploadComplete(self, videoId, filePath):
        """Handle direct upload completion."""
        normalizedPath = str(Path(filePath).resolve())
        self.uploadingFiles.discard(normalizedPath)
        
        logger.info(f"Direct upload completed: {filePath} -> {videoId}")
        
        # Stop animation and restore normal icon
        if self.uploadPulseTimer and self.uploadPulseTimer.isActive():
            self.uploadPulseTimer.stop()
        
        if self.trayIcon and self.normalIcon:
            self.trayIcon.setIcon(self.normalIcon)
            logger.info("Tray icon restored to normal mode after direct upload")
        
        # Update status display
        self.currentStatus = "finished"
        self.progressLabel.setText(f"Complete! Video ID: {videoId}")
        self.updateStatusDisplay()
        
        # Clean up thread
        if self.uploadThread:
            self.uploadThread.wait()
            self.uploadThread = None
        
        # Reset status after a moment
        QTimer.singleShot(5000, self._resetUploadStatus)  # Reset after 5 seconds
    
    def _resetUploadStatus(self):
        """Reset upload status display after completion."""
        self.currentFile = None
        self.currentFileSize = 0
        self.currentStatus = "idle"
        self.progressLabel.setText("")
        self.updateStatusDisplay()
    
    def _onDirectUploadError(self, errorMsg, filePath):
        """Handle direct upload errors."""
        normalizedPath = str(Path(filePath).resolve())
        self.uploadingFiles.discard(normalizedPath)
        
        logger.error(f"Direct upload failed: {filePath} - {errorMsg}")
        
        # Stop animation and restore normal icon
        if self.uploadPulseTimer and self.uploadPulseTimer.isActive():
            self.uploadPulseTimer.stop()
        
        if self.trayIcon and self.normalIcon:
            self.trayIcon.setIcon(self.normalIcon)
            logger.info("Tray icon restored to normal mode after upload error")
        
        # Update status display
        self.currentStatus = "idle"
        self.progressLabel.setText(f"Error: {errorMsg[:50]}...")
        self.updateStatusDisplay()
        
        # Clean up thread
        if self.uploadThread:
            self.uploadThread.wait()
            self.uploadThread = None
        
        # Reset status after a moment
        QTimer.singleShot(5000, self._resetUploadStatus)
    
    def run(self):
        """Run the GUI application."""
        # Window starts hidden - accessible only through system tray
        # Don't call self.show() here
        logger.info("GUI application started (window hidden, accessible via system tray)")


def main():
    """Main entry point for GUI application."""
    app = QApplication(sys.argv)
    window = YouTubeUploaderGUI()
    window.run()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

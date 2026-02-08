"""
PySide6 GUI for YouTube Uploader application.
Provides a modern desktop interface for selecting files/directories to watch
and monitoring upload progress.
"""
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QRadioButton, QButtonGroup, QGroupBox,
    QFileDialog, QProgressDialog, QMessageBox, QTextEdit
)
from PySide6.QtCore import QTimer, Qt, Signal, QObject
from PySide6.QtGui import QFont

from main import YouTubeUploader
from fileHandler import NewFileHandler


class StatusSignals(QObject):
    """Qt signals for thread-safe UI updates."""
    statusChanged = Signal(str)
    fileSizeChanged = Signal(str, int)
    uploadProgress = Signal(int)


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
        self.uploadDialog = None
        
        # Create signals object for thread-safe communication
        self.signals = StatusSignals()
        self.signals.statusChanged.connect(self._onStatusChanged)
        self.signals.fileSizeChanged.connect(self._onFileSizeChanged)
        self.signals.uploadProgress.connect(self._onUploadProgress)
        
        # Initialize uploader
        self.uploader = YouTubeUploader(guiMode=True)
        
        # Set up UI
        self.initUI()
        
        # Set up timer for file size updates (every 5 minutes = 300000 ms)
        self.sizeUpdateTimer = QTimer()
        self.sizeUpdateTimer.timeout.connect(self.updateFileSize)
        self.sizeUpdateTimer.start(300000)  # 5 minutes
    
    def initUI(self):
        """Initialize the user interface."""
        self.setWindowTitle("YouTube Uploader")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
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
        self.selectDirectoryBtn = QPushButton("Select Directory")
        self.selectFileBtn = QPushButton("Select File")
        self.selectDirectoryBtn.clicked.connect(self.selectDirectory)
        self.selectFileBtn.clicked.connect(self.selectFile)
        buttonLayout.addWidget(self.selectDirectoryBtn)
        buttonLayout.addWidget(self.selectFileBtn)
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
        
        statusLayout.addWidget(self.fileLabel)
        statusLayout.addWidget(self.sizeLabel)
        statusLayout.addWidget(self.statusLabel)
        statusGroup.setLayout(statusLayout)
        layout.addWidget(statusGroup)
        
        # Control buttons
        controlLayout = QHBoxLayout()
        self.startBtn = QPushButton("Start")
        self.stopBtn = QPushButton("Stop")
        self.startBtn.clicked.connect(self.startWatching)
        self.stopBtn.clicked.connect(self.stopWatching)
        self.stopBtn.setEnabled(False)
        
        controlLayout.addWidget(self.startBtn)
        controlLayout.addWidget(self.stopBtn)
        layout.addLayout(controlLayout)
        
        # Add stretch to push everything to top
        layout.addStretch()
    
    def selectDirectory(self):
        """Open directory selection dialog."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Directory to Watch",
            str(Path.home())
        )
        if directory:
            self.selectedPath = Path(directory)
            self.pathLabel.setText(f"Directory: {self.selectedPath}")
            self.directoryRadio.setChecked(True)
    
    def selectFile(self):
        """Open file selection dialog."""
        filePath, _ = QFileDialog.getOpenFileName(
            self,
            "Select File to Watch",
            str(Path.home()),
            "Video Files (*.mp4 *.avi *.mov *.mkv *.webm);;All Files (*)"
        )
        if filePath:
            self.selectedPath = Path(filePath)
            self.pathLabel.setText(f"File: {self.selectedPath.name}")
            self.fileRadio.setChecked(True)
    
    def startWatching(self):
        """Start watching the selected file or directory."""
        if not hasattr(self, 'selectedPath'):
            QMessageBox.warning(self, "No Selection", "Please select a file or directory first.")
            return
        
        try:
            if self.directoryRadio.isChecked():
                # Directory watching mode
                self.uploader.startWatchingDirectory(
                    str(self.selectedPath),
                    statusCallback=self._statusCallback,
                    fileSizeCallback=self._fileSizeCallback,
                    progressCallback=self._progressCallback
                )
                self.observer = self.uploader.observer
                self.eventHandler = self.uploader.eventHandler
            else:
                # File watching mode
                self.uploader.startWatchingFile(
                    str(self.selectedPath),
                    statusCallback=self._statusCallback,
                    fileSizeCallback=self._fileSizeCallback,
                    progressCallback=self._progressCallback
                )
                self.eventHandler = self.uploader.eventHandler
                self.observer = None  # No observer in file mode
                self.currentFile = str(self.selectedPath)
                self.updateFileSize()
            
            self.startBtn.setEnabled(False)
            self.stopBtn.setEnabled(True)
            self.selectDirectoryBtn.setEnabled(False)
            self.selectFileBtn.setEnabled(False)
            self.directoryRadio.setEnabled(False)
            self.fileRadio.setEnabled(False)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start watching: {str(e)}")
    
    def stopWatching(self):
        """Stop watching and clean up."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        
        if self.eventHandler:
            self.eventHandler.running = False
            self.eventHandler = None
        
        self.currentFile = None
        self.currentFileSize = 0
        self.currentStatus = "idle"
        self.updateStatusDisplay()
        
        self.startBtn.setEnabled(True)
        self.stopBtn.setEnabled(False)
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
            # Show upload dialog
            if self.currentFile:
                self.showUploadDialog(Path(self.currentFile).name)
        elif status == "finished":
            # Close upload dialog if open
            if self.uploadDialog:
                self.uploadDialog.close()
                self.uploadDialog = None
                QMessageBox.information(self, "Upload Complete", "Video uploaded successfully!")
            self.currentStatus = "idle"
        
        self.updateStatusDisplay()
    
    def _onFileSizeChanged(self, filePath, size):
        """Handle file size change in UI thread."""
        self.currentFile = filePath
        self.currentFileSize = size
        self.updateStatusDisplay()
    
    def _onUploadProgress(self, progress):
        """Handle upload progress in UI thread."""
        if self.uploadDialog:
            self.uploadDialog.setValue(progress)
    
    def updateFileSize(self):
        """Manually update file size (called by timer)."""
        if self.eventHandler and self.eventHandler.currentFilePath:
            size = self.eventHandler.getFileSize()
            if size is not None:
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
        
        # Update status label
        statusText = self.currentStatus.capitalize()
        self.statusLabel.setText(f"Status: {statusText}")
    
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
    
    def run(self):
        """Run the GUI application."""
        self.show()


def main():
    """Main entry point for GUI application."""
    app = QApplication(sys.argv)
    window = YouTubeUploaderGUI()
    window.run()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

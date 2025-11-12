"""
File watcher module for setting up directory monitoring.
This module provides utilities for watching directories for file changes.
"""
from pathlib import Path
from watchdog.observers import Observer


def createWatcher(directory, eventHandler, recursive=False):
    """
    Create and configure a file system observer.
    
    Args:
        directory: Directory path to watch (Path or string)
        eventHandler: Event handler instance (e.g., NewFileHandler)
        recursive: Whether to watch subdirectories (default: False)
    
    Returns:
        Configured Observer instance (not started)
    """
    watchPath = Path(directory)
    observer = Observer()
    observer.schedule(eventHandler, str(watchPath), recursive=recursive)
    return observer


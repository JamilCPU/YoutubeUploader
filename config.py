"""
Configuration management for YouTube Uploader.
Handles persistence of application settings in config.json.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
CONFIG_FILE = Path('config.json')


def loadConfig():
    """
    Load config from config.json, creating default if missing.
    Creates config.json with empty/default structure if file doesn't exist.
    
    Returns:
        dict: Config dictionary with 'lastDirectory' key (None if not set)
    """
    try:
        if not CONFIG_FILE.exists():
            # Create default config file
            defaultConfig = {"lastDirectory": None}
            with open(CONFIG_FILE, 'w') as f:
                json.dump(defaultConfig, f, indent=2)
            logger.info(f"Created default config file: {CONFIG_FILE}")
            return defaultConfig
        
        # Load existing config
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        logger.debug(f"Loaded config from {CONFIG_FILE}")
        return config
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        # Create backup and return default
        backupFile = CONFIG_FILE.with_suffix('.json.bak')
        try:
            CONFIG_FILE.rename(backupFile)
            logger.warning(f"Backed up corrupted config to {backupFile}")
        except Exception:
            pass
        defaultConfig = {"lastDirectory": None}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(defaultConfig, f, indent=2)
        return defaultConfig
        
    except Exception as e:
        logger.error(f"Error loading config file: {e}", exc_info=True)
        # Return default config on error
        return {"lastDirectory": None}


def saveConfig(directory):
    """
    Save directory path to config.json.
    
    Args:
        directory: Directory path (Path or str) to save, or None to clear
    """
    try:
        # Load existing config or create new
        config = loadConfig()
        
        # Update lastDirectory
        if directory is None:
            config["lastDirectory"] = None
        else:
            # Convert to string and normalize path
            dirPath = Path(directory)
            config["lastDirectory"] = str(dirPath.resolve())
        
        # Save config
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Saved config: lastDirectory = {config['lastDirectory']}")
        
    except Exception as e:
        logger.error(f"Error saving config file: {e}", exc_info=True)
        # Don't raise - allow operation to continue even if config save fails

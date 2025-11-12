# YouTube Uploader

Automatically uploads OBS recordings to YouTube when recording finishes. The application monitors a directory for new video files, detects when recording is complete, and automatically uploads them to your YouTube channel.

## How It Works

1. **File Monitoring**: Uses the `watchdog` library to monitor a directory (default: `~/Videos`) for new files
2. **Recording Detection**: When OBS starts recording, it creates a file. The application begins tracking this file
3. **Completion Detection**: Periodically checks if the file has stopped being modified (default: every 5 minutes)
4. **Automatic Upload**: Once the file is detected as finished, it automatically uploads to YouTube with:
   - Title: Current date in MM/DD/YYYY format
   - Privacy: Private (you can change this in YouTube Studio)
   - Description: Auto-generated with the date

## Prerequisites

- Python 3.7+
- Google Cloud Project with YouTube Data API v3 enabled
- OAuth 2.0 credentials (Client ID and Secret)
- YouTube channel associated with your Google account

## Setup

### 1. Install Dependencies
ash
pip install -r requirements.txt### 2. Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable **YouTube Data API v3**:
   - Navigate to "APIs & Services" → "Library"
   - Search for "YouTube Data API v3"
   - Click "Enable"
4. Create OAuth 2.0 Credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Application type: **Desktop app**
   - Note your Client ID and Client Secret
5. Configure OAuth Consent Screen:
   - Go to "APIs & Services" → "OAuth consent screen"
   - User Type: External (or Internal if you have Google Workspace)
   - Fill in required fields (App name, support email, etc.)
   - Add scope: `https://www.googleapis.com/auth/youtube.upload`
   - Add yourself as a test user
   - Save

### 3. Configure Environment Variables

Add to your `~/.bashrc`:

export YOUTUBE_CLIENT_ID='your-client-id-here'
export YOUTUBE_CLIENT_SECRET='your-client-secret-here'
export YOUTUBE_PROJECT_ID='your-project-id'  # OptionalReload your bashrc:

source ~/.bashrcOr simply open a new terminal.

### 4. First Run Authentication

On first run, the application will:
1. Open your browser automatically
2. Prompt you to log in with your Google account
3. Ask for permission to upload videos to YouTube
4. Save authentication token to `token.json` (this file is gitignored)

After the first authentication, the token is reused automatically.

## Usage

### Basic Usage

python main.pyThe application will:
- Start monitoring `~/Videos` directory (or your configured directory)
- Wait for OBS to start recording
- Automatically detect when recording finishes
- Upload the video to YouTube

### Custom Configuration

You can customize the watch directory and check interval:
on
from main import YouTubeUploader

uploader = YouTubeUploader(
    watchDirectory="/path/to/your/videos",
    checkInterval=300  # Check every 5 minutes (in seconds)
)
uploader.start()## Project Structure

- `main.py` - Central hub that orchestrates the file watcher and uploader
- `fileHandler.py` - Handles file system events and detects when recordings finish
- `uploader.py` - Manages YouTube API authentication and video uploads
- `watcher.py` - Utility module for file system watching

## How Recording Detection Works

The application uses a polling approach to detect when a file has finished being written:

1. When a file is created, tracking begins
2. Every 5 minutes (configurable), the application checks if the file was modified since the last check
3. If the file was modified, it resets the timer and waits another interval
4. If the file hasn't been modified, it's considered finished and upload begins

This approach is efficient and avoids false positives from temporary file operations.

## Configuration

### Environment Variables

- `YOUTUBE_CLIENT_ID` (required) - OAuth 2.0 Client ID from Google Cloud Console
- `YOUTUBE_CLIENT_SECRET` (required) - OAuth 2.0 Client Secret from Google Cloud Console
- `YOUTUBE_PROJECT_ID` (optional) - Google Cloud Project ID (defaults to 'youtube-uploader')

### Default Settings

- **Watch Directory**: `~/Videos`
- **Check Interval**: 300 seconds (5 minutes)
- **Video Privacy**: Private
- **Video Title**: Current date (MM/DD/YYYY format)

## Troubleshooting

### Environment Variables Not Found

If you see warnings about missing environment variables:
1. Verify they're in `~/.bashrc`: `cat ~/.bashrc | grep YOUTUBE`
2. Reload: `source ~/.bashrc`
3. Verify: `echo $YOUTUBE_CLIENT_ID`

### Authentication Issues

- Make sure you're added as a test user in OAuth consent screen
- Delete `token.json` and re-authenticate if needed
- Ensure YouTube Data API v3 is enabled in your project

### Videos Not Detecting

- Check that OBS is saving to the watched directory
- Verify the file is actually being created (check file system)
- Check the console output for debug messages

## Notes

- Videos are uploaded as **private** by default - you can change this in YouTube Studio
- The application tracks only one file at a time
- Authentication token is stored in `token.json` (gitignored for security)
- The application runs continuously until stopped with Ctrl+C

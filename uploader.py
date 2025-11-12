"""
YouTube video uploader using the YouTube Data API v3.
Handles authentication and video uploads to YouTube.
"""
import os
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


class Uploader:
    """
    Handles uploading videos to YouTube using the YouTube Data API v3.
    """
    
    # YouTube API scopes required for uploading videos
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    
    def __init__(self, tokenFile='token.json'):
        """
        Initialize the YouTube uploader.
        
        Args:
            tokenFile: Path to store/load OAuth token
        """
        self.tokenFile = Path(tokenFile)
        self.youtubeService = None
        self.credentials = None
    
    def _getClientConfig(self):
        """
        Get OAuth client configuration from environment variables.
        
        Returns:
            Client configuration dict, or None if environment variables are not set
        """
        clientId = os.getenv('YOUTUBE_CLIENT_ID')
        clientSecret = os.getenv('YOUTUBE_CLIENT_SECRET')
        clientProjectId = os.getenv('YOUTUBE_PROJECT_ID')
        if not clientId or not clientSecret or not clientProjectId:
            return None
        
        return {
            "installed": {
                "client_id": clientId,
                "client_secret": clientSecret,
                "project_id": clientProjectId,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": ["http://localhost"]
            }
        }
    
    def authenticate(self):
        """
        Authenticate with YouTube API using OAuth 2.0.
        Uses environment variables for OAuth credentials.
        Creates token.json on first run after user authorizes.
        
        Returns:
            True if authentication successful, False otherwise
        """
        # Load existing token if available
        if self.tokenFile.exists():
            self.credentials = Credentials.from_authorized_user_file(
                str(self.tokenFile), 
                self.SCOPES
            )
        
        # If no valid credentials, get new ones
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                # Refresh expired token
                self.credentials.refresh(Request())
            else:
                # Need to get new credentials from environment variables
                clientConfig = self._getClientConfig()
                if not clientConfig:
                    print("Error: Environment variables not set")
                    print("Please set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET")
                    print("Example:")
                    print("  export YOUTUBE_CLIENT_ID='your-client-id'")
                    print("  export YOUTUBE_CLIENT_SECRET='your-client-secret'")
                    return False
                
                flow = InstalledAppFlow.from_client_config(
                    clientConfig, 
                    self.SCOPES
                )
                self.credentials = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(self.tokenFile, 'w') as token:
                token.write(self.credentials.to_json())
        
        # Build YouTube API service
        try:
            self.youtubeService = build('youtube', 'v3', credentials=self.credentials)
            print("Successfully authenticated with YouTube API")
            return True
        except Exception as e:
            print(f"Error building YouTube service: {e}")
            return False
    
    def uploadVideo(self, videoPath, title, description="", categoryId="22", privacyStatus="unlisted", tags=None):
        """
        Upload a video to YouTube.
        
        Args:
            videoPath: Path to the video file to upload
            title: Video title
            description: Video description (default: empty)
            categoryId: YouTube category ID (default: 22 = People & Blogs)
            privacyStatus: Privacy setting - "private", "unlisted", or "public" (default: "private")
            tags: List of tags for the video (default: None)
        
        Returns:
            Video ID if successful, None otherwise
        """
        if not self.youtubeService:
            if not self.authenticate():
                return None
        
        videoPath = Path(videoPath)
        if not videoPath.exists():
            print(f"Error: Video file not found: {videoPath}")
            return None
        
        # Build video metadata
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'categoryId': categoryId,
                'tags': tags or []
            },
            'status': {
                'privacyStatus': privacyStatus
            }
        }
        
        # Create media upload request
        media = MediaFileUpload(
            str(videoPath),
            chunksize=-1,
            resumable=True,
            mimetype='video/*'
        )
        
        try:
            print(f"Uploading video: {videoPath.name}")
            print(f"Title: {title}")
            
            # Insert video
            insertRequest = self.youtubeService.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            # Execute upload with progress
            videoId = self._resumableUpload(insertRequest)
            
            if videoId:
                print(f"Video uploaded successfully! Video ID: {videoId}")
                print(f"Watch at: https://www.youtube.com/watch?v={videoId}")
                return videoId
            else:
                print("Upload failed")
                return None
                
        except HttpError as e:
            print(f"An HTTP error occurred: {e}")
            return None
        except Exception as e:
            print(f"An error occurred during upload: {e}")
            return None
    
    def _resumableUpload(self, insertRequest):
        """
        Execute a resumable upload with progress tracking.
        
        Args:
            insertRequest: The insert request object from YouTube API
        
        Returns:
            Video ID if successful, None otherwise
        """
        response = None
        error = None
        retry = 0
        
        while response is None:
            try:
                print("Uploading file...")
                status, response = insertRequest.next_chunk()
                
                if response is not None:
                    if 'id' in response:
                        return response['id']
                    else:
                        raise Exception(f"Upload failed with response: {response}")
                elif status:
                    progress = int(status.progress() * 100)
                    print(f"Upload progress: {progress}%")
                    
            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    error = f"A retriable HTTP error {e.resp.status} occurred:\n{e.content}"
                else:
                    raise
            except Exception as e:
                error = f"A retriable error occurred: {e}"
            
            if error is not None:
                print(error)
                retry += 1
                if retry > 3:
                    print("Max retries exceeded")
                    return None
                
                print(f"Retrying upload... (attempt {retry})")
                error = None
        
        return None


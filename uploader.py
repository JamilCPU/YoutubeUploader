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
    
    def __init__(self, tokenFile='token.json', progressCallback=None):
        """
        Initialize the YouTube uploader.
        
        Args:
            tokenFile: Path to store/load OAuth token
            progressCallback: Callback function(progress) called with upload progress (0-100)
        """
        self.tokenFile = Path(tokenFile)
        self.youtubeService = None
        self.credentials = None
        self.progressCallback = progressCallback
    
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
    
    def testCredentials(self):
        """
        Test if environment variables are set and API connection works.
        This performs a simple API call to verify authentication without uploading.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        # Check environment variables first
        clientId = os.getenv('YOUTUBE_CLIENT_ID')
        clientSecret = os.getenv('YOUTUBE_CLIENT_SECRET')
        clientProjectId = os.getenv('YOUTUBE_PROJECT_ID')
        
        if not clientId or not clientSecret or not clientProjectId:
            missing = []
            details = []
            
            if not clientId:
                missing.append("YOUTUBE_CLIENT_ID")
                details.append("YOUTUBE_CLIENT_ID: (not set)")
            else:
                # Show partial value for security (first 8 chars + ...)
                maskedId = clientId[:8] + "..." if len(clientId) > 8 else clientId
                details.append(f"YOUTUBE_CLIENT_ID: {maskedId} (set)")
            
            if not clientSecret:
                missing.append("YOUTUBE_CLIENT_SECRET")
                details.append("YOUTUBE_CLIENT_SECRET: (not set)")
            else:
                # Show partial value for security (first 8 chars + ...)
                maskedSecret = clientSecret[:8] + "..." if len(clientSecret) > 8 else clientSecret
                details.append(f"YOUTUBE_CLIENT_SECRET: {maskedSecret} (set)")
            
            if not clientProjectId:
                missing.append("YOUTUBE_PROJECT_ID")
                details.append("YOUTUBE_PROJECT_ID: (not set)")
            else:
                details.append(f"YOUTUBE_PROJECT_ID: {clientProjectId} (set)")
            
            message = f"Missing environment variables: {', '.join(missing)}\n\nCurrent values:\n" + "\n".join(details)
            return (False, message)
        
        # Try to authenticate
        if not self.authenticate():
            return (False, "Authentication failed. Check your credentials and OAuth configuration.")
        
        # Test API connection with a simple call (get channel info)
        try:
            # Use channels().list() with 'mine' to get current user's channel info
            # This is a simple read operation that doesn't require uploading
            request = self.youtubeService.channels().list(
                part='snippet',
                mine=True
            )
            response = request.execute()
            
            if response.get('items'):
                channelTitle = response['items'][0]['snippet']['title']
                return (True, f"Credentials valid! Connected to YouTube channel: {channelTitle}")
            else:
                return (True, "Credentials valid! API connection successful. (No channel info available)")
                
        except HttpError as e:
            errorMsg = str(e)
            if "GOCSPX" in errorMsg:
                return (False, f"OAuth error: {errorMsg}\n\nThis usually means:\n1. Invalid CLIENT_ID, CLIENT_SECRET, or PROJECT_ID\n2. OAuth consent screen not configured\n3. Token needs to be refreshed")
            return (False, f"API error: {errorMsg}")
        except Exception as e:
            return (False, f"Error testing API connection: {str(e)}")
    
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
                try:
                    self.credentials.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    print("Token refresh failed. You may need to re-authenticate.")
                    # Delete invalid token file and try to get new credentials
                    if self.tokenFile.exists():
                        self.tokenFile.unlink()
                        print("Deleted invalid token file. Will attempt to get new credentials.")
                    self.credentials = None
            else:
                # Need to get new credentials from environment variables
                clientConfig = self._getClientConfig()
                if not clientConfig:
                    print("Error: Environment variables not set")
                    print("Please set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, and YOUTUBE_PROJECT_ID")
                    print("Example:")
                    print("  export YOUTUBE_CLIENT_ID='your-client-id'")
                    print("  export YOUTUBE_CLIENT_SECRET='your-client-secret'")
                    print("  export YOUTUBE_PROJECT_ID='your-project-id'")
                    return False
                
                try:
                    flow = InstalledAppFlow.from_client_config(
                        clientConfig, 
                        self.SCOPES
                    )
                    self.credentials = flow.run_local_server(port=0)
                except Exception as e:
                    errorMsg = str(e)
                    print(f"Error during OAuth authentication: {errorMsg}")
                    if "GOCSPX" in errorMsg or "invalid_grant" in errorMsg.lower():
                        print("\nOAuth authentication failed. This usually means:")
                        print("1. The OAuth credentials (CLIENT_ID, CLIENT_SECRET, PROJECT_ID) are incorrect")
                        print("2. The OAuth consent screen is not properly configured")
                        print("3. You need to delete token.json and re-authenticate")
                        if self.tokenFile.exists():
                            print(f"\nTry deleting {self.tokenFile} and running again.")
                    return False
            
            # Save credentials for next run
            with open(self.tokenFile, 'w') as token:
                token.write(self.credentials.to_json())
        
        # Build YouTube API service
        try:
            self.youtubeService = build('youtube', 'v3', credentials=self.credentials)
            print("Successfully authenticated with YouTube API")
            return True
        except Exception as e:
            errorMsg = str(e)
            print(f"Error building YouTube service: {errorMsg}")
            if "GOCSPX" in errorMsg or "invalid_grant" in errorMsg.lower():
                print("\nAuthentication error detected. This usually means:")
                print("1. The OAuth credentials are invalid or expired")
                print("2. The PROJECT_ID doesn't match your Google Cloud project")
                print("3. The OAuth consent screen needs to be reconfigured")
                print(f"\nTry deleting {self.tokenFile} and re-authenticating.")
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
            errorMsg = str(e)
            print(f"An HTTP error occurred: {e}")
            if "GOCSPX" in errorMsg or "invalid_grant" in errorMsg.lower() or "unauthorized" in errorMsg.lower():
                print("\nAuthentication error during upload. The token may be invalid.")
                print(f"Try deleting {self.tokenFile} and re-authenticating.")
                # Clear invalid credentials
                self.credentials = None
                self.youtubeService = None
            return None
        except Exception as e:
            errorMsg = str(e)
            print(f"An error occurred during upload: {e}")
            if "GOCSPX" in errorMsg:
                print("\nOAuth error detected. This usually means:")
                print("1. Invalid or expired OAuth credentials")
                print("2. PROJECT_ID mismatch with Google Cloud Console")
                print(f"3. Try deleting {self.tokenFile} and re-authenticating")
                # Clear invalid credentials
                self.credentials = None
                self.youtubeService = None
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
                    if self.progressCallback:
                        self.progressCallback(progress)
                    
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

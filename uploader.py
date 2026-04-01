"""
YouTube video uploader using the YouTube Data API v3.
Handles authentication and video uploads to YouTube.
"""
import os
import logging
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# Create logger at module level
logger = logging.getLogger(__name__)


class Uploader:
    """
    Handles uploading videos to YouTube using the YouTube Data API v3.
    """
    
    # YouTube API scopes required for uploading videos
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    
    def __init__(self, tokenFile=None, progressCallback=None):
        """
        Initialize the YouTube uploader.
        
        Args:
            tokenFile: Path to store/load OAuth token (default: uses DATA_DIR/token.json or ./token.json)
            progressCallback: Callback function(progress) called with upload progress (0-100)
        """
        import os
        if tokenFile is None:
            # Use DATA_DIR environment variable if set (for Docker), otherwise use current directory
            dataDir = Path(os.getenv('DATA_DIR', '.'))
            tokenFile = dataDir / 'token.json'
        self.tokenFile = Path(tokenFile)
        self.youtubeService = None
        self.credentials = None
        self.progressCallback = progressCallback
        self.uploadAcceptedCallback = None  # Callback when YouTube accepts upload
    
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
        Uses youtube.readonly scope for testing (separate from upload scope).
        
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
        
        # Create credentials and API service client with readonly scope for testing
        # This uses the Google API library to authenticate and make API calls
        # We use a separate scope (youtube.readonly) so testing doesn't affect the main uploader
        testScopes = ['https://www.googleapis.com/auth/youtube.readonly']
        testTokenFile = Path('token.readonly.json')  # Separate token file for readonly scope
        
        try:
            # Get client config from environment variables
            clientConfig = self._getClientConfig()
            if not clientConfig:
                return (False, "Failed to get client configuration from environment variables.")
            
            # Try to load existing readonly token
            testCredentials = None
            if testTokenFile.exists():
                try:
                    testCredentials = Credentials.from_authorized_user_file(
                        str(testTokenFile),
                        testScopes
                    )
                except Exception:
                    # If token is invalid, delete it
                    testTokenFile.unlink()
                    testCredentials = None
            
            # Authenticate if needed (using Google's OAuth library)
            if not testCredentials or not testCredentials.valid:
                if testCredentials and testCredentials.expired and testCredentials.refresh_token:
                    try:
                        testCredentials.refresh(Request())
                    except Exception:
                        testTokenFile.unlink() if testTokenFile.exists() else None
                        testCredentials = None
                
                if not testCredentials or not testCredentials.valid:
                    # Get new credentials with readonly scope (opens browser for OAuth)
                    flow = InstalledAppFlow.from_client_config(clientConfig, testScopes)
                    testCredentials = flow.run_local_server(port=0)
                    
                    # Save readonly token
                    with open(testTokenFile, 'w') as token:
                        token.write(testCredentials.to_json())
            
            # Build YouTube API service client using Google's library
            # This creates a client object that can make API calls
            testService = build('youtube', 'v3', credentials=testCredentials)
            
            # Test API connection with channels().list() using readonly scope
            request = testService.channels().list(
                part='snippet',
                mine=True
            )
            response = request.execute()
            
            if response.get('items'):
                channelTitle = response['items'][0]['snippet']['title']
                return (True, f"Credentials valid! Connected to YouTube channel: {channelTitle}")
            else:
                return (True, "Credentials valid! API connection successful using youtube.readonly scope.")
                
        except HttpError as e:
            errorMsg = str(e)
            statusCode = e.resp.status if hasattr(e, 'resp') else None
            if "GOCSPX" in errorMsg:
                return (False, f"OAuth error: {errorMsg}\n\nThis usually means:\n1. Invalid CLIENT_ID, CLIENT_SECRET, or PROJECT_ID\n2. OAuth consent screen not configured\n3. Token needs to be refreshed")
            elif statusCode == 403:
                return (False, f"Permission denied (403): {errorMsg}\n\nMake sure 'youtube.readonly' scope is added to your OAuth consent screen in Google Cloud Console.")
            return (False, f"API error ({statusCode}): {errorMsg}")
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
            logger.info(f"Preparing upload: {videoPath.name}")
            logger.info(f"Title: {title}")
            logger.info(f"Description: {description}")
            logger.info(f"Privacy: {privacyStatus}")
            logger.info(f"Category: {categoryId}")
            logger.info(f"File size: {videoPath.stat().st_size} bytes")
            
            # Insert video
            insertRequest = self.youtubeService.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            logger.info("YouTube API insert request created successfully")
            logger.info(f"Request parts: {','.join(body.keys())}")
            logger.info(f"Media file: {videoPath}")
            logger.info("Starting resumable upload to YouTube...")
            
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
        uploadAccepted = False
        
        while response is None:
            try:
                print("Uploading file...")
                status, response = insertRequest.next_chunk()
                
                # Log when YouTube first accepts the upload (first chunk)
                if not uploadAccepted and status:
                    uploadAccepted = True
                    logger.info("YouTube accepted upload request - upload session established")
                    logger.info(f"Resumable upload URL received from YouTube")
                    logger.info(f"Upload session active, transferring file chunks...")
                    # Notify that upload was accepted
                    if self.uploadAcceptedCallback:
                        try:
                            self.uploadAcceptedCallback()
                        except Exception as e:
                            logger.warning(f"Error in uploadAcceptedCallback: {e}")
                
                if response is not None:
                    if 'id' in response:
                        videoId = response['id']
                        logger.info(f"YouTube API response received - Upload complete")
                        logger.info(f"Video ID: {videoId}")
                        logger.info(f"Video URL: https://www.youtube.com/watch?v={videoId}")
                        logger.info(f"Full API response: {response}")
                        return videoId
                    else:
                        logger.error(f"Upload failed - unexpected response: {response}")
                        raise Exception(f"Upload failed with response: {response}")
                elif status:
                    progress = int(status.progress() * 100)
                    print(f"Upload progress: {progress}%")
                    logger.debug(f"Upload progress: {progress}%")
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

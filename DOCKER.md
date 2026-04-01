# Docker Setup for YouTube Uploader

This guide explains how to run the YouTube Uploader application in a Windows Docker container.

## Prerequisites

1. **Windows Docker Desktop** installed and running
2. **Windows containers enabled** in Docker Desktop (not Linux containers)
3. **Environment variables set** for YouTube API credentials:
   - `YOUTUBE_CLIENT_ID`
   - `YOUTUBE_CLIENT_SECRET`
   - `YOUTUBE_PROJECT_ID`

## Quick Start

### 0. Validate Setup (Optional)

Run the validation script to check prerequisites:

```powershell
.\validate-docker-setup.ps1
```

This will verify:
- Docker installation and status
- Windows container support
- Required environment variables
- Required files and directories

### 1. Set Environment Variables

Set the required environment variables in your PowerShell session or system environment:

```powershell
$env:YOUTUBE_CLIENT_ID="your-client-id"
$env:YOUTUBE_CLIENT_SECRET="your-client-secret"
$env:YOUTUBE_PROJECT_ID="your-project-id"
```

Or set them permanently in Windows System Environment Variables.

### 2. Create Data Directory

Create a local directory for persistent storage (config.json and token.json):

```powershell
mkdir data
```

### 3. Build and Run with Docker Compose

```powershell
docker-compose up --build
```

This will:
- Build the Docker image
- Start the container in CLI mode
- Mount `C:\Recordings` to `C:\watch` in the container (adjust in docker-compose.yml if needed)
- Mount `.\data` to `C:\data` for persistent storage

## Configuration

### Volume Mounts

The `docker-compose.yml` file mounts two volumes:

1. **Watched Directory**: 
   - Host: `C:\Recordings` (default)
   - Container: `C:\watch`
   - Change the `source` path in `docker-compose.yml` to point to your recording directory

2. **Data Directory**:
   - Host: `.\data` (relative to project directory)
   - Container: `C:\data`
   - Stores `config.json` and `token.json` for persistence

### Running in GUI Mode

To run the application with GUI, uncomment the `command` line in `docker-compose.yml`:

```yaml
command: ["python", "main.py", "--gui"]
```

**Note**: GUI mode in Windows containers may require additional setup for display access. For local Windows Docker Desktop, GUI apps may work directly, but remote access typically requires RDP or VNC.

### Running in CLI Mode

CLI mode is the default. The container will:
- Watch the mounted directory for new video files
- Automatically upload finished files to YouTube
- Log output to the console

## Manual Docker Commands

### Build the Image

```powershell
docker build -t youtube-uploader .
```

### Run Container (CLI Mode)

```powershell
docker run -it --rm `
  -v C:\Recordings:C:\watch `
  -v ${PWD}\data:C:\data `
  -e YOUTUBE_CLIENT_ID=$env:YOUTUBE_CLIENT_ID `
  -e YOUTUBE_CLIENT_SECRET=$env:YOUTUBE_CLIENT_SECRET `
  -e YOUTUBE_PROJECT_ID=$env:YOUTUBE_PROJECT_ID `
  -e DATA_DIR=C:\data `
  -e WATCH_DIR=C:\watch `
  youtube-uploader
```

### Run Container (GUI Mode)

```powershell
docker run -it --rm `
  -v C:\Recordings:C:\watch `
  -v ${PWD}\data:C:\data `
  -e YOUTUBE_CLIENT_ID=$env:YOUTUBE_CLIENT_ID `
  -e YOUTUBE_CLIENT_SECRET=$env:YOUTUBE_CLIENT_SECRET `
  -e YOUTUBE_PROJECT_ID=$env:YOUTUBE_PROJECT_ID `
  -e DATA_DIR=C:\data `
  -e WATCH_DIR=C:\watch `
  youtube-uploader python main.py --gui
```

## Environment Variables

The following environment variables are used by the application:

| Variable | Description | Required |
|----------|-------------|----------|
| `YOUTUBE_CLIENT_ID` | Google OAuth Client ID | Yes |
| `YOUTUBE_CLIENT_SECRET` | Google OAuth Client Secret | Yes |
| `YOUTUBE_PROJECT_ID` | Google Cloud Project ID | Yes |
| `DATA_DIR` | Directory for config.json and token.json | No (defaults to `C:\data`) |
| `WATCH_DIR` | Directory to watch for video files | No (defaults to `C:\watch`) |

## Troubleshooting

### Container Won't Start

1. **Check Windows containers are enabled**:
   - Right-click Docker Desktop icon → Switch to Windows containers
   - Verify in Docker Desktop settings

2. **Verify environment variables are set**:
   ```powershell
   echo $env:YOUTUBE_CLIENT_ID
   echo $env:YOUTUBE_CLIENT_SECRET
   echo $env:YOUTUBE_PROJECT_ID
   ```

3. **Check volume paths exist**:
   - Ensure `C:\Recordings` exists (or update docker-compose.yml)
   - Ensure `.\data` directory exists

### Authentication Errors

1. **Delete token.json**:
   ```powershell
   Remove-Item .\data\token.json
   ```
   This will force re-authentication on next run.

2. **Verify OAuth credentials**:
   - Check that environment variables are correctly set
   - Verify credentials in Google Cloud Console

### File Watching Not Working

1. **Check volume mount**:
   - Verify the watched directory is correctly mounted
   - Check file permissions on the host directory

2. **Check logs**:
   ```powershell
   docker-compose logs -f
   ```

### GUI Not Displaying

1. **For local Docker Desktop**: GUI should work directly
2. **For remote access**: Consider using RDP or VNC server in the container
3. **Alternative**: Use CLI mode for headless operation

## Stopping the Container

### Using Docker Compose

```powershell
docker-compose down
```

### Using Docker Run

Press `Ctrl+C` to stop, or in another terminal:

```powershell
docker stop <container-id>
```

## Data Persistence

The `data` directory on your host machine contains:
- `config.json`: Application configuration (last watched directory)
- `token.json`: OAuth authentication token

These files persist across container restarts, so you won't need to re-authenticate unless the token expires.

## Building for Production

For production deployments, consider:

1. **Using a specific Windows base image tag** instead of `latest`
2. **Setting up health checks** in docker-compose.yml
3. **Configuring log rotation** for container logs
4. **Using Docker secrets** for sensitive environment variables (if using Docker Swarm)

## Additional Resources

- [Docker Desktop for Windows Documentation](https://docs.docker.com/desktop/windows/)
- [Windows Containers Documentation](https://docs.microsoft.com/en-us/virtualization/windowscontainers/)
- [YouTube Data API Documentation](https://developers.google.com/youtube/v3)

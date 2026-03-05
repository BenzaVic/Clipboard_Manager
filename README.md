# Clipboard Manager

A lightweight desktop application that automatically records everything you copy and stores it in a searchable, organized history. Instead of relying on a single clipboard slot, the app keeps a running list of your recent snippets so you can quickly find, pin, and reuse text and images at any time. It runs quietly in the background, captures new clipboard content in real time, and provides a fast interface for browsing and copying items back to the system clipboard.

## Features

- **Automatic Clipboard Monitoring**: Captures text and images as you copy them
- **Search Functionality**: Quickly find items in your clipboard history
- **Pin Important Items**: Keep frequently used items at the top
- **Image Support**: Handles both text and image clipboard content with thumbnails
- **System Tray Integration**: Runs in the background with easy access
- **Duplicate Prevention**: Avoids storing duplicate content
- **History Management**: Configurable history size with automatic cleanup
- **Cross-Platform**: Works on Windows, macOS, and Linux


### Requirements

- Python 3.8 or higher
- PyQt6
- SQLite3 (usually included with Python)

### Installation

1. Clone or download this repository
2. Install dependencies:
   ```bash
   pip install PyQt6
   ```

### Run the app

```bash
python main.py
```

The application will start and appear in your system tray. Click the tray icon to open the main window.

## Project Structure

```
clipboard_manager/
├── main.py              # Main application code
├── README.md            # This file
├── clipboard_history.db # SQLite database (created automatically)
└── images/              # Stored image files (created automatically)
```

## Features in Detail

### Clipboard Monitoring
- Monitors clipboard every 300ms for new content
- Automatically detects text vs image content
- Prevents duplicate entries using SHA256 hashing for images

### Search and Filter
- Real-time search through clipboard history
- Search works on text content only (images show as thumbnails)

### Pinning System
- Pin important items to keep them at the top
- Pinned items are never automatically deleted
- Visual indicator (⭐) shows pinned status

### Image Handling
- Saves images as PNG files in the `images/` directory
- Displays thumbnails in the main interface
- Supports copying images back to clipboard

### Settings
- Configure maximum history size (100-10000 items)
- History automatically cleans up old unpinned items

### System Tray
- Minimizes to tray for background operation
- Quick access to show window, clear history, or quit

## What I Learnt

This project taught me several important concepts in desktop application development:

1. **PyQt6 GUI Development**: Building responsive user interfaces with proper event handling
2. **Clipboard Management**: Working with system clipboard APIs and MIME data
3. **Database Design**: Using SQLite for persistent storage with proper indexing and cleanup
4. **Image Processing**: Handling QImage objects, thumbnails, and file I/O
5. **System Tray Integration**: Creating background applications with tray icons
6. **Error Handling**: Robust error handling for file operations and database interactions
7. **Settings Management**: Using QSettings for persistent application configuration
8. **Memory Management**: Implementing automatic cleanup to prevent unbounded growth

## Possible Extensions

- **Keyboard Shortcuts**: Global hotkeys for quick access
- **Categories/Tags**: Organize clipboard items into categories
- **Cloud Sync**: Sync clipboard history across devices
- **Advanced Search**: Search within images using OCR
- **Export/Import**: Backup and restore clipboard history
- **Themes**: Dark/light mode support
- **Auto-start**: Automatically start on system boot
- **Encryption**: Encrypt sensitive clipboard data
- **Plugins**: Extensible architecture for custom content types

## Technical Details

- **Database**: SQLite with automatic schema creation
- **Image Storage**: PNG format with SHA256 deduplication
- **UI Framework**: PyQt6 with responsive table widget
- **Memory Management**: Configurable history limits with automatic cleanup
- **Error Handling**: Comprehensive try/catch blocks with user feedback

## License

This project is open source and available under the MIT License.


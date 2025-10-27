# Media Sending Documentation

## 1. Upload File Endpoint

Upload media files to be used in chat messages.

**Endpoint:** `POST /api/chat/upload-media/`  
**Authentication:** Required (Department Staff only)

### Request Format
```http
POST /api/chat/upload-media/
Content-Type: multipart/form-data
Authorization: Bearer <token>

conversation_id: 123
caption: Optional caption for the file
file: [binary file data]
```

### Response Format
```json
{
  "success": true,
  "file_url": "https://example.com/media/chat/2024/01/15/document.pdf",
  "filename": "document.pdf",
  "file_type": "document",
  "file_size": 1024000,
  "caption": "Optional caption",
  "conversation_id": 123
}
```

### Supported File Types
- **Images:** JPEG, PNG, GIF
- **Documents:** PDF, TXT, DOC, DOCX
- **Videos:** MP4, AVI, MOV
- **Audio:** MP3, WAV, MPEG

### File Size Limit
Maximum file size: 10MB

---

## 2. WebSocket Media Message

Send the uploaded file as a chat message via WebSocket.

**WebSocket URL:** `ws://localhost:8000/ws/chat/`

### Request Format
```json
{
  "type": "media",
  "conversation_id": 123,
  "file_url": "https://example.com/media/chat/2024/01/15/document.pdf",
  "filename": "document.pdf",
  "file_type": "document",
  "caption": "Optional caption for the document"
}
```

### Response Format
```json
{
  "type": "chat_message",
  "message": {
    "id": 456,
    "conversation_id": 123,
    "sender_type": "staff",
    "sender_name": "John Doe",
    "message_type": "document",
    "content": "Optional caption for the document",
    "media_url": "https://example.com/media/chat/2024/01/15/document.pdf",
    "media_filename": "document.pdf",
    "created_at": "2024-01-15T10:30:00Z",
    "guest_info": {
      "name": "Guest Name",
      "room_number": "101"
    }
  }
}
```

### Valid file_type Values
- `"image"` - For images
- `"document"` - For documents
- `"video"` - For videos
- `"audio"` - For audio files

---

## Complete Flow Example

1. **Upload file:**
```bash
curl -X POST \
  http://localhost:8000/api/chat/upload-media/ \
  -H 'Authorization: Bearer your-token' \
  -F 'conversation_id=123' \
  -F 'caption=Hotel menu' \
  -F 'file=@menu.pdf'
```

2. **Send via WebSocket:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat/');

ws.send(JSON.stringify({
  type: 'media',
  conversation_id: 123,
  file_url: 'https://example.com/media/chat/2024/01/15/menu.pdf',
  filename: 'menu.pdf',
  file_type: 'document',
  caption: 'Hotel menu'
}));
```

**Note:** For 'service' conversation types, the media will also be sent to the guest via WhatsApp automatically.
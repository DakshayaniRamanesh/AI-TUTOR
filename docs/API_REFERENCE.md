# API Reference

## 1. `/generate` (POST)
Submits a PDF file and text prompt for video generation.

**Request**: `multipart/form-data`
- `pdf`: Binary File (PDF <= 20 pages)
- `prompt`: String (Prompt description)

**Response**: `200 OK`
```json
{
  "job_id": "job_123456789",
  "status": "processing",
  "message": "Video generation pipeline started."
}
```

---

## 2. `/status/{job_id}` (GET)
Retrieves current pipeline status and job details.

**Response**: `200 OK`
```json
{
  "job_id": "job_123456789",
  "status": "done",
  "step": "uploader",
  "progress_percentage": 100,
  "video_url": "https://bucket.nyc3.digitaloceanspaces.com/videos/job_123456789.mp4",
  "error": null
}
```

---

## 3. `/annotate` (POST)
Submits canvas annotation highlights and question for video extending.

**Request**: `application/json`
```json
{
  "job_id": "job_123456789",
  "annotations": [
    {
      "timestamp": 14.5,
      "canvas_image": "data:image/png;base64,...",
      "paths": [[{"x": 0.2, "y": 0.3}, {"x": 0.4, "y": 0.5}]],
      "comment": "Can you explain this step in more detail?"
    }
  ]
}
```

**Response**: `200 OK`
```json
{
  "job_id": "job_123456789",
  "status": "updated",
  "new_version": 2,
  "video_url": "https://bucket.nyc3.digitaloceanspaces.com/videos/job_123456789_v2.mp4"
}
```

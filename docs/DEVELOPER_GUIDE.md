# Developer Setup Guide

## Environment Variables

### Backend (`backend/.env`)
```env
GEMINI_API_KEY=your_gemini_api_key
QDRANT_HOST=your_qdrant_host
QDRANT_API_KEY=your_qdrant_api_key
DO_SPACES_KEY=your_do_spaces_key
DO_SPACES_SECRET=your_do_spaces_secret
DO_SPACES_BUCKET=your_do_spaces_bucket_name
DO_SPACES_REGION=nyc3
DO_SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com
FIREBASE_CREDENTIALS_JSON={}
TAVILY_API_KEY=your_tavily_api_key
```

### Frontend (`frontend/.env.local`)
```env
MODAL_BACKEND_URL=https://your-modal-user--manim-app-web-endpoint.modal.run
NEXT_PUBLIC_MOCK_MODE=false
```

## Running Backend Locally
```bash
cd backend
pip install -r requirements.txt
modal serve modal_app.py
```

## Running Frontend Locally
```bash
cd frontend
npm install
npm run dev
```

## Mock Mode
If you do not have Modal or Qdrant keys configured yet, you can test the frontend in mock mode by setting `NEXT_PUBLIC_MOCK_MODE=true` in `frontend/.env.local` or appending `?mock=true` to the URL.

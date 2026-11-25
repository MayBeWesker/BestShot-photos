# BestShot-photos

English | [简体中文](README.zh-CN.md)

BestShot-photos is a privacy-first travel photo organizer that runs locally. It groups similar photos, ranks them by quality, and creates a nine-photo story with a ready-to-use social media caption.

## Core Features

- Import JPG, JPEG, PNG, WebP, HEIC, and HEIF images in one batch
- Group similar scenes and rank groups by their best photo
- Score photos by sharpness, exposure, color, composition, and visual cleanliness
- Build a coherent nine-photo story with an intentional layout
- Replace selections manually or with AI assistance, then download the final photos as a ZIP archive
- Blend the best parts of burst photos and export the result as a high-resolution PNG

> Photo organization runs locally by default. Only compressed thumbnails of candidate photos are sent to the user-configured vision API when the user explicitly generates a social media post. Original photos stay local, and the API key is read only by the local backend.

## Windows Quick Start

Install Python 3.11+ and Node.js 20+, then double-click one of these files in the project root:

- `Start BestShot.bat`: start the services and open the app in your browser
- `Stop BestShot.bat`: stop the background services

Dependencies are installed automatically on the first launch, so the initial startup may take a few minutes.

## Configure AI Post Generation (Optional)

1. Copy `.env.example` to `.env`.
2. Add your API key as `DEEPSEEK_API_KEY` in `.env`.
3. Restart BestShot-photos and click **Generate Post** after photo classification is complete.

## Development

Start the backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

## Verification

```powershell
cd backend
.\.venv\Scripts\python -m pytest -q

cd ..\frontend
npm run build
```

## Tech Stack

- Frontend: React, TypeScript, and Konva
- Backend: FastAPI and OpenCV
- Local data: `.bestshot-data/`

## License

[MIT](LICENSE)

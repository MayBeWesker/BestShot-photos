# BestShot-photos

BestShot-photos 是一款本地运行、隐私优先的旅行照片整理工具。它可以自动归类相似照片、按质量排序，并从旅行照片中生成适合朋友圈发布的九图与文案。

## 核心功能

- 批量导入 JPG、JPEG、PNG、WebP、HEIC 和 HEIF 图片
- 自动归类相似场景，并按每组最高分排序
- 根据清晰度、曝光、色彩、构图和画面简洁度评估照片质量
- 从候选照片中生成具有故事线和布局逻辑的朋友圈九图
- 支持手动或智能换组，并将最终九张原图打包下载
- 支持连拍照片的局部融合与高清 PNG 导出

> 照片整理默认在本地完成。只有用户主动生成朋友圈时，候选照片的压缩缩略图才会发送到用户配置的视觉 API；原图和 API Key 不会上传到前端或由项目保存。

## Windows 快速启动

请先安装 Python 3.11+ 和 Node.js 20+，然后双击项目根目录中的：

- `启动 BestShot.bat`：启动服务并打开浏览器
- `停止 BestShot.bat`：停止后台服务

首次启动会自动安装依赖，所需时间可能稍长。

## 配置朋友圈生成（可选）

1. 将 `.env.example` 复制为 `.env`。
2. 在 `.env` 中填写 `DEEPSEEK_API_KEY`。
3. 重启 BestShot-photos，在分类完成后点击“生成朋友圈”。

## 开发运行

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

前端（另一个终端）：

```powershell
cd frontend
npm install
npm run dev
```

## 验证

```powershell
cd backend
.\.venv\Scripts\python -m pytest -q

cd ..\frontend
npm run build
```

## 技术栈

- 前端：React、TypeScript、Konva
- 后端：FastAPI、OpenCV
- 数据：保存在本地 `.bestshot-data/` 目录

## License

[MIT](LICENSE)

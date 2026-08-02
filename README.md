# 🖼️ 在线图片工具

一个基于 Flask + rembg 的在线图片处理工具，支持：

- 📐 **调整尺寸** — 像素 / 百分比 / 预设尺寸
- 🔄 **格式转换** — PNG / JPEG / WebP / BMP
- ⬜ **白底照片** — AI 抠图 + 白色背景
- 📸 **证件照制作** — 一寸、二寸等标准尺寸，支持白/红/蓝背景

## 快速开始

```bash
pip install -r requirements.txt
python3 app.py --port 8613
```

浏览器打开 http://127.0.0.1:8613

## Docker 部署

```bash
docker build -t img-tool .
docker run -p 8613:8613 -v ~/.u2net:/root/.u2net img-tool
```

## 技术栈

- **后端**: Flask + Pillow + rembg (AI 背景移除)
- **前端**: 原生 HTML/CSS/JS，支持暗色模式
- **AI 模型**: u2netp (4.4MB 轻量) / u2net_human_seg (168MB 人像专用)

## 项目结构

```
├── app.py           # Flask 后端
├── image_engine.py  # 图片处理核心
├── requirements.txt
└── static/
    ├── index.html   # 前端页面
    ├── app.js       # 前端逻辑
    └── style.css    # 样式
```

## 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--port` | 8613 | 服务端口 |
| `--host` | 127.0.0.1 | 绑定地址 |
| `--no-browser` | false | 不自动打开浏览器 |

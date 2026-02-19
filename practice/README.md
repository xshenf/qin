# 专业吉他练习应用

基于先进 MIR（Music Information Retrieval）技术的音频-乐谱对齐练习系统。

## 技术栈

- **音频 I/O**: PortAudio (sounddevice)
- **多音检测**: Basic Pitch (Spotify)
- **单音检测**: CREPE (CNN)
- **节奏检测**: madmom (RNN)
- **乐谱对齐**: Online DTW
- **ML 推理**: ONNX Runtime
- **UI 框架**: PySide6 (Qt)

## 快速开始

```bash
# 安装核心依赖
pip install -e .

# 安装 MIR 依赖
pip install -e ".[mir]"

# 运行
python -m src.main
```

## 项目结构

```
src/
├── audio/          # 音频 I/O 和预处理
├── mir/            # 音高、节奏、Chroma 检测
├── engine/         # 练习引擎和乐谱对齐
├── ui/             # PySide6 GUI
└── main.py         # 入口
```

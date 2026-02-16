"""
乐谱渲染组件 — 基于 QWebEngineView + AlphaTab

通过 QWebChannel 桥接 Python ↔ JavaScript，实现：
- 加载 GP/MusicXML 乐谱文件
- 播放/暂停/停止控制
- 实时光标位置同步
- 音符命中/错误着色反馈
"""

import os
import json
import base64
from pathlib import Path
from typing import Optional, Callable

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt, QObject, Slot, Signal, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel


class JsBridge(QObject):
    """Python ↔ JavaScript 桥接对象

    暴露给 JavaScript 端调用的方法通过 @Slot 装饰器标记。
    JavaScript 发来的事件通过信号转发给 Python 端。
    """

    # 信号：从 JavaScript 接收的事件
    scoreLoaded = Signal(dict)     # 乐谱加载完成
    playerReady = Signal()          # 播放器就绪
    playerFinished = Signal()       # 播放完成
    beatChanged = Signal(dict)      # 当前拍子变化（含音符数据）
    positionChanged = Signal(dict)  # 播放位置变化
    fileDropped = Signal(dict)      # 文件拖放
    webReady = Signal()             # Web 页面就绪

    @Slot(str, str)
    def onJsEvent(self, event: str, data: str):
        """JavaScript 调用此方法通知 Python 端事件"""
        try:
            parsed = json.loads(data) if data else {}
        except json.JSONDecodeError:
            parsed = {}

        if event == 'scoreLoaded':
            self.scoreLoaded.emit(parsed)
        elif event == 'playerReady':
            self.playerReady.emit()
        elif event == 'playerFinished':
            self.playerFinished.emit()
        elif event == 'beatChanged':
            self.beatChanged.emit(parsed)
        elif event == 'positionChanged':
            self.positionChanged.emit(parsed)
        elif event == 'fileDropped':
            self.fileDropped.emit(parsed)
        elif event == 'ready':
            self.webReady.emit()


class ScoreView(QWidget):
    """乐谱渲染组件

    封装 QWebEngineView + AlphaTab，提供 Pythonic API。

    事件:
        on_score_loaded(info: dict)  — 乐谱加载完成
        on_beat_changed(data: dict)  — 当前拍子变化
        on_position_changed(data: dict) — 播放位置变化
    """

    # 转发信号
    scoreLoaded = Signal(dict)
    beatChanged = Signal(dict)
    positionChanged = Signal(dict)
    playerFinished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._setup_bridge()
        self._load_html()
        self._is_ready = False

    def _setup_ui(self):
        """构建 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.web_view = QWebEngineView()
        self.web_view.setMinimumHeight(200)

        # 允许本地文件访问
        settings = self.web_view.page().settings()
        from PySide6.QtWebEngineCore import QWebEngineSettings
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

        layout.addWidget(self.web_view)

    def _setup_bridge(self):
        """设置 QWebChannel 桥接"""
        self.bridge = JsBridge()
        self.channel = QWebChannel()
        self.channel.registerObject('bridge', self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        # 连接信号
        self.bridge.webReady.connect(self._on_web_ready)
        self.bridge.scoreLoaded.connect(self._on_score_loaded)
        self.bridge.beatChanged.connect(self.beatChanged.emit)
        self.bridge.positionChanged.connect(self.positionChanged.emit)
        self.bridge.playerFinished.connect(self.playerFinished.emit)
        self.bridge.fileDropped.connect(self._on_file_dropped)

    def _load_html(self):
        """加载 AlphaTab HTML 模板"""
        html_path = Path(__file__).parent / 'score_viewer.html'
        if html_path.exists():
            self.web_view.setUrl(QUrl.fromLocalFile(str(html_path)))
        else:
            print(f"[ScoreView] HTML 模板未找到: {html_path}")

    def _on_web_ready(self):
        """Web 页面就绪"""
        self._is_ready = True
        print("[ScoreView] AlphaTab 已就绪")

    def _on_score_loaded(self, info: dict):
        """乐谱加载完成"""
        print(f"[ScoreView] 乐谱已加载: {info.get('title', '未命名')} "
              f"by {info.get('artist', '未知')} "
              f"♩={info.get('tempo', '?')}")
        self.scoreLoaded.emit(info)

    def _on_file_dropped(self, info: dict):
        """文件拖放"""
        print(f"[ScoreView] 文件拖放: {info.get('name', '?')} "
              f"({info.get('size', 0)} bytes)")

    # ==== 公开 API ====

    def load_file(self, file_path: str):
        """加载乐谱文件

        支持: .gp3, .gp4, .gp5, .gpx, .gp, .musicxml, .mxl, .xml
        """
        path = Path(file_path)
        if not path.exists():
            print(f"[ScoreView] 文件不存在: {file_path}")
            return

        # 读取文件并通过 base64 传给 JavaScript
        with open(path, 'rb') as f:
            data = f.read()

        b64 = base64.b64encode(data).decode('ascii')
        self._run_js(f"loadScoreData('{b64}')")
        print(f"[ScoreView] 正在加载: {path.name} ({len(data)} bytes)")

    def load_url(self, url: str):
        """通过 URL 加载乐谱"""
        self._run_js(f"loadScore('{url}')")

    def play_pause(self):
        """播放/暂停"""
        self._run_js("playPause()")

    def stop(self):
        """停止"""
        self._run_js("stop()")

    def set_speed(self, speed: float):
        """设置播放速度 (1.0 = 正常)"""
        self._run_js(f"setPlaybackSpeed({speed})")

    def set_volume(self, volume: float):
        """设置音量 (0.0 ~ 1.0)"""
        self._run_js(f"setMasterVolume({volume})")

    def set_track(self, index: int):
        """选择轨道"""
        self._run_js(f"setTrack({index})")

    def set_stave_profile(self, profile: str):
        """设置谱面模式

        Args:
            profile: 'Tab' (六线谱), 'Score' (五线谱),
                     'ScoreTab' (五线谱+六线谱)
        """
        self._run_js(f"setStaveProfile('{profile}')")

    def mark_note(self, note_id: int, color: str):
        """标记音符颜色（练习反馈）

        Args:
            note_id: 音符 ID
            color: CSS 颜色值，如 '#44ff44' (命中) 或 '#ff4444' (错过)
        """
        self._run_js(f"markNote({note_id}, '{color}')")

    def _run_js(self, code: str):
        """执行 JavaScript 代码"""
        self.web_view.page().runJavaScript(code)

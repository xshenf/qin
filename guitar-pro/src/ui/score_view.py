"""
乐谱渲染组件 — 基于 QWebEngineView + AlphaTab

通过 QWebChannel 桥接 Python ↔ JavaScript，实现：
- 加载 GP/MusicXML 乐谱文件
- 播放/暂停/停止控制
- 实时光标位置同步
- 音符命中/错误着色反馈
- 缩放控制、布局模式切换、小节跳转
"""

import os
import json
import base64
from pathlib import Path
from typing import Optional, Callable, List

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
    scoreLoaded = Signal(dict)          # 乐谱加载完成
    playerReady = Signal()              # 播放器就绪
    playerFinished = Signal()           # 播放完成
    beatChanged = Signal(dict)          # 当前拍子变化（含音符数据）
    positionChanged = Signal(dict)      # 播放位置变化
    fileDropped = Signal(dict)          # 文件拖放
    webReady = Signal()                 # Web 页面就绪
    renderProgress = Signal(int)        # 渲染进度 (0-100)
    errorOccurred = Signal(str)         # 错误通知
    zoomChanged = Signal(float)         # 缩放变化
    layoutModeChanged = Signal(str)     # 布局模式变化

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
        elif event == 'renderProgress':
            progress = parsed.get('progress', 0)
            self.renderProgress.emit(progress)
        elif event == 'error':
            message = parsed.get('message', '未知错误')
            self.errorOccurred.emit(message)
        elif event == 'zoomChanged':
            zoom = parsed.get('zoom', 1.0)
            self.zoomChanged.emit(zoom)
        elif event == 'layoutModeChanged':
            mode = parsed.get('mode', 'Page')
            self.layoutModeChanged.emit(mode)


class ScoreView(QWidget):
    """乐谱渲染组件

    封装 QWebEngineView + AlphaTab，提供 Pythonic API。
    具有命令就绪队列：在 Web 页面未就绪时缓冲 JS 命令，就绪后自动执行。

    事件:
        on_score_loaded(info: dict)  — 乐谱加载完成
        on_beat_changed(data: dict)  — 当前拍子变化
        on_position_changed(data: dict) — 播放位置变化
        on_render_progress(progress: int) — 渲染进度
        on_error(message: str) — 错误通知
    """

    # 转发信号
    scoreLoaded = Signal(dict)
    beatChanged = Signal(dict)
    positionChanged = Signal(dict)
    playerFinished = Signal()
    renderProgress = Signal(int)
    errorOccurred = Signal(str)
    zoomChanged = Signal(float)
    layoutModeChanged = Signal(str)

    # 支持的文件格式
    SUPPORTED_EXTENSIONS = {
        '.gp3', '.gp4', '.gp5', '.gpx', '.gp',
        '.musicxml', '.mxl', '.xml',
        '.mid', '.midi',
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_ready = False
        self._pending_commands: List[str] = []
        self._current_zoom = 1.0
        self._current_layout = 'Page'
        self._score_info: Optional[dict] = None

        self._setup_ui()
        self._setup_bridge()
        self._load_html()

    def _setup_ui(self):
        """构建 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.web_view = QWebEngineView()
        self.web_view.setMinimumHeight(200)

        # 允许本地文件访问
        settings = self.web_view.page().settings()
        from PySide6.QtWebEngineCore import QWebEngineSettings
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )

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
        self.bridge.renderProgress.connect(self.renderProgress.emit)
        self.bridge.errorOccurred.connect(self._on_error)
        self.bridge.zoomChanged.connect(self._on_zoom_changed)
        self.bridge.layoutModeChanged.connect(self._on_layout_mode_changed)

    def _load_html(self):
        """加载 AlphaTab HTML 模板"""
        html_path = Path(__file__).parent / 'score_viewer.html'
        if html_path.exists():
            self.web_view.setUrl(QUrl.fromLocalFile(str(html_path)))
        else:
            print(f"[ScoreView] HTML 模板未找到: {html_path}")

    def _on_web_ready(self):
        """Web 页面就绪，执行所有待执行命令"""
        self._is_ready = True
        print("[ScoreView] AlphaTab 已就绪")

        # 执行所有缓冲的命令
        if self._pending_commands:
            print(f"[ScoreView] 执行 {len(self._pending_commands)} 个缓冲命令")
            for cmd in self._pending_commands:
                self.web_view.page().runJavaScript(cmd)
            self._pending_commands.clear()

    def _on_score_loaded(self, info: dict):
        """乐谱加载完成"""
        self._score_info = info
        title = info.get('title', '未命名')
        artist = info.get('artist', '未知')
        tempo = info.get('tempo', '?')
        bars = info.get('bars', 0)
        print(f"[ScoreView] 乐谱已加载: {title} by {artist} ♩={tempo} ({bars}小节)")
        self.scoreLoaded.emit(info)

    def _on_file_dropped(self, info: dict):
        """文件拖放"""
        name = info.get('name', '?')
        size = info.get('size', 0)
        print(f"[ScoreView] 文件拖放: {name} ({size} bytes)")

    def _on_error(self, message: str):
        """错误通知"""
        print(f"[ScoreView] 错误: {message}")
        self.errorOccurred.emit(message)

    def _on_zoom_changed(self, zoom: float):
        """缩放变化"""
        self._current_zoom = zoom
        self.zoomChanged.emit(zoom)

    def _on_layout_mode_changed(self, mode: str):
        """布局模式变化"""
        self._current_layout = mode
        self.layoutModeChanged.emit(mode)

    # ==== 公开 API ====

    @property
    def is_ready(self) -> bool:
        """Web 页面是否就绪"""
        return self._is_ready

    @property
    def current_zoom(self) -> float:
        """当前缩放比例"""
        return self._current_zoom

    @property
    def current_layout(self) -> str:
        """当前布局模式"""
        return self._current_layout

    @property
    def score_info(self) -> Optional[dict]:
        """当前乐谱信息"""
        return self._score_info

    def load_file(self, file_path: str):
        """加载乐谱文件

        支持: .gp3, .gp4, .gp5, .gpx, .gp, .musicxml, .mxl, .xml, .mid, .midi
        """
        path = Path(file_path)
        if not path.exists():
            print(f"[ScoreView] 文件不存在: {file_path}")
            self.errorOccurred.emit(f"文件不存在: {file_path}")
            return

        # 检查格式
        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            msg = f"不支持的文件格式: {path.suffix}"
            print(f"[ScoreView] {msg}")
            self.errorOccurred.emit(msg)
            return

        # 读取文件并通过 base64 传给 JavaScript
        with open(path, 'rb') as f:
            data = f.read()

        b64 = base64.b64encode(data).decode('ascii')
        self._run_js(f"loadScoreData('{b64}')")
        print(f"[ScoreView] 正在加载: {path.name} ({len(data):,} bytes)")

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
        self._run_js(f"setSpeed({speed})")

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

    def set_zoom(self, scale: float):
        """设置缩放比例

        Args:
            scale: 0.5 ~ 2.0，1.0 为原始大小
        """
        scale = max(0.5, min(2.0, scale))
        if self._current_zoom != scale:
            self._current_zoom = scale
            self._run_js(f"setZoom({scale})")
            self.zoomChanged.emit(scale)

    def zoom_in(self):
        """放大 10%"""
        self.set_zoom(self._current_zoom + 0.1)

    def zoom_out(self):
        """缩小 10%"""
        self.set_zoom(self._current_zoom - 0.1)

    def zoom_reset(self):
        """重置缩放为 100%"""
        self.set_zoom(1.0)

    def set_layout_mode(self, mode: str):
        """设置布局模式

        Args:
            mode: 'Page' (分页视图), 'Horizontal' (水平滚动)
        """
        self._current_layout = mode
        self._run_js(f"setLayoutMode('{mode}')")

    def go_to_bar(self, bar_index: int):
        """跳转到指定小节（1-indexed）

        Args:
            bar_index: 小节编号，从 1 开始
        """
        self._run_js(f"goToBar({bar_index})")

    def mark_note(self, note_id: int, color: str):
        """标记音符颜色（练习反馈）

        Args:
            note_id: 音符 ID
            color: CSS 颜色值，如 '#44ff44' (命中) 或 '#ff4444' (错过)
        """
        self._run_js(f"markNote({note_id}, '{color}')")

    def _run_js(self, code: str):
        """执行 JavaScript 代码

        如果 Web 页面尚未就绪，命令会被缓冲并在就绪后自动执行。
        """
        if self._is_ready:
            self.web_view.page().runJavaScript(code)
        else:
            self._pending_commands.append(code)
            print(f"[ScoreView] 命令已缓冲（页面未就绪）: {code[:60]}...")

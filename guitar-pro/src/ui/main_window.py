"""
PySide6 主窗口 — 实时波形、电平表、音高显示

使用 pyqtgraph 实现高性能实时波形绘制，
集成 AudioIO 和 MIR 引擎的检测结果。
"""

import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QStatusBar,
    QProgressBar, QGroupBox, QSplitter, QFrame,
    QFileDialog, QSlider, QSpinBox, QMenuBar, QMenu
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QFont, QColor, QAction, QKeySequence, QIcon
import pyqtgraph as pg

from src.audio.audio_io import AudioIO
from src.mir.preprocessor import AudioPreprocessor
from src.mir.pitch import PitchTracker
from src.mir.alignment import ScoreFollower
from src.engine.practice import PracticeSession
from src.ui.score_view import ScoreView
from src.ui.icons import get_icon


class WaveformWidget(pg.PlotWidget):
    """实时波形显示组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackground('#1a1a2e')
        self.setTitle("实时波形", color='#e0e0e0', size='11pt')
        self.setLabel('left', '幅度')
        self.setLabel('bottom', '时间 (ms)')
        self.setYRange(-1, 1)
        self.showGrid(x=True, y=True, alpha=0.3)

        # 波形曲线
        pen = pg.mkPen(color='#00d4ff', width=1.5)
        self.curve = self.plot(pen=pen)

        # 配置
        self.display_ms = 100  # 显示最近 100ms

    def update_waveform(self, audio_data: np.ndarray, sample_rate: int):
        """更新波形显示"""
        n = len(audio_data)
        t = np.linspace(0, n / sample_rate * 1000, n)
        self.curve.setData(t, audio_data)


class SpectrumWidget(pg.PlotWidget):
    """实时频谱显示组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackground('#1a1a2e')
        self.setTitle("频谱", color='#e0e0e0', size='11pt')
        self.setLabel('left', '幅度 (dB)')
        self.setLabel('bottom', '频率 (Hz)')
        self.setXRange(50, 2000)
        self.setYRange(-80, 0)
        self.setLogMode(x=True, y=False)
        self.showGrid(x=True, y=True, alpha=0.3)

        # 频谱曲线
        pen = pg.mkPen(color='#ff6b6b', width=1.5)
        self.curve = self.plot(pen=pen)

    def update_spectrum(self, audio_data: np.ndarray, sample_rate: int):
        """更新频谱显示"""
        if len(audio_data) < 1024:
            return

        # 使用 Hanning 窗
        windowed = audio_data[-2048:] * np.hanning(min(2048, len(audio_data[-2048:])))
        n = len(windowed)

        # FFT
        fft = np.fft.rfft(windowed)
        magnitude = np.abs(fft) / n
        magnitude_db = 20 * np.log10(magnitude + 1e-10)
        freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)

        # 只显示 50-4000Hz
        mask = (freqs >= 50) & (freqs <= 4000)
        self.curve.setData(freqs[mask], magnitude_db[mask])


class LevelMeter(QProgressBar):
    """电平表"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOrientation(Qt.Orientation.Vertical)
        self.setMinimum(-80)
        self.setMaximum(0)
        self.setValue(-80)
        self.setTextVisible(True)
        self.setFormat('%v dB')
        self.setFixedWidth(40)
        self.setStyleSheet("""
            QProgressBar {
                border: 1px solid #333;
                border-radius: 3px;
                background: #1a1a2e;
                text-align: center;
                color: #e0e0e0;
                font-size: 9px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff4444, stop:0.15 #ff8800,
                    stop:0.3 #ffcc00, stop:0.6 #44ff44,
                    stop:1 #00cc44
                );
            }
        """)


class PitchDisplay(QLabel):
    """音高显示组件"""

    def __init__(self, parent=None):
        super().__init__("--", parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont("Consolas", 48, QFont.Weight.Bold))
        self.setStyleSheet("""
            QLabel {
                color: #00d4ff;
                background: #16213e;
                border: 2px solid #0f3460;
                border-radius: 10px;
                padding: 20px;
                min-height: 80px;
            }
        """)

    def set_pitch(self, note: str, frequency: float, cents: float):
        """设置检测到的音高"""
        cents_str = f"+{cents:.0f}" if cents >= 0 else f"{cents:.0f}"
        self.setText(f"{note}\n{frequency:.1f} Hz  ({cents_str}¢)")

        # 根据音准偏移着色
        if abs(cents) < 5:
            color = '#44ff44'  # 准确
        elif abs(cents) < 15:
            color = '#ffcc00'  # 偏差小
        else:
            color = '#ff4444'  # 偏差大

        self.setStyleSheet(f"""
            QLabel {{
                color: {color};
                background: #16213e;
                border: 2px solid #0f3460;
                border-radius: 10px;
                padding: 20px;
                min-height: 80px;
            }}
        """)

    def clear_pitch(self):
        """清除显示"""
        self.setText("--")
        self.setStyleSheet("""
            QLabel {
                color: #555;
                background: #16213e;
                border: 2px solid #0f3460;
                border-radius: 10px;
                padding: 20px;
                min-height: 80px;
            }
        """)


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Guitar Pro — 专业吉他练习")
        self.setMinimumSize(1200, 800)
        self.setStyleSheet("""
            QMainWindow {
                background: #0a0a1a;
            }
            QGroupBox {
                color: #e0e0e0;
                border: 1px solid #333;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background: #16213e;
                color: #e0e0e0;
                border: 1px solid #0f3460;
                border-radius: 5px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #1a3a6a;
            }
            QPushButton:pressed {
                background: #0f3460;
            }
            QPushButton:checked {
                background: #e94560;
                border-color: #e94560;
            }
            QLabel {
                color: #e0e0e0;
            }
            QComboBox {
                background: #16213e;
                color: #e0e0e0;
                border: 1px solid #0f3460;
                border-radius: 3px;
                padding: 4px 8px;
            }
            QStatusBar {
                background: #0f0f23;
                color: #888;
            }
        """)

        # 音频引擎
        self.audio = AudioIO(sample_rate=44100, block_size=256)
        
        # 音频预处理 (用于分析)
        self.preprocessor = AudioPreprocessor(self.audio.sample_rate)

        # 音高检测器 (16kHz usually for CREPE, but we pass full rate and let it handle/resample if needed, or initialized with full rate)
        # Note: CREPE models are trained on 16kHz. PitchTracker might need to handle resampling if CREPE is used.
        # Our simple wrapper currently expects 16000 for CREPE.
        self.pitch_tracker = PitchTracker(sample_rate=self.audio.sample_rate)

        # 乐谱跟随 (对齐)
        self.score_follower = ScoreFollower(sample_rate=self.audio.sample_rate)
        
        # 练习引擎
        self.practice_session = PracticeSession()
        self.marked_notes = set() # 记录已命中的音符ID

        # 构建 UI
        self._build_menubar()
        self._build_ui()

        # 定时器：30fps 刷新 UI
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self._update_ui)
        self.ui_timer.setInterval(33)  # ~30fps

    def _build_menubar(self):
        """构建菜单栏"""
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background: #0f0f23;
                color: #cdd6f4;
                padding: 2px 0;
                font-size: 13px;
            }
            QMenuBar::item {
                padding: 4px 12px;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background: #313244;
            }
            QMenu {
                background: #1e1e2e;
                color: #cdd6f4;
                border: 1px solid #313244;
                padding: 4px 0;
            }
            QMenu::item {
                padding: 6px 30px 6px 20px;
            }
            QMenu::item:selected {
                background: #313244;
            }
            QMenu::separator {
                height: 1px;
                background: #313244;
                margin: 4px 8px;
            }
        """)

        # ---- 文件菜单 ----
        file_menu = menubar.addMenu("文件(&F)")

        self.action_open = QAction("📂 打开乐谱...", self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.triggered.connect(self._open_score_file)
        file_menu.addAction(self.action_open)

        file_menu.addSeparator()

        action_quit = QAction("退出(&Q)", self)
        action_quit.setShortcut(QKeySequence("Ctrl+Q"))
        action_quit.triggered.connect(self.close)
        file_menu.addAction(action_quit)

        # ---- 视图菜单 ----
        view_menu = menubar.addMenu("视图(&V)")

        # 谱面模式子菜单
        stave_menu = view_menu.addMenu("谱面模式")
        self.action_tab = QAction("六线谱", self, checkable=True, checked=True)
        self.action_tab.triggered.connect(lambda: self._set_stave("Tab"))
        stave_menu.addAction(self.action_tab)

        self.action_score = QAction("五线谱", self, checkable=True)
        self.action_score.triggered.connect(lambda: self._set_stave("Score"))
        stave_menu.addAction(self.action_score)

        self.action_score_tab = QAction("五线+六线", self, checkable=True)
        self.action_score_tab.triggered.connect(lambda: self._set_stave("ScoreTab"))
        stave_menu.addAction(self.action_score_tab)

        # 布局模式子菜单
        layout_menu = view_menu.addMenu("布局模式")
        self.action_page_layout = QAction("📄 页面视图", self, checkable=True, checked=True)
        self.action_page_layout.triggered.connect(lambda: self._set_layout("Page"))
        layout_menu.addAction(self.action_page_layout)

        self.action_horizontal_layout = QAction("↔ 水平滚动", self, checkable=True)
        self.action_horizontal_layout.triggered.connect(lambda: self._set_layout("Horizontal"))
        layout_menu.addAction(self.action_horizontal_layout)

        view_menu.addSeparator()

        # 缩放
        action_zoom_in = QAction("🔍 放大", self)
        action_zoom_in.setShortcut(QKeySequence("Ctrl+="))
        action_zoom_in.triggered.connect(self._zoom_in)
        view_menu.addAction(action_zoom_in)

        action_zoom_out = QAction("🔍 缩小", self)
        action_zoom_out.setShortcut(QKeySequence("Ctrl+-"))
        action_zoom_out.triggered.connect(self._zoom_out)
        view_menu.addAction(action_zoom_out)

        action_zoom_reset = QAction("🔍 重置缩放", self)
        action_zoom_reset.setShortcut(QKeySequence("Ctrl+0"))
        action_zoom_reset.triggered.connect(self._zoom_reset)
        view_menu.addAction(action_zoom_reset)

        # ---- 播放菜单 ----
        play_menu = menubar.addMenu("播放(&P)")

        self.action_play = QAction("▶ 播放/暂停", self)
        self.action_play.setShortcut(QKeySequence("Space"))
        self.action_play.triggered.connect(self._toggle_playback)
        play_menu.addAction(self.action_play)

        self.action_stop = QAction("⏹ 停止", self)
        self.action_stop.triggered.connect(self._stop_playback)
        play_menu.addAction(self.action_stop)

        # ---- 音频菜单 ----
        audio_menu = menubar.addMenu("音频(&A)")

        # 设备选择子菜单
        self.device_menu = audio_menu.addMenu("输入设备")
        self._populate_device_menu()

        audio_menu.addSeparator()

        self.action_record = QAction("🎤 开始采集", self, checkable=True)
        self.action_record.triggered.connect(self._toggle_recording)
        audio_menu.addAction(self.action_record)

        self.action_practice = QAction("🎸 练习模式", self, checkable=True)
        self.action_practice.setEnabled(False)
        audio_menu.addAction(self.action_practice)

    def _build_ui(self):
        """构建界面"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(8, 4, 8, 8)

        # === 精简工具栏 ===
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        # 打开文件
        self.btn_open = QPushButton("打开")
        self.btn_open.setIcon(get_icon("folder"))
        self.btn_open.setToolTip("打开乐谱文件 (Ctrl+O)")
        self.btn_open.clicked.connect(self._open_score_file)
        toolbar.addWidget(self.btn_open)

        self._add_separator(toolbar)

        # 播放控制
        self.btn_play = QPushButton()
        self.btn_play.setIcon(get_icon("play"))
        self.btn_play.setToolTip("播放/暂停 (Space)")
        self.btn_play.setFixedSize(36, 32)
        self.btn_play.clicked.connect(self._toggle_playback)
        toolbar.addWidget(self.btn_play)

        self.btn_stop = QPushButton()
        self.btn_stop.setIcon(get_icon("stop"))
        self.btn_stop.setToolTip("停止")
        self.btn_stop.setFixedSize(36, 32)
        self.btn_stop.clicked.connect(self._stop_playback)
        toolbar.addWidget(self.btn_stop)

        # 速度控制：SpinBox + Reset
        toolbar.addWidget(QLabel("速度:"))

        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(25, 200)
        self.speed_spin.setValue(100)
        self.speed_spin.setSingleStep(5)
        self.speed_spin.setSuffix("%")
        self.speed_spin.setFixedWidth(85)
        self.speed_spin.setToolTip("播放速度 (25% - 200%)")
        
        # Base64 SVGs for arrows (fill: #e0e0e0)
        _arrow_up = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSIjZTBlMGUwIj48cGF0aCBkPSJNNy40MSAxNS40MUwxMiAxMC44M2w0LjU5IDQuNThMMTggMTRsLTYtNi02IDZ6Ii8+PC9zdmc+"
        _arrow_down = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSIjZTBlMGUwIj48cGF0aCBkPSJNNy40MSA4LjU5TDEyIDEzLjE3bDQuNTktNC41OEwxOCAxMGwtNiA2LTYtNnoiLz48L3N2Zz4="

        from pathlib import Path
        _arrow_dir = Path(__file__).parent / "arrows"
        _up_path = (_arrow_dir / "up.svg").as_posix()
        _down_path = (_arrow_dir / "down.svg").as_posix()

        self.speed_spin.setStyleSheet(f"""
            QSpinBox {{
                background: #16213e;
                color: #e0e0e0;
                border: 1px solid #0f3460;
                border-radius: 3px;
                padding: 4px 4px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 24px;
                border-left: 1px solid #0f3460;
                background: #16213e; 
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background: #1a3a6a;
            }}
            QSpinBox::up-arrow {{ 
                image: url({_up_path});
                width: 10px; height: 10px;
            }}
            QSpinBox::down-arrow {{ 
                image: url({_down_path});
                width: 10px; height: 10px;
            }}
        """)
        self.speed_spin.valueChanged.connect(self._on_speed_changed)
        toolbar.addWidget(self.speed_spin)

        toolbar.addSpacing(6)

        self.btn_speed_reset = QPushButton()
        self.btn_speed_reset.setIcon(get_icon("reset"))
        self.btn_speed_reset.setFixedSize(28, 28)
        self.btn_speed_reset.setToolTip("重置速度 (100%)")
        self.btn_speed_reset.clicked.connect(self._reset_speed)
        toolbar.addWidget(self.btn_speed_reset)

        self._add_separator(toolbar)

        # 缩放
        self.btn_zoom_out = QPushButton()
        self.btn_zoom_out.setIcon(get_icon("zoom_out"))
        self.btn_zoom_out.setFixedSize(32, 32)
        self.btn_zoom_out.setToolTip("缩小 (Ctrl+-)")
        self.btn_zoom_out.clicked.connect(self._zoom_out)
        toolbar.addWidget(self.btn_zoom_out)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setFixedWidth(40)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(self.zoom_label)

        self.btn_zoom_in = QPushButton()
        self.btn_zoom_in.setIcon(get_icon("zoom_in"))
        self.btn_zoom_in.setFixedSize(32, 32)
        self.btn_zoom_in.setToolTip("放大 (Ctrl+=)")
        self.btn_zoom_in.clicked.connect(self._zoom_in)
        toolbar.addWidget(self.btn_zoom_in)

        self._add_separator(toolbar)

        # 谱面模式
        toolbar.addWidget(QLabel("模式:"))
        self.stave_combo = QComboBox()
        self.stave_combo.addItems(["六线谱", "五线谱", "五线+六线"])
        self.stave_combo.setToolTip("选择谱面显示模式")
        self.stave_combo.setFixedWidth(100)
        self.stave_combo.currentIndexChanged.connect(self._on_stave_changed)
        toolbar.addWidget(self.stave_combo)

        toolbar.addStretch()

        # 采集 / 练习
        self.btn_record = QPushButton("采集")
        self.btn_record.setIcon(get_icon("record"))
        self.btn_record.setCheckable(True)
        self.btn_record.setToolTip("开始/停止音频采集")
        self.btn_record.clicked.connect(self._toggle_recording)
        toolbar.addWidget(self.btn_record)

        self.btn_practice = QPushButton("练习")
        self.btn_practice.setIcon(get_icon("practice"))
        self.btn_practice.setCheckable(True)
        self.btn_practice.setEnabled(False)
        self.btn_practice.setToolTip("练习模式（需先开启采集）")
        self.btn_practice.clicked.connect(self._toggle_practice)
        toolbar.addWidget(self.btn_practice)

        self._add_separator(toolbar)

        # 片段录音/播放
        self.btn_snippet_rec = QPushButton()
        self.btn_snippet_rec.setIcon(get_icon("rec_off"))
        self.btn_snippet_rec.setToolTip("录制一小段音频 (需先开启采集)")
        self.btn_snippet_rec.setCheckable(True)
        self.btn_snippet_rec.setEnabled(False)
        self.btn_snippet_rec.clicked.connect(self._toggle_snippet_recording)
        toolbar.addWidget(self.btn_snippet_rec)

        self.btn_snippet_play = QPushButton()
        self.btn_snippet_play.setIcon(get_icon("play"))
        self.btn_snippet_play.setToolTip("播放录制的片段")
        self.btn_snippet_play.setEnabled(False)
        self.btn_snippet_play.clicked.connect(self._play_snippet)
        toolbar.addWidget(self.btn_snippet_play)

        main_layout.addLayout(toolbar)

        # === 中间内容区 ===
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 上半部：乐谱区域（AlphaTab WebView）
        self.score_view = ScoreView()
        self.score_view.scoreLoaded.connect(self._on_score_loaded)
        self.score_view.beatChanged.connect(self._on_beat_changed)
        self.score_view.positionChanged.connect(self._on_position_changed)
        self.score_view.playerFinished.connect(self._on_player_finished)
        self.score_view.renderProgress.connect(self._on_render_progress)
        self.score_view.errorOccurred.connect(self._on_error)
        self.score_view.zoomChanged.connect(self._on_zoom_changed)
        self.score_view.scoreDataReceived.connect(self._on_score_data_received) # Connect new signal
        splitter.addWidget(self.score_view)

        # 下半部：音频分析区域
        analysis_widget = QWidget()
        analysis_layout = QHBoxLayout(analysis_widget)
        analysis_layout.setSpacing(8)

        # 波形 + 频谱
        viz_layout = QVBoxLayout()
        self.waveform = WaveformWidget()
        self.spectrum = SpectrumWidget()
        viz_layout.addWidget(self.waveform)
        viz_layout.addWidget(self.spectrum)
        analysis_layout.addLayout(viz_layout, stretch=3)

        # 右侧面板：电平 + 音高
        right_panel = QVBoxLayout()
        right_panel.setSpacing(10)

        # 电平表
        self.level_meter = LevelMeter()
        level_group = QGroupBox("电平")
        level_layout = QVBoxLayout(level_group)
        level_layout.addWidget(self.level_meter, alignment=Qt.AlignmentFlag.AlignCenter)
        right_panel.addWidget(level_group)

        # 音高显示
        self.pitch_display = PitchDisplay()
        pitch_group = QGroupBox("检测音高")
        pitch_layout = QVBoxLayout(pitch_group)
        pitch_layout.addWidget(self.pitch_display)
        right_panel.addWidget(pitch_group)

        # 练习统计 (Score/Combo)
        stats_group = QGroupBox("练习统计")
        stats_layout = QVBoxLayout(stats_group)
        
        self.label_score = QLabel("得分: 0")
        self.label_score.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFD700;") # Gold
        
        self.label_combo = QLabel("Combo: 0")
        self.label_combo.setStyleSheet("font-size: 24px; font-weight: bold; color: #00FF00;") # Green
        
        stats_layout.addWidget(self.label_score)
        stats_layout.addWidget(self.label_combo)
        right_panel.addWidget(stats_group)

        right_panel.addStretch()
        analysis_layout.addLayout(right_panel, stretch=1)

        splitter.addWidget(analysis_widget)
        splitter.setSizes([300, 400])  # 初始比例
        main_layout.addWidget(splitter)

        # === 状态栏 ===
        self.statusBar().showMessage("就绪 — 请拖入乐谱文件或点击「打开」...")

    @staticmethod
    def _add_separator(layout: QHBoxLayout):
        """添加工具栏分隔线"""
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(20)
        sep.setStyleSheet("color: #333;")
        layout.addWidget(sep)

    def _populate_device_menu(self):
        """填充音频设备菜单"""
        import sounddevice as sd
        devices = sd.query_devices()
        self.device_menu.clear()

        # 默认设备
        action_default = QAction("默认设备", self, checkable=True, checked=True)
        action_default.setData(None)
        action_default.triggered.connect(lambda: self._select_device(None))
        self.device_menu.addAction(action_default)
        self._device_actions = [action_default]

        self.device_menu.addSeparator()

        for i, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                name = f"[{i}] {dev['name']} ({dev['max_input_channels']}ch)"
                action = QAction(name, self, checkable=True)
                action.setData(i)
                action.triggered.connect(lambda checked, idx=i: self._select_device(idx))
                self.device_menu.addAction(action)
                self._device_actions.append(action)

    def _select_device(self, device_index):
        """选择音频设备"""
        # 取消所有选中
        for action in self._device_actions:
            action.setChecked(action.data() == device_index)
        self.audio.device = device_index
        name = '默认设备' if device_index is None else f'设备 {device_index}'
        self.statusBar().showMessage(f"已选择: {name}")

    def _toggle_recording(self, checked):
        """切换音频采集"""
        if checked:
            # 设备已在菜单中选择
            pass
            try:
                self.audio.start()
                self.btn_record.setText("⏹ 停止")
                self.btn_practice.setEnabled(True)
                self.btn_snippet_rec.setEnabled(True)
                self.action_record.setText("⏹ 停止采集")
                self.action_practice.setEnabled(True)
                self.ui_timer.start()
                self.statusBar().showMessage(
                    f"采集中 — SR: {self.audio.sample_rate}Hz, "
                    f"Block: {self.audio.block_size} samples "
                    f"({self.audio.block_size / self.audio.sample_rate * 1000:.1f}ms)"
                )
            except Exception as e:
                self.btn_record.setChecked(False)
                self.statusBar().showMessage(f"错误: {e}")
        else:
            self.audio.stop()
            self.ui_timer.stop()
            self.btn_record.setText("🎤 采集")
            self.action_record.setText("🎤 开始采集")
            self.btn_practice.setEnabled(False)
            self.action_practice.setEnabled(False)
            self.btn_snippet_rec.setEnabled(False)
            self.btn_snippet_rec.setChecked(False)
            self.btn_snippet_rec.setIcon(get_icon("rec_off"))
            self.pitch_display.clear_pitch()
            self.statusBar().showMessage("已停止")

    @Slot()
    def _update_ui(self):
        """UI 刷新（30fps 定时器触发）"""
        if not self.audio.is_running:
            return

        sr = self.audio.sample_rate

        # 获取音频数据 (原始用于波形绘制)
        waveform_data = self.audio.get_buffer(duration_ms=100)
        
        # 预处理数据 (用于频谱和分析)
        # 获取稍长一点的数据以获得更好的频率分辨率
        raw_analysis_data = self.audio.get_buffer(duration_ms=60)
        
        # 使用预处理 (加窗、预加重)
        preprocessed_data = self.preprocessor.process(raw_analysis_data, apply_window=True)
        
        if len(waveform_data) == 0:
            return

        # 更新波形 (使用原始数据，看起来更直观)
        self.waveform.update_waveform(waveform_data, sr)

        # 更新频谱 (使用预处理后数据，更干净)
        # 注意: AudioPreprocessing 可能会降采样、加窗，这会改变数据长度和频率对应关系
        # 我们暂时简单地只取幅度，忽略具体的频率刻度缩放修正，仅展示效果
        # 如果预处理做了降采样，频谱显示的 X 轴需要调整，这里暂时用原始采样率计算
        
        # 为了演示，我们暂时不降采样，或者在 Process 中传参
        # AudioPreprocessor 默认保留 SR/2 的频率，这里简单处理
        
        # 更新频谱
        self.spectrum.update_spectrum(preprocessed_data, sr)

        # 更新电平表
        rms_db = self.audio.get_rms_db()
        self.level_meter.setValue(int(max(-80, rms_db)))

        # TODO: 集成 MIR 引擎后更新音高显示
        # 使用 PitchTracker
        # 2. 音高检测
        freq, conf = 0.0, 0.0
        if rms_db > -50:
             # Predict pitch using the tracker
             freq, conf = self.pitch_tracker.predict(preprocessed_data)
             if freq > 0 and conf > 0.4: # Tweak confidence threshold
                 self._update_pitch_display(freq, conf)
             else:
                 self.pitch_display.clear_pitch()
        else:
             self.pitch_display.clear_pitch()

        # 3. 乐谱跟随 & 练习反馈
        if self.score_follower.is_ready and self.btn_practice.isChecked():
            # 使用稍长的分析帧进行 chroma 提取 (e.g. 100ms or 2048 samples)
            # 这里复用 preprocessed_data (60ms) 可能偏短，但 ChromaExtractor 会自动 padding
            est_time = self.score_follower.process_frame(preprocessed_data)
            
            # 同步给 ScoreView 光标
            self.score_view.set_cursor_time(est_time)
            
            # 视觉反馈 (Visual Feedback)
            if freq > 0 and conf > 0.4:
                self._check_note_hit(est_time, freq)

    def _check_note_hit(self, time: float, detected_freq: float):
        """检查当前时间点的音符是否命中"""
        active_notes = self.score_follower.get_active_notes(time)
        
        import math
        
        for note in active_notes:
            note_id = note.get('id')
            if note_id in self.marked_notes:
                continue
                
            midi_pitch = note.get('pitch')
            target_freq = 440.0 * (2 ** ((midi_pitch - 69) / 12.0))
            
            # 允许 0.5 半音误差 (approx 3%)
            # semitone_diff = 12 * log2(f / target)
            semitone_error = abs(12 * math.log2(detected_freq / target_freq))
            
            if semitone_error < 0.5:
                # 命中!
                self.score_view.mark_note(note_id, '#44ff44') # Green
                self.marked_notes.add(note_id)
                
                # 记录得分
                res = self.practice_session.register_hit(note_id)
                if res:
                    self.label_score.setText(f"得分: {res['score']}")
                    self.label_combo.setText(f"Combo: {res['combo']}")
                    
                    # 可以在 statusBar 显示连击
                    if res['combo'] > 1 and res['combo'] % 5 == 0:
                        self.statusBar().showMessage(f"太棒了! {res['combo']} 连击!", 2000)

    def _toggle_snippet_recording(self, checked):
        """切换片段录音"""
        if checked:
            self.audio.start_snippet_recording()
            self.btn_snippet_rec.setIcon(get_icon("rec_on"))
            self.btn_snippet_play.setEnabled(False)
            self.statusBar().showMessage("正在录制片段...")
        else:
            data = self.audio.stop_snippet_recording()
            self.btn_snippet_rec.setIcon(get_icon("rec_off"))
            if data is not None and len(data) > 0:
                self.btn_snippet_play.setEnabled(True)
                self.statusBar().showMessage(f"片段录制完成 ({len(data)/self.audio.sample_rate:.1f}s)")
            else:
                self.btn_snippet_play.setEnabled(False)
                self.statusBar().showMessage("录制取消或无数据")

    def _play_snippet(self):
        """播放片段"""
        self.audio.play_snippet()
        self.statusBar().showMessage("正在播放录制片段...")

    def _update_pitch_display(self, freq: float, conf: float):
        """Update pitch display with frequency and calculate note info"""
        if freq < 20: return
        
        # Calculate Note Name and Cents
        import math
        # A4 = 440Hz
        midi = 69 + 12 * math.log2(freq / 440.0)
        note_idx = int(round(midi)) % 12
        octave = int(round(midi)) // 12 - 1
        cents = (midi - round(midi)) * 100
        
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        note_name = f"{note_names[note_idx]}{octave}"
        
        self.pitch_display.set_pitch(note_name, freq, cents)

    # Removed _simple_pitch_detect as it is replaced by PitchTracker


    # ==== 乐谱相关 ====

    def _on_score_loaded(self, info: dict):
        """乐谱加载完成回调"""
        title = info.get('title', '未知标题')
        artist = info.get('artist', '未知艺术家')
        self.statusBar().showMessage(f"乐谱已加载: {title} - {artist}")
        
        # 请求获取详细音符数据用于对齐
        # 延迟一点请求，确保 AlphaTab 完全渲染完毕
        QTimer.singleShot(500, self.score_view.request_score_data)

    @Slot(dict)
    def _on_score_data_received(self, data: dict):
        """接收到乐谱数据 (JS -> Python)"""
        events = data.get('events', [])
        print(f"[MainWindow] 收到乐谱数据: {len(events)} 个音符事件")
        
        # 将数据加载到 ScoreFollower
        # event: [startTime, duration, midiPitch]
        if events:
            self.score_follower.load_score_from_midi_events(events)
            self.statusBar().showMessage(f"对齐数据已就绪: {len(events)} 音符")

    def _open_score_file(self):
        """打开乐谱文件对话框"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开乐谱文件",
            "",
            "乐谱文件 (*.gp3 *.gp4 *.gp5 *.gpx *.gp *.musicxml *.mxl *.xml *.mid *.midi);;所有文件 (*)"
        )
        if file_path:
            self.score_view.load_file(file_path)
            self.statusBar().showMessage(f"正在加载: {file_path}")

    def _toggle_playback(self):
        """播放/暂停切换"""
        self.score_view.play_pause()

    def _stop_playback(self):
        """停止播放"""
        self.score_view.stop()

    def _on_speed_changed(self, value):
        """速度变化"""
        speed = value / 100.0
        # self.speed_label.setText(f"{value}%") # Removed label
        self.score_view.set_speed(speed)

    def _reset_speed(self):
        """重置速度"""
        self.speed_spin.setValue(100)

    def _toggle_practice(self):
        """切换练习模式"""
        if self.btn_practice.isChecked():
            self.statusBar().showMessage("练习模式已开启 - 自动跟随")
            self.score_follower.reset()
            self.marked_notes.clear() # 清除命中记录
            
            # 初始化练习统计
            total_notes = len(self.score_follower.events) if hasattr(self.score_follower, 'events') else 0
            self.practice_session.start(total_notes)
            self.label_score.setText("得分: 0")
            self.label_combo.setText("Combo: 0")
            
            # Reset cursor to start
            self.score_view.set_cursor_time(0.0)
        else:
            self.statusBar().showMessage("练习模式已关闭")
            self.practice_session.stop()
            
            # 弹出结算 summary (简单演示)
            summary = self.practice_session.get_summary()
            QMessageBox.information(self, "练习完成", 
                f"得分: {summary['score']}\n"
                f"准确率: {summary['accuracy']:.1f}%\n"
                f"最大连击: {summary['max_combo']}\n"
                f"命中: {summary['hits']}/{summary['hits'] + summary['misses']}")

    def _set_stave(self, profile: str):
        """谱面模式切换"""
        self.score_view.set_stave_profile(profile)
        # 更新菜单勾选
        self.action_tab.setChecked(profile == "Tab")
        self.action_score.setChecked(profile == "Score")
        self.action_score_tab.setChecked(profile == "ScoreTab")
        
        # Sync Combo Box
        mapping = {"Tab": 0, "Score": 1, "ScoreTab": 2}
        if profile in mapping:
            self.stave_combo.blockSignals(True)
            self.stave_combo.setCurrentIndex(mapping[profile])
            self.stave_combo.blockSignals(False)

    def _set_layout(self, mode: str):
        """布局模式切换"""
        self.score_view.set_layout_mode(mode)
        # 更新菜单勾选
        self.action_page_layout.setChecked(mode == "Page")
        self.action_horizontal_layout.setChecked(mode == "Horizontal")

    def _zoom_in(self):
        """放大"""
        self.score_view.zoom_in()

    def _zoom_out(self):
        """缩小"""
        self.score_view.zoom_out()

    def _zoom_reset(self):
        """重置缩放"""
        self.score_view.zoom_reset()

    def _on_zoom_changed(self, zoom: float):
        """缩放变化回调"""
        self.zoom_label.setText(f"{int(zoom * 100)}%")

    def _on_stave_changed(self, index):
        """谱面模式下拉框变化"""
        profiles = ["Tab", "Score", "ScoreTab"]
        if 0 <= index < len(profiles):
            self._set_stave(profiles[index])

    def _on_score_loaded(self, info: dict):
        """乐谱加载完成"""
        title = info.get('title', '未命名')
        artist = info.get('artist', '')
        tempo = info.get('tempo', '?')
        bars = info.get('bars', 0)
        self.setWindowTitle(f"Guitar Pro — {title} - {artist}")
        self.statusBar().showMessage(f"已加载: {title} | {artist} | ♩={tempo} | {bars}小节")



    def _on_beat_changed(self, data: dict):
        """当前拍子变化（练习模式用）"""
        # TODO: 连接到 PracticeEngine
        pass

    def _on_position_changed(self, data: dict):
        """播放位置变化"""
        # 更新状态栏时间
        current = data.get('currentTime')
        end = data.get('endTime')
        
        if current is None or end is None:
            return

        m1, s1 = divmod(int(current / 1000), 60)
        m2, s2 = divmod(int(end / 1000), 60)
        self.statusBar().showMessage(f"播放中: {m1}:{s1:02d} / {m2}:{s2:02d}")

    def _on_player_finished(self):
        """播放完成"""
        self.statusBar().showMessage("播放完成")

    def _on_render_progress(self, progress: int):
        """渲染进度回调"""
        if progress < 100:
            self.statusBar().showMessage(f"渲染中... {progress}%")
        else:
            self.statusBar().showMessage("渲染完成")

    def _on_error(self, message: str):
        """错误回调"""
        self.statusBar().showMessage(f"⚠️ {message}")

    def closeEvent(self, event):
        """窗口关闭时清理资源"""
        self.ui_timer.stop()
        if self.audio.is_running:
            self.audio.stop()
        event.accept()

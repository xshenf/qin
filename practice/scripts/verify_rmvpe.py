
import numpy as np
import sys
import os

# 将 src 添加到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.mir.pitch import PitchTracker
from src.mir.alignment import ScoreFollower

def test_rmvpe_integration():
    print("--- 开始测试 RMVPE 集成 ---")
    
    # 1. 检查模型文件
    model_path = "vendor/models/rmvpe.onnx"
    if not os.path.exists(model_path):
        print(f"[警告] 模型文件未找到: {model_path}。音高检测将回退到 YIN/CREPE。")
    
    # 2. 初始化 PitchTracker
    tracker = PitchTracker(sample_rate=16000)
    print(f"PitchTracker 初始化完成。RMVPE 加载状态: {'成功' if tracker.rmvpe_engine and tracker.rmvpe_engine.is_ready else '未加载'}")
    
    # 3. 模拟一段音频 (440Hz A4)
    duration = 0.5
    sr = 16000
    t = np.linspace(0, duration, int(sr * duration))
    audio = 0.5 * np.sin(2 * np.pi * 440.0 * t).astype(np.float32)
    
    # 4. 测试预测
    freq, conf = tracker.predict(audio)
    print(f"检测结果: 频率={freq:.2f}Hz, 置信度={conf:.2f}")
    
    if abs(freq - 440.0) < 5.0:
        print("[成功] 音高识别准确。")
    else:
        print("[失败] 音高识别偏离。")
        
    # 5. 测试对齐逻辑 (F0-based Chroma)
    follower = ScoreFollower(sample_rate=sr)
    # 模拟简单的乐谱数据 (一条 A4 音符)
    # events: start, dur, pitch, id
    follower.load_score_from_midi_events([(0.0, 1.0, 69, "note1")])
    
    # 使用 F0 引导对齐
    est_time = follower.process_frame(audio, f0=freq, confidence=conf)
    print(f"对齐测试: 估计时间={est_time:.2f}s")
    
    if est_time >= 0:
        print("[成功] 对齐逻辑运行正常。")

if __name__ == "__main__":
    test_rmvpe_integration()

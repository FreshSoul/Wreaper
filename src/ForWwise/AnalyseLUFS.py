import soundfile as sf
import pyloudnorm as pyln
import numpy as np
import csv
from waapi import WaapiClient, CannotConnectToWaapiException

def analyze_loudness_detailed(audio_file_path, window_size=0.4, overlap=0.5):
    try:
        data, rate = sf.read(audio_file_path, always_2d=False)
    except Exception as e:
        print(f"读取文件失败: {audio_file_path}，原因: {e}")
        return None, None

    window_samples = max(1, int(rate * window_size))

    # 若音频短于窗口，零填充到窗口长度，保证至少一个分析块
    if len(data) < window_samples:
        pad = window_samples - len(data)
        if getattr(data, "ndim", 1) == 1:
            data = np.pad(data, (0, pad), mode='constant')
        else:
            data = np.pad(data, ((0, pad), (0, 0)), mode='constant')

    meter = pyln.Meter(rate)

    try:
        integrated = meter.integrated_loudness(data)
    except Exception as e:
        print(f"响度分析失败: {audio_file_path}，原因: {e}")
        return None, None

    hop_samples = max(1, int(window_samples * (1 - overlap)))
    momentary_levels = []
    for i in range(0, len(data) - window_samples + 1, hop_samples):
        chunk = data[i:i + window_samples]
        try:
            loudness = meter.integrated_loudness(chunk)
            momentary_levels.append(loudness)
        except Exception:
            continue

    # 若没有有效瞬时窗口，则回退为综合值
    max_momentary = max(momentary_levels) if momentary_levels else integrated
    return integrated, max_momentary

def get_audio_sources():
    try:
        with WaapiClient() as client:
            # 1) 获取当前选择
            result = client.call("ak.wwise.ui.getSelectedObjects")
            selected = result.get('objects', []) if result else []
            if not selected:
                print("未选中任何对象。")
                return []

            ids = [obj['id'] for obj in selected]

            # 2) 取“选中对象自身”的信息
            selected_info = client.call("ak.wwise.core.object.get", {
                "from": {"id": ids},
                "options": {"return": ["id", "name", "type", "path"]}
            })
            selected_objects = (selected_info or {}).get('return', [])

            # 3) 取“选中对象的所有后代”的信息
            descendants_info = client.call("ak.wwise.core.object.get", {
                "from": {"id": ids},
                "transform": [{"select": ["descendants"]}],
                "options": {"return": ["id", "name", "type", "path"]}
            })
            descendants_objects = (descendants_info or {}).get('return', [])

            # 合并自身 + 后代
            all_objects = selected_objects + descendants_objects

            # 4) 过滤音频源
            audio_sources = [obj for obj in all_objects if obj.get('type') == 'AudioFileSource']

            audio_files = []
            for audio in audio_sources:
                # 5) 拉取源自身属性（含原始文件路径、@@OutputBusVolume）
                props = client.call("ak.wwise.core.object.get", {
                    "from": {"id": [audio['id']]},
                    "options": {"return": ["originalWavFilePath", "name", "path", "duration", "@OutputBusVolume"]}
                })
                for item in (props or {}).get('return', []):
                    path = item.get('originalWavFilePath')
                    if not path:
                        continue

                    self_volume = item.get('@OutputBusVolume')

                    # 若源本身无该值，取直接父级（通常是 Sound）的 @@OutputBusVolume 
                    if self_volume is None:
                        parent_props = client.call("ak.wwise.core.object.get", {
                            "from": {"id": [audio['id']]},
                            "transform": [{"select": ["parent"]}],
                            "options": {"return": ["id", "name", "@OutputBusVolume"]}
                        })
                        parent_items = (parent_props or {}).get('return', [])
                        if parent_items:
                            self_volume = parent_items[0].get('@OutputBusVolume')

                    # 6) ancestors 列表（含每级 @Volume 与 make-up gain）
                    ancestors_props = client.call("ak.wwise.core.object.get", {
                        "from": {"id": [audio['id']]},
                        "transform": [{"select": ["ancestors"]}],
                        "options": {"return": [
                            "id", "name",
                            "@Volume",
                            "@MakeUpGain"
                        ]}
                    })

                    ancestors_list = []
                    for ancestor in (ancestors_props or {}).get('return', []):
                        name = ancestor.get('name')
                        vol = ancestor.get('@Volume')
                        # 兼容不同插件/版本下的命名
                        mug = ancestor.get('@MakeUpGain') 
                        if name:
                            ancestors_list.append({"name": name, "volume": vol, "makeup": mug})

                    ancestors_map = {a["name"]: a.get("volume") for a in ancestors_list}

                    audio_files.append({
                        "name": item.get('name', ''),
                        "wwise_path": item.get('path', ''),
                        "file_path": path,
                        "duration": item.get('duration', 0),
                        "Volume": self_volume,  
                        "ancestors_list": ancestors_list,
                        
                    })
            return audio_files
    except CannotConnectToWaapiException:
        print("无法连接到WAAPI，请确保Wwise已开启WAAPI。")
        return []

def main():
    audio_files = get_audio_sources()
    if not audio_files:
        print("未找到音频源文件。")
        return

    # 计算最大父级层数（从最近父级开始计数）
    max_depth = 0
    for audio in audio_files:
        depth = len(audio.get("ancestors_list", []))
        if depth > max_depth:
            max_depth = depth

    # 基础列 + 层级列（父级名1..N、父级音量1..N）
    base_fields = ["name", "wwise_path", "file_path", "LUFS-I", "LUFS-M-MAX", "音频时长", "OutPutBus音量"]
    level_fields = []
    for i in range(1, max_depth + 1):
        level_fields.append(f"父级名{i}")
        level_fields.append(f"父级音量{i}")
        level_fields.append(f"父级MakeUpGain{i}")  # 统一使用 MakeUpGain
    fieldnames = base_fields + level_fields

    results = []
    for audio in audio_files:
        print(f"分析: {audio['name']} ({audio['file_path']})")
        integrated, max_momentary = analyze_loudness_detailed(audio['file_path'])
        row = {
            "name": audio['name'],
            "wwise_path": audio['wwise_path'],
            "file_path": audio['file_path'],
            "LUFS-I": integrated,
            "LUFS-M-MAX": max_momentary,
            "音频时长": audio['duration'],
            "OutPutBus音量": ("" if audio['Volume'] is None else audio['Volume']),  # 输出总线音量
        }

        # 填充层级列：按从近到远的顺序写入
        ancestors = audio.get("ancestors_list", [])
        for i in range(max_depth):
            name_key = f"父级名{i+1}"
            vol_key = f"父级音量{i+1}"
            mug_key = f"父级MakeUpGain{i+1}"  # 统一列名
            if i < len(ancestors):
                row[name_key] = ancestors[i].get("name", "")
                v = ancestors[i].get("volume", None)
                m = ancestors[i].get("makeup", None)
                row[vol_key] = v if v is not None else ""
                row[mug_key] = m if m is not None else ""
            else:
                row[name_key] = ""
                row[vol_key] = ""
                row[mug_key] = ""
        results.append(row)

    csv_path = "UI_Original_Audio_Loudness.csv"
    with open(csv_path, "w", newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)
    print(f"分析结果已保存到 {csv_path}")

if __name__ == "__main__":
    main()
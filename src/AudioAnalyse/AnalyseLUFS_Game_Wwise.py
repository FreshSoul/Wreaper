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
        return None, None, f"读取文件失败: {e}"

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
        return None, None, f"响度分析失败: {e}"

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
    return integrated, max_momentary, None

def get_audio_sources(progress_callback=None, status_callback=None):
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
            total = len(audio_sources)
            for idx, audio in enumerate(audio_sources):
                if progress_callback:
                    progress_callback(int((idx + 1) / total * 100))
                if status_callback:
                    status_callback(f"正在获取: {audio.get('name', '')} ({idx+1}/{total})")

                # 5) 拉取源自身属性（含原始文件路径、OutputBus 引用）
                props = client.call("ak.wwise.core.object.get", {
                    "from": {"id": [audio['id']]},
                    "options": {"return": ["originalWavFilePath", "name", "path", "duration", "OutputBus"]}
                })
                for item in (props or {}).get('return', []):
                    path = item.get('originalWavFilePath')
                    if not path:
                        continue

                    # 读取对象自身的 Output Bus（兼容字符串或字典）
                    bus_ref = item.get('OutputBus')
                    bus_id = bus_ref.get('id') if isinstance(bus_ref, dict) else bus_ref

                    # 6) ancestors 列表（含每级 @Volume、@MakeUpGain、@OutputBus），用于层级列与 Output Bus 继承回退
                    ancestors_props = client.call("ak.wwise.core.object.get", {
                        "from": {"id": [audio['id']]},
                        "transform": [{"select": ["ancestors"]}],
                        "options": {"return": ["id", "name", "@Volume", "@MakeUpGain", "OutputBus"]}
                    })

                    ancestors_list = []
                    raw_ancestors = (ancestors_props or {}).get('return', [])
                    for ancestor in raw_ancestors:
                        name = ancestor.get('name')
                        vol = ancestor.get('@Volume')
                        mug = ancestor.get('@MakeUpGain')
                        if name:
                            ancestors_list.append({"name": name, "volume": vol, "makeup": mug})

                    # 若对象未设置 Output Bus，则从最近父级开始寻找第一个设置了 @OutputBus 的对象
                    if not bus_id:
                        for anc in raw_ancestors:
                            anc_bus_ref = anc.get('OutputBus')
                            anc_bus_id = anc_bus_ref.get('id') if isinstance(anc_bus_ref, dict) else anc_bus_ref
                            if anc_bus_id:
                                bus_id = anc_bus_id
                                break

                    # 7) 查询目标 Bus 的 BusVolume 与 Volume 以及 ancestors
                    bus_bus_volume = None
                    bus_volume = None
                    bus_ancestors_list = []
                    bus_name = ""
                    if bus_id:
                        bus_info = client.call("ak.wwise.core.object.get", {
                            "from": {"id": [bus_id]},
                            "options": {"return": ["id", "name", "@BusVolume", "@Volume"]}
                        })
                        bus_items = (bus_info or {}).get('return', [])
                        if bus_items:
                            bus_bus_volume = bus_items[0].get('@BusVolume')
                            bus_volume = bus_items[0].get('@Volume')
                            bus_name = bus_items[0].get('name', '')

                        # 查询 Bus 的 ancestors
                        bus_ancestors_info = client.call("ak.wwise.core.object.get", {
                            "from": {"id": [bus_id]},
                            "transform": [{"select": ["ancestors"]}],
                            "options": {"return": ["id", "name", "@BusVolume", "@Volume"]}
                        })
                        raw_bus_ancestors = (bus_ancestors_info or {}).get('return', [])
                        for ancestor in raw_bus_ancestors:
                            bus_ancestors_list.append({
                                "name": ancestor.get('name'),
                                "bus_volume": ancestor.get('@BusVolume'),
                                "volume": ancestor.get('@Volume')
                            })

                    audio_files.append({
                        "name": item.get('name', ''),
                        "wwise_path": item.get('path', ''),
                        "file_path": path,
                        "duration": item.get('duration', 0),
                        "OutputBus_Name": bus_name,
                        "OutputBus_BusVolume": bus_bus_volume,
                        "OutputBus_Volume": bus_volume,
                        "OutputBus_ancestors_list": bus_ancestors_list,
                        "ancestors_list": ancestors_list,
                    })
            return audio_files
    except CannotConnectToWaapiException:
        print("无法连接到WAAPI，请确保Wwise已开启WAAPI。")
        return []



#if __name__ == "__main__":
#    main()
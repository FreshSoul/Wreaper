from waapi import WaapiClient, CannotConnectToWaapiException

def get_selected_object_children_audio_sources():
    try:
        with WaapiClient() as client:
            # 获取当前选中的对象
            result = client.call("ak.wwise.ui.getSelectedObjects")
            selected = result.get('objects', [])
            if not selected:
                print("未选中任何对象。")
                return

            # 获取所有子层级对象（递归）
            ids = [obj['id'] for obj in selected]
            query = {
                "from": {"id": ids},
                "options": {"return": ["id", "name", "type", "path"]},
                "transform": [
                    {"select": ["descendants"]}
                ]
            }
            descendants = client.call("ak.wwise.core.object.get", query)
            all_objects = descendants.get('return', [])

            # 过滤出音频源对象
            audio_sources = [obj for obj in all_objects if obj['type'] == 'AudioFileSource']

            # 获取原始音频文件路径
            for audio in audio_sources:
                props = client.call("ak.wwise.core.object.get", {
                    "from": {"id": [audio['id']]},
                    "options": {"return": ["originalWavFilePath", "name", "path"]}
                })
                for item in props.get('return', []):
                    print(f"{item['name']} ({item['path']}): {item.get('originalWavFilePath', '无路径')}")

    except CannotConnectToWaapiException:
        print("无法连接到WAAPI，请确保Wwise已开启WAAPI。")

if __name__ == "__main__":
    get_selected_object_children_audio_sources()
from waapi import WaapiClient, CannotConnectToWaapiException

def get_selected_and_descendants_volume_makeup():
    try:
        with WaapiClient() as client:
    
            result = client.call("ak.wwise.ui.getSelectedObjects")
            selected = result.get('objects', []) if result else []
            if not selected:
                print("未选中任何对象。")
                return []

            ids = [obj['id'] for obj in selected]

           
            all_objects_info_descendants = client.call("ak.wwise.core.object.get", {
                "from": {"id": ids},
                "transform": [{"select": ["descendants"]}],
                "options": {"return": ["id", "name", "type", "path", "@Volume", "@MakeUpGain"]}
            })
            descendants_objects = (all_objects_info_descendants or {}).get('return', [])
            
            
            all_objects_info_self = client.call("ak.wwise.core.object.get", {
                "from": {"id": ids},
                "options": {"return": ["id", "name", "type", "path", "@Volume", "@MakeUpGain"]}
            })
            self_objects = (all_objects_info_self or {}).get('return', [])
            
            all_objects = {obj['id']: obj for obj in self_objects + descendants_objects}

     
            for obj in all_objects.values():
                volume = obj.get("@Volume")
                makeup_gain = obj.get("@MakeUpGain")
                name = obj.get("name")
               
                if volume is not None or makeup_gain is not None:
                    try:
                        volume_f = float(volume) if volume is not None else 0
                    except (TypeError, ValueError):
                        volume_f = 0
                    try:
                        makeup_gain_f = float(makeup_gain) if makeup_gain is not None else 0
                    except (TypeError, ValueError):
                        makeup_gain_f = 0
                    new_makeup_gain = volume_f + makeup_gain_f
                    
                    print(name,volume_f, makeup_gain_f, new_makeup_gain)
                    
                   
                    if volume is not None:
                        try:
                            client.call("ak.wwise.core.object.setProperty", {
                                "object": obj['id'],
                                "property": "Volume",
                                "value": 0
                            })
                        except Exception as e:
                            print(f"{obj.get('name')}: 设置Volume失败，原因：{e}")

                   
                    if makeup_gain is not None:
                        try:
                            client.call("ak.wwise.core.object.setProperty", {
                                "object": obj['id'],
                                "property": "MakeUpGain",
                                "value": new_makeup_gain
                            })
                        except Exception as e:
                            print(f"{obj.get('name')}: 设置MakeUpGain失败，原因：{e}")

                    print(f"{obj.get('name')}: Volume设为0，MakeUpGain设为{new_makeup_gain}")
                else:
                    print(f"{obj.get('name')}: 无Volume和MakeUpGain属性，跳过。")

    except CannotConnectToWaapiException:
        print("无法连接到WAAPI，请确保Wwise已开启WAAPI。")
        return []

if __name__ == "__main__":
    get_selected_and_descendants_volume_makeup()
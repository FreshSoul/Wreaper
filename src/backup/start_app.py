from waapi import WaapiClient, CannotConnectToWaapiException

def getaudio_sources():
    with WaapiClient() as client:
        # 第一步：获取目标对象下的 AudioFileSource 子对象
        result = client.call("ak.wwise.core.object.get", {
            "from": {
                "path": ["\\Actor-Mixer Hierarchy\\X6_Audio\\X6_Audio\\X6_Audio\\X6_CD\\X6_CD\\CD_2_0\\CD_2_0\\Sfx_q102101_1_d1_cd_06"]
            },
            "options": {
                "return": ["id", "name", "type"]
            }
        })
        print("对象信息:", result)

        if result and "return" in result:
            obj_id = result["return"][0]["id"]

            # 第二步：获取该对象的 AudioFileSource 子对象
            sources = client.call("ak.wwise.core.object.get", {
                "from": {
                    "id": [obj_id]
                },
                "transform": [
                    {"select": ["children"]}
                ],
                "options": {
                    "return": ["id", "name", "type", "@VolumeOffset"]
                }
            })
            print("音频源信息:", sources)

getaudio_sources()
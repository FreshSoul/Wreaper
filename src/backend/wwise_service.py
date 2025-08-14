import traceback
from waapi import WaapiClient, CannotConnectToWaapiException

class WwiseService:
    """
    封装与 Wwise 的通讯。该模块不依赖任何前端库（如 PyQt）。
    """

    def get_selected_audio_files(self):
        """
        返回 Wwise 里当前选中的对象的 originalFilePath 列表。
        """
        try:
            with WaapiClient() as client:
                result = client.call(
                    "ak.wwise.ui.getSelectedObjects",
                    options={'return': ['originalFilePath', 'music:playlistRoot']}
                )
                return [o.get("originalFilePath")
                        for o in result.get("objects", [])
                        if o.get("originalFilePath")]
        except CannotConnectToWaapiException as e:
            raise RuntimeError("无法连接到Wwise，请确保Wwise正在运行。") from e
        except Exception as e:
            raise RuntimeError(f"获取Wwise选中对象失败: {e}\n{traceback.format_exc()}") from e
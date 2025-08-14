import asyncio
import socket
import traceback
from waapi import WaapiClient, CannotConnectToWaapiException

class WwiseService:
    def __init__(self, host="127.0.0.1", port=8080, timeout=1.0):
        self.host = host
        self.port = port
        self.timeout = float(timeout)  # 这里的 timeout 仅用于端口探测

    def _is_wwise_port_open(self) -> bool:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout)  # 快速探测
        try:
            return s.connect_ex((self.host, self.port)) == 0
        finally:
            try:
                s.close()
            except Exception:
                pass

    def get_selected_audio_files(self):
        """
        返回 Wwise 里当前选中的对象的 originalFilePath 列表。
        放在子线程里调用更安全。
        """
        loop = None
        try:
            # 1) 先做快速端口探测，未开启直接返回友好错误
            if not self._is_wwise_port_open():
                raise RuntimeError("无法连接到Wwise，请确保Wwise已启动并启用WAAPI。")

            # 2) 确保当前线程有事件循环（waapi 内部会用到 asyncio）
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # 3) 连接并获取选中对象
            url = f"ws://{self.host}:{self.port}/waapi"
            # 注意：此版本 WaapiClient 不支持 timeout 参数，不要传
            with WaapiClient(url=url) as client:
                result = client.call(
                    "ak.wwise.ui.getSelectedObjects",
                    options={'return': ['originalFilePath', 'music:playlistRoot']}
                )
                objs = result.get("objects", []) if result else []
                return [o.get("originalFilePath") for o in objs if o.get("originalFilePath")]

        except CannotConnectToWaapiException as e:
            raise RuntimeError("无法连接到Wwise，请确保Wwise正在运行并启用WAAPI。") from e
        except Exception as e:
            raise RuntimeError(f"获取Wwise选中对象失败: {e}\n{traceback.format_exc()}") from e
        finally:
            # 只关闭我们手动创建的事件循环
            if loop is not None:
                try:
                    loop.close()
                except Exception:
                    pass
                try:
                    asyncio.set_event_loop(None)
                except Exception:
                    pass
from typing import Tuple, List, Dict, Union
import requests
import time

from .mineflayer_manager import MineflayerManager
from .server_manager import ServerManager
from .data.action import Action
from .data.low_level_action import LowLevelAction
from .data.observation import Observation
from .data.code_info import CodeInfo
from .data.event import Event

class Bridge:
    def __init__(
        self,

        mineflayer_manager: MineflayerManager,
        server_manager: ServerManager,

        ticks_per_step: int,
        enable_auto_pause: bool,
        enable_low_level_action: bool,

        minecraft_server_host: str,
        minecraft_server_port: int,
        image_size: Tuple[int, int],
        headless: bool,

        agents_count: int,
        agents_config: List[Dict[str, Union[int, str]]],

        minecraft_version: str = 1.19,
        mineflayer_host: str = "localhost",
        mineflayer_port: int = 21301,
        request_timeout: float = 3000,
    ):
        self.mineflayer_manager = mineflayer_manager
        self.server_manager = server_manager

        self.minecraft_server_host = minecraft_server_host
        self.minecraft_server_port = minecraft_server_port
        self.ticks_per_step = ticks_per_step
        self.enable_auto_pause = enable_auto_pause
        self.enable_low_level_action = enable_low_level_action

        self.agents_count = agents_count
        self.agents_config = agents_config

        self.image_height = image_size[0]
        self.image_width = image_size[1]
        self.headless = headless

        self.minecraft_version = minecraft_version
        self.mineflayer_host = mineflayer_host
        self.mineflayer_port = mineflayer_port
        self.mineflayer_host_port = f"http://{self.mineflayer_host}:{self.mineflayer_port}"
        self.request_timeout = request_timeout

        self.camera_set = set()

    
    def reset(
        self
    ) -> List[Observation]:
        res = requests.post(
            f"{self.mineflayer_host_port}/start",
            json={
                "server_host": self.minecraft_server_host,
                "server_port": self.minecraft_server_port,
                "minecraft_version": self.minecraft_version,
                "agents_count": self.agents_count,
                "agents_config": self.agents_config,
                "image_width": self.image_width,
                "image_height": self.image_height,
                "headless": self.headless,
            },
            timeout=self.request_timeout,
        )
        if res.status_code != 200:
            raise RuntimeError("[Bridge]", "Failed to start, status code: " + str(res.status_code))
        
        data = res.json()

        for i in range(len(data['observation'])):
            data['observation'][i]['event'] = []

        return Observation.from_json_list(data['observation'])

    def step(
        self,
        action: List[Union[Action, LowLevelAction]],
    ) -> Tuple[List[Observation], List[CodeInfo], List[Event]]:
        
        res = requests.post(
            f"{self.mineflayer_host_port}/step_pre",
            json={
                "ticks": self.ticks_per_step,
                "is_low_level_action": self.enable_low_level_action,
                "action": [a.to_json() for a in action],
            },
            timeout=self.request_timeout,
        )

        data = res.json()
        if res.status_code != 200:
            raise RuntimeError("Failed to step, status code: " + str(res.status_code) + '\n' + "  message: " + data['error'] + '\n')
        
        # ===== Divider =====
        if self.server_manager is not None and self.enable_auto_pause:
            self.server_manager.execute("runtick " + str(self.ticks_per_step))

        res = requests.post(
            f"{self.mineflayer_host_port}/step_lst",
            json={
                "ticks": self.ticks_per_step,
            },
            timeout=self.request_timeout,
        )
        
        data = res.json()
        if res.status_code != 200:
            raise RuntimeError("Failed to step, status code: " + str(res.status_code) + '\n' + "  message: " + data['error'] + '\n')
        for i in range(len(data['observation'])):
            if data['observation'][i] is not None:
                data['observation'][i]['event'] = data['event'][i]
        
        return (
            Observation.from_json_list(data['observation']),
            CodeInfo.from_json_list(data['code_info']),
            data['event'], # No event class wrapper
        )
    
    def add_an_agent(self, agent_config: Dict[str, Union[int, str]]):
        res = requests.post(
            f"{self.mineflayer_host_port}/add_an_agent",
            json={
                "server_host": self.minecraft_server_host,
                "server_port": self.minecraft_server_port,
                "minecraft_version": self.minecraft_version,
                "agent_config": agent_config,
                "image_width": self.image_width,
                "image_height": self.image_height,
                "headless": self.headless,
            },
            timeout=self.request_timeout,
        )
        if res.status_code != 200:
            raise RuntimeError("[Bridge]", "Failed to add an agent, status code: " + str(res.status_code))
    
    def disconnect_an_agent(self, name: str):
        res = requests.post(
            f"{self.mineflayer_host_port}/disconnect_an_agent",
            json={
                "name": name,
            },
            timeout=self.request_timeout,
        )
        if res.status_code != 200:
            raise RuntimeError("[Bridge]", "Failed to disconnect an agent, status code: " + str(res.status_code))


    def close(self):
        res = requests.post(
            f"{self.mineflayer_host_port}/end",
            timeout=self.request_timeout,
        )
        if res.status_code != 200:
            raise RuntimeError("[Bridge]", "Failed to close, status code: " + str(res.status_code))
        
        self.mineflayer_manager.shutdown()
        return res.json()
    
    # ===== Camera =====
    
    def addCamera(self, camera_id):
        self.camera_set.add(camera_id)
        res = requests.post(
            f"{self.mineflayer_host_port}/addCamera",
            json={
                "camera_id": camera_id,
                "image_width": self.image_width,
                "image_height": self.image_height,
            },
            timeout=self.request_timeout,
        )
        if res.status_code != 200:
            raise RuntimeError("[Bridge]", "Failed to add camera, status code: " + str(res.status_code))
        
        return res.json()
    
    def getCameraView(self, camera_id):
        if camera_id not in self.camera_set:
            raise ValueError(f"Camera ID {camera_id} is not available in the camera set.")
        
        res = requests.post(
            f"{self.mineflayer_host_port}/getCameraView",
            json={
                "camera_id": camera_id,
            },
            timeout=self.request_timeout,
        )
        if res.status_code != 200:
            raise RuntimeError("[Bridge]", "Failed to get camera view, status code: " + str(res.status_code))
        
        data = res.json()

        return data['rgb']
    
    def updateCameraLocation(self, camera_id, pos, yaw, pitch):
        if camera_id not in self.camera_set:
            raise ValueError(f"Camera ID {camera_id} is not available in the camera set.")
        
        res = requests.post(
            f"{self.mineflayer_host_port}/updateCameraLocation",
            json={
                "camera_id": camera_id,
                "pos": pos,
                "yaw": yaw,
                "pitch": pitch,
            },
            timeout=self.request_timeout,
        )
        if res.status_code != 200:
            raise RuntimeError("[Bridge]", "Failed to update camera location, status code: " + str(res.status_code))
        return res.json()
    
    def moveCamera(self, camera_id, pos, yaw, pitch):
        if camera_id not in self.camera_set:
            raise ValueError(f"Camera ID {camera_id} is not available in the camera set.")
        
        res = requests.post(
            f"{self.mineflayer_host_port}/moveCameraLocation",
            json={
                "camera_id": camera_id,
                "d_pos": pos,
                "d_yaw": yaw,
                "d_pitch": pitch,
            },
            timeout=self.request_timeout,
        )
        if res.status_code != 200:
            raise RuntimeError("[Bridge]", "Failed to add camera location, status code: " + str(res.status_code))
        return res.json()
    

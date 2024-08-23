from mineland.sim.data.task_info import TaskInfo
from mineland.utils import base64_to_image, red_text

from .base_task import BaseTask
from .utils import *
import os
import cv2
import numpy as np
import base64

has_mineclip = False
import_error = None
try:
    import torch
    import hashlib
    from PIL import Image
    from torchvision import transforms
    from mineclip import MineCLIP
    has_mineclip = True
except ImportError as e:
    has_mineclip = e
    enble_mineclip = False

class ConstructionTask(BaseTask):
    def __init__(
        self,
        blueprint_file_name:str,
        baseline_file_name:str,
        goal:str,
        enable_mineclip:bool = False,
        mineclip_ckpt_path:str = None,
        **kwargs,
    ):
        self.blueprint_file_name = blueprint_file_name
        self.baseline_file_name = baseline_file_name
        self.enable_mineclip = enable_mineclip
        self.mineclip_ckpt_path = mineclip_ckpt_path
        self.goal = goal

        if self.enable_mineclip and not has_mineclip:
            mineclip_link = 'https://github.com/MineDojo/MineCLIP'
            raise ImportError(f"MineCLIP is not installed. Import error message is {import_error}. Please install MineCLIP " + red_text('avg') + f" according to {mineclip_link}.")
        if self.enable_mineclip:
            if mineclip_ckpt_path is None:
                raise ValueError("Please use `mineclip_ckpt_path='...'` to load ckpt.")
            print("MineCLIP is enabled. Loading model...")
            assert (
                hashlib.md5(open(self.mineclip_ckpt_path, "rb").read()).hexdigest() == 'd97a07f2830095a2016a8da22abcff52'
            ), 'broken ckpt. Please use "avg" ckpt'
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.FRAME_HEIGHT = 160
            self.FRAME_WIDTH = 256
            self.transform = transforms.Compose([
                transforms.Resize((self.FRAME_HEIGHT, self.FRAME_WIDTH)),
                transforms.ToTensor(),
            ])
            cfg = {
                'arch': 'vit_base_p16_fz.v2.t2',
                'hidden_dim': 512,
                'image_feature_dim': 512,
                'mlp_adapter_spec': 'v0-2.t0',
                'pool_type': 'avg',
                'resolution': [160, 256]
            }
            self.mineclip = MineCLIP(**cfg).to(self.device)
            self.mineclip.load_ckpt(self.mineclip_ckpt_path, strict=True)
            print("MineCLIP model ckpt loaded.")
            print("Run `mland.get_score_by_mineclip()` to get the score.")


        kwargs["world_type"] = "construction"
        # self.goal = f'agent(s) need to build a construction like the picture \n '
        self.guidance = f'this is creative mode, you can use any system instruction, such as /give oak_log, to give yourself some oak logs'
        
        picture_path = os.path.join(os.path.dirname(__file__), 'description_files')
        picture_path = os.path.join(picture_path, 'construction_tasks_pictures')
        
        self.blueprint_file_path = os.path.join(picture_path, self.blueprint_file_name)
        self.baseline_file_path = os.path.join(picture_path, self.baseline_file_name)
        self.initiate_picture_message()
        
        if self.enable_mineclip:
            self.initiate_picture_message_mineclip()

        super().__init__(**kwargs)
        print(f'agent(s) need to build a construction like the picture')
    
    def reset(self):
        obs = self.env.reset()
        # self.server_manager.execute("gamemode creative")
        self.env.bridge.addCamera("construction_camera")
        return obs
    
    def __load_img(self, path):
        img = Image.open(path).convert('RGB')
        return self.transform(img).to(self.device)
    
    def initiate_picture_message(self) :
        # baseline score
        baseline_img = cv2.imread(self.baseline_file_path, cv2.IMREAD_COLOR)
        blueprint_img = cv2.imread(self.blueprint_file_path, cv2.IMREAD_COLOR)
        print(self.baseline_file_path)
        baseline_img = np.transpose(baseline_img, (2, 0, 1))
        blueprint_img = np.transpose(blueprint_img, (2, 0, 1))
        self.baseline_score = get_image_similarity_by_orb(baseline_img, blueprint_img)
        
        # blueprint_img_base64
        blueprint_img_file = open(self.blueprint_file_path, 'rb')
        self.blueprint_img_base64 = base64.b64encode(blueprint_img_file.read())
        self.blueprint_img_np = blueprint_img
        # check image 
        # rgb = base64_to_image(self.blueprint_img_base64, 320, 180)
        # img = np.transpose(rgb, (1, 2, 0))
        # pil_img = Image.fromarray(img)
        # pil_img.show()
        # pil_img.save(f'output_camera_image.jpg')

        # image_files
        print("baseline is : " + str(self.baseline_score))

    def initiate_picture_message_mineclip(self):
        if not self.enable_mineclip:
            raise ValueError("MineCLIP is not enabled. Please use `enable_mineclip=True` when creating the task.")

        video = torch.zeros((1, 1, 3, self.FRAME_HEIGHT, self.FRAME_WIDTH), device=self.device)
        video[0][0] = self.__load_img(self.baseline_file_path)

        self.baseline_score_mineclip = self.__run_mineclip(video, [self.goal])

    def __run_mineclip(self, video, prompts):
        if not self.enable_mineclip:
            raise ValueError("MineCLIP is not enabled. Please use `enable_mineclip=True` when creating the task.")
        VIDEO_BATCH, TEXT_BATCH = video.size(0), len(prompts)

        image_feats = self.mineclip.forward_image_features(video)
        video_feats = self.mineclip.forward_video_features(image_feats)
        assert video_feats.shape == (VIDEO_BATCH, 512)
        
        text_feats_batch = self.mineclip.encode_text(prompts)
        print(prompts, text_feats_batch.shape)
        assert text_feats_batch.shape == (TEXT_BATCH, 512)

        reward_scores, _ = self.mineclip(
            video_feats, text_tokens=text_feats_batch, is_video_features=True
        )

        return reward_scores

    def get_image_correlation_by_mineclip(self, img, prompt):
        if not self.enable_mineclip:
            raise ValueError("MineCLIP is not enabled. Please use `enable_mineclip=True` when creating the task.")

        video = torch.zeros((1, 1, 3, self.FRAME_HEIGHT, self.FRAME_WIDTH), device=self.device)
        video[0][0] = self.transform(Image.fromarray(img)).to(self.device)
        return self.__run_mineclip(video, [prompt])
    
    def move_camera(self, pos, yaw, pitch) :
        self.env.bridge.moveCamera("construction_camera", pos, yaw, pitch)
    
    def get_blueprint_base64(self) :
        return self.blueprint_img_base64
    
    def get_blueprint_np(self) :
        rgb = base64_to_image(self.blueprint_img_base64, 320, 180)
        return rgb
    
    def get_camera_view(self) :
        return self.env.bridge.getCameraView("construction_camera")

    def get_score(self) :
        camera_view = self.get_camera_view()
        camera_view = base64_to_image(camera_view, 320, 180)
        score = get_image_similarity_by_orb(camera_view, self.blueprint_img_np) / self.baseline_score
        return score
    
    def get_score_by_mineclip(self):
        if not self.enable_mineclip:
            raise ValueError("MineCLIP is not enabled. Please use `enable_mineclip=True` when creating the task.")
        camera_view = self.get_camera_view()
        camera_view = base64_to_image(camera_view, 320, 180)
        camera_view = np.transpose(camera_view, (1, 2, 0))
        score = self.get_image_correlation_by_mineclip(camera_view, self.goal) / self.baseline_score_mineclip
        return score
    
    def step(self, action):
        obs, code_info, events, done, task_info = self.env.step(action)

        task_info = TaskInfo(
            task_id=self.task_id,
            score = self.get_score(),
            is_success=False,
            is_failed=False,
            goal=self.goal,
            guidance=self.guidance,
        )

        return obs, code_info, events, False, task_info

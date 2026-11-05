"""
AI 模型厂商工厂 (支持 LLM / 生图 / 生视频 厂商插件化切换与真实 API 调用 / 高保真 Mock 回退)

技术栈与官方文档参考:
- 阿里百炼 / 通义千问 Qwen (LLM & Text Embedding): https://help.aliyun.com/zh/model-studio/developer-reference/use-qwen-by-calling-api
- 阿里百炼 / Qwen Image 3.0 Pro: https://help.aliyun.com/zh/model-studio/developer-reference/multimodal-generation
- 阿里百炼 / Wan 3.0 Video: https://help.aliyun.com/zh/model-studio/developer-reference/video-generation
"""

import os
import time
import logging
import asyncio
from typing import Dict, Any, List, Optional
import httpx
from app.conf.config import settings

logger = logging.getLogger("provider_factory")

# ──────────────────────────────────────────────────────────────────────────────
# 1. 通义千问 (Qwen) LLM & Embedding 客户端
# ──────────────────────────────────────────────────────────────────────────────
class QwenLLMClient:
    """通义千问官方兼容接口客户端 (OpenAI 协议兼容)"""

    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_URL = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.DASHSCOPE_API_KEY

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "qwen-plus",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """发起千问大语言模型调用；若无 API Key 则自动进入高保真 Mock 模式"""
        start_time = time.time()

        if not self.api_key or self.api_key.strip() == "":
            logger.info("未检测到 DASHSCOPE_API_KEY，切换至 Qwen 高保真 Mock 响应模式")
            return self._mock_chat_completion(messages, model)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    content = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})
                    return {
                        "content": content,
                        "prompt_tokens": usage.get("prompt_tokens", 100),
                        "completion_tokens": usage.get("completion_tokens", 300),
                        "cost": (usage.get("prompt_tokens", 100) * 0.000004) + (usage.get("completion_tokens", 300) * 0.000012),
                        "elapsed_ms": elapsed_ms,
                        "model": model,
                        "is_mock": 0,
                    }
                else:
                    logger.warning(f"Qwen API 响应状态异常 ({resp.status_code}): {resp.text}，启用 Mock 回退")
                    return self._mock_chat_completion(messages, model)
        except Exception as e:
            logger.error(f"调用 Qwen 接口发生网络或协议异常: {str(e)}，自动回退 Mock")
            return self._mock_chat_completion(messages, model)

    async def get_embedding(self, text: str, model: str = "text-embedding-v4") -> List[float]:
        """获取文本 Embedding 向量 (使用 DashScope HTTP API)"""
        if not self.api_key or self.api_key.strip() == "":
            # 伪归一化向量 (1024 维)
            return [0.03125] * 1024

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": model, "input": {"texts": [text]}}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    self.EMBEDDING_URL,
                    headers=headers,
                    json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data["output"]["embeddings"][0]["embedding"]
                else:
                    logger.warning(f"Embedding API 响应异常: {resp.text}")
        except Exception as e:
            logger.warning(f"获取 Embedding 异常: {str(e)}，返回默认向量")
        return [0.03125] * 1024

    def _mock_chat_completion(self, messages: List[Dict[str, str]], model: str) -> Dict[str, Any]:
        """针对电商多智能体业务构建的高拟真 Mock 文本"""
        last_msg = messages[-1]["content"] if messages else ""
        
        if "需求分析" in last_msg or "analyzer" in last_msg.lower():
            mock_text = (
                "【目标受众定位】25-45岁热爱轻量化户外探险与露营的精致生活人群。\n"
                "【核心卖点提炼】\n"
                "1. 航天级 7075 铝合金骨架，仅重 1.1kg，轻量化携带无负担。\n"
                "2. 600D 加厚抗撕裂牛津布，高弹透气人体工学承重达 150kg。\n"
                "3. 3 秒快速折叠收纳系统，紧凑体积随意塞入后备箱与背包。\n"
                "【多语种关键词】Ultralight Camping Chair, Portable Folding Chair, Ergonomic Outdoor Seating, Backpacking Stool."
            )
        elif "文案" in last_msg or "copy" in last_msg.lower() or "planner" in last_msg.lower():
            mock_text = (
                "TITLE: Ultralight Aviation Aluminum Folding Camping Chair - 3s Quick Setup, 330lbs Heavy Duty\n\n"
                "BULLETS:\n"
                "- [FEATHERLIGHT YET ROCK-SOLID] Crafted from aerospace-grade 7075 aluminum alloy, weighing just 2.4 lbs while easily supporting up to 330 lbs.\n"
                "- [3-SECOND RAPID DEPLOYMENT] Patented elastic cord pole structure enables intuitive 3-second setup and teardown anywhere.\n"
                "- [ERGONOMIC COMFORT] Deep bucket seat with breathable dual-side mesh keeps you cool and relieves spinal pressure during long outdoor gatherings.\n"
                "- [COMPACT PACKABILITY] Packs down to a neat 13.8 x 4.7 inches cylindrical carry bag, ideal for trekking, angling, and beach weekends.\n"
                "- [WEATHER-READY DURABILITY] Water-resistant 600D ripstop fabric resists abrasions, UV rays, and heavy outdoor wear.\n\n"
                "DESCRIPTION: Rediscover the backcountry without the heavy load. The Ultralight Aviation Aluminum Folding Chair combines peak engineering with effortless comfort."
            )
        elif "分镜" in last_msg or "storyboard" in last_msg.lower() or "designer" in last_msg.lower():
            mock_text = (
                "分镜规划方案（5镜头 15秒海外带货短视频）：\n"
                "Shot 1 (0-3s): [Hook] 主播在崎岖山顶单手从背包抽出椅子，3秒甩开成型，特写金属扣咬合声。\n"
                "Shot 2 (3-6s): [Pain Point] 对比传统笨重老旧折叠椅的狼狈，凸显 1.1kg 羽量化轻巧。\n"
                "Shot 3 (6-9s): [Demo] 健壮成年人猛烈坐下，微距展现 7075 铝合金骨架与加厚牛津布稳固无晃动。\n"
                "Shot 4 (9-12s): [Lifestyle] 森林日落与溪流营地，主人公端咖啡惬意斜倚，展现人体工学包裹感。\n"
                "Shot 5 (12-15s): [CTA] 3秒收纳塞入背包，弹出独立站特惠倒计时与折扣标牌。"
            )
        elif "审核" in last_msg or "compliance" in last_msg.lower() or "reviewer" in last_msg.lower():
            mock_text = (
                "{\n"
                '  "score": 96.5,\n'
                '  "passed": 1,\n'
                '  "dimensions": {"brand_consistency": 98.0, "platform_compliance": 95.0, "readability": 97.0, "legal_safety": 96.0},\n'
                '  "violations": [],\n'
                '  "suggestions": ["文案整体合规严谨，未出现‘世界第一’等绝对化违禁词", "建议主图添加 330lbs 承重图标以提高转化率"]\n'
                "}"
            )
        else:
            mock_text = f"基于智能体电商生成模型，已成功处理上下文输入并生成高质量营销内容。模型: {model}"

        return {
            "content": mock_text,
            "prompt_tokens": 120,
            "completion_tokens": 320,
            "cost": 0.0035,
            "elapsed_ms": 320,
            "model": f"{model}-mock",
            "is_mock": 1,
        }


# ──────────────────────────────────────────────────────────────────────────────
# 2. Qwen Image 3.0 Pro 生图客户端
# ──────────────────────────────────────────────────────────────────────────────
class WanxImageClient:
    """通义万相 / Qwen Image 3.0 Pro 生图客户端"""

    # 用户指定的专有 Workspace API Endpoint
    SUBMIT_URL = "https://llm-pqoya4ttmg66ljtm.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

    # 高清商品展示样本图 (Unsplash 高清商业级正版素材)
    DEMO_PRODUCT_IMAGES = [
        "https://images.unsplash.com/photo-1510312305653-8ed496efae75?w=1200&q=80",
        "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=1200&q=80",
        "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=1200&q=80",
        "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=1200&q=80",
    ]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.WANX_API_KEY or settings.DASHSCOPE_API_KEY

    async def generate_images(
        self,
        prompt: str,
        n: int = 1,
        size: str = "1024*1024",
        model: str = "qwen-image-3.0-pro",
    ) -> Dict[str, Any]:
        """同步返回结果文生图任务；无 Key 时自动切换高清商品级 Mock"""
        start_time = time.time()

        if not self.api_key or self.api_key.strip() == "":
            logger.info("未检测到 API_KEY，启用 Qwen Image 高保真 Mock 生图模式")
            return self._mock_generate_images(prompt, n, size, model)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt}]
                    }
                ]
            },
            "parameters": {"prompt_extend": True}
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(self.SUBMIT_URL, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    # Qwen Image 3.0 Pro multimodal generation API 返回的是同步图像内容
                    # 结构解析: data["output"]["choices"][0]["message"]["content"][0]["image"]
                    choices = data.get("output", {}).get("choices", [])
                    urls = []
                    for choice in choices:
                        content_list = choice.get("message", {}).get("content", [])
                        for item in content_list:
                            if item.get("type") == "image":
                                urls.append(item.get("image"))
                    
                    if urls:
                        elapsed_ms = int((time.time() - start_time) * 1000)
                        return {
                            "urls": urls,
                            "task_id": data.get("request_id", ""),
                            "elapsed_ms": elapsed_ms,
                            "cost": 0.08 * n,
                            "is_mock": 0,
                            "model": model,
                        }
                    else:
                        logger.warning(f"Qwen Image 响应中未找到图片 URL: {data}")
                else:
                    logger.warning(f"Qwen Image 响应状态异常 ({resp.status_code}): {resp.text}")
        except Exception as e:
            logger.error(f"Qwen Image 生图请求异常: {str(e)}，自动回退 Mock")

        return self._mock_generate_images(prompt, n, size, model)

    def _mock_generate_images(self, prompt: str, n: int, size: str, model: str) -> Dict[str, Any]:
        """返回高质量电商商品图片链接与详细元数据"""
        selected_urls = []
        for i in range(n):
            url = self.DEMO_PRODUCT_IMAGES[i % len(self.DEMO_PRODUCT_IMAGES)]
            selected_urls.append(url)

        return {
            "urls": selected_urls,
            "task_id": f"mock_wanx_{int(time.time()*1000)}",
            "elapsed_ms": 650,
            "cost": 0.0,
            "is_mock": 1,
            "model": f"{model}-mock",
        }


# ──────────────────────────────────────────────────────────────────────────────
# 3. 万相 Wan 3.0 Video 生视频客户端
# ──────────────────────────────────────────────────────────────────────────────
class KlingVideoClient:
    """通义万相 Wan 3.0 Video 生视频客户端"""

    SUBMIT_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
    TASK_URL = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

    # 高清产品动态视频样本 (电商带货场景演示流)
    DEMO_PRODUCT_VIDEOS = [
        "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
        "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4",
        "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4",
    ]

    def __init__(self, api_key: Optional[str] = None):
        # 用户要求替换可灵，所以这里实际是万相视频，为了不改外面代码类名保留不变，或外层可以不依赖类名。
        # 实际调用的已经是 Wan 3.0 API
        self.api_key = api_key or settings.DASHSCOPE_API_KEY

    async def generate_video(
        self,
        prompt: str,
        duration: int = 5,
        aspect_ratio: str = "16:9",
        model: str = "wan3.0-video",
        image_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建文生视频任务；无 Key 时自动切换商品演示 Mock"""
        start_time = time.time()

        if not self.api_key or self.api_key.strip() == "":
            logger.info("未检测到 DASHSCOPE_API_KEY，启用 Wan 3.0 高保真 Mock 视频生成模式")
            return self._mock_generate_video(prompt, duration, aspect_ratio, model)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable"
        }
        # 将比例转换为 adaptive (Wan 3.0 支持 adaptive 适配)
        payload = {
            "model": model,
            "input": {"prompt": prompt},
            "parameters": {
                "resolution": "480P", 
                "ratio": "adaptive", 
                "duration": duration
            }
        }
        # 如果是图生视频，可以添加 image 字段 (如 API 支持)
        if image_url:
            payload["input"]["image_url"] = image_url

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(self.SUBMIT_URL, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    task_id = data.get("output", {}).get("task_id")
                    logger.info(f"Wan 3.0 视频任务已提交，TaskID: {task_id}，正在等待视频处理...")

                    # 轮询查询视频任务 (视频生成比较慢，可能需要几分钟，此处简化轮询)
                    for _ in range(60):
                        await asyncio.sleep(5)
                        query_resp = await client.get(
                            self.TASK_URL.format(task_id=task_id),
                            headers={"Authorization": f"Bearer {self.api_key}"},
                        )
                        if query_resp.status_code == 200:
                            q_data = query_resp.json()
                            status = q_data.get("output", {}).get("task_status")
                            if status == "SUCCEEDED":
                                video_url = q_data["output"]["video_url"]
                                elapsed_ms = int((time.time() - start_time) * 1000)
                                return {
                                    "video_url": video_url,
                                    "task_id": task_id,
                                    "duration": duration,
                                    "elapsed_ms": elapsed_ms,
                                    "cost": 0.50,
                                    "is_mock": 0,
                                    "model": model,
                                }
                            elif status in ["FAILED", "CANCELED"]:
                                logger.warning(f"Wan 3.0 视频生成失败: {q_data}，切换 Mock")
                                break
        except Exception as e:
            logger.error(f"Wan 3.0 视频调用发生异常: {str(e)}，自动回退 Mock")

        return self._mock_generate_video(prompt, duration, aspect_ratio, model)

    def _mock_generate_video(self, prompt: str, duration: int, aspect_ratio: str, model: str) -> Dict[str, Any]:
        """返回高质量演示视频链接与分镜元数据"""
        video_url = self.DEMO_PRODUCT_VIDEOS[0]
        return {
            "video_url": video_url,
            "task_id": f"mock_wan3_video_{int(time.time()*1000)}",
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "elapsed_ms": 1200,
            "cost": 0.0,
            "is_mock": 1,
            "model": f"{model}-mock",
        }


# ──────────────────────────────────────────────────────────────────────────────
# 4. 统一门面工厂 ProviderFactory
# ──────────────────────────────────────────────────────────────────────────────
class ProviderFactory:
    """提供统一的单例或实例模型客户端访问入口"""

    @staticmethod
    def get_llm_client(provider_type: str = "qwen") -> QwenLLMClient:
        return QwenLLMClient()

    @staticmethod
    def get_image_client(provider_type: str = "wanx") -> WanxImageClient:
        return WanxImageClient()

    @staticmethod
    def get_video_client(provider_type: str = "kling") -> KlingVideoClient:
        return KlingVideoClient()

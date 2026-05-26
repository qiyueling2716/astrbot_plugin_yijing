"""
易经塔罗占卜插件 for AstrBot
作者: 长歌&月凌
功能: 提供易经占卜、卦象查询、六爻分析等功能
API: https://yaoguang.fa945s.top
"""

import json
import random
from typing import Dict, Any, Optional, List

import aiohttp
from astrbot.api.all import *
from astrbot.api.message_components import *
from astrbot.api.event import filter, AstrMessageEvent

# API配置
API_BASE_URL = "https://yaoguang.fa945s.top"
API_TIMEOUT = 30

# 六十四卦列表（与 API 返回的 name 字段完全对齐）
HEXAGRAM_NAMES = {
    1: "乾为天", 2: "坤为地", 3: "水雷屯", 4: "山水蒙", 5: "水天需", 6: "天水讼",
    7: "地水师", 8: "水地比", 9: "风天小畜", 10: "天泽履", 11: "地天泰", 12: "天地否",
    13: "天火同人", 14: "火天大有", 15: "地山谦", 16: "雷地豫", 17: "泽雷随", 18: "山风蛊",
    19: "地泽临", 20: "风地观", 21: "火雷噬嗑", 22: "山火贲", 23: "山地剥", 24: "地雷复",
    25: "天雷无妄", 26: "山天大畜", 27: "山雷颐", 28: "泽风大过", 29: "坎为水", 30: "离为火",
    31: "泽山咸", 32: "雷风恒", 33: "天山遯", 34: "雷天大壮", 35: "火地晋", 36: "地火明夷",
    37: "风火家人", 38: "火泽睽", 39: "水山蹇", 40: "雷水解", 41: "山泽损", 42: "风雷益",
    43: "泽天夬", 44: "天风姤", 45: "泽地萃", 46: "地风升", 47: "泽水困", 48: "水风井",
    49: "泽火革", 50: "火风鼎", 51: "震为雷", 52: "艮为山", 53: "风山渐", 54: "雷泽归妹",
    55: "雷火丰", 56: "火山旅", 57: "巽为风", 58: "兑为泽", 59: "风水涣", 60: "水泽节",
    61: "风泽中孚", 62: "雷山小过", 63: "水火既济", 64: "火水未济"
}


@register("yijing", "长歌&月凌", "易经塔罗占卜插件", "1.0.0", "https://github.com/yourname/astrbot_plugin_yijing")
class YiJingPlugin(Star):
    """易经占卜插件"""
    
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.session = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建aiohttp会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self.session
    
    async def _api_request(self, method: str, endpoint: str, data: dict = None) -> Optional[Dict]:
        """发送API请求"""
        session = await self._get_session()
        url = f"{API_BASE_URL}{endpoint}"
        
        try:
            if method.upper() == "GET":
                async with session.get(url) as response:
                    text = await response.text()
                    logger.debug(f"API GET {endpoint} -> status:{response.status} body:{text[:300]}")
                    if response.status == 200:
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            logger.error(f"API返回非JSON: {text[:200]}")
                            return None
                    else:
                        logger.error(f"API请求失败: {response.status}, 响应: {text[:200]}")
                        return None
            else:
                async with session.post(url, json=data) as response:
                    text = await response.text()
                    logger.debug(f"API POST {endpoint} -> status:{response.status} body:{text[:300]}")
                    if response.status == 200:
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            logger.error(f"API返回非JSON: {text[:200]}")
                            return None
                    else:
                        logger.error(f"API请求失败: {response.status}, 响应: {text[:200]}")
                        return None
        except Exception as e:
            logger.error(f"API请求异常: {e}")
            return None
    
    def _is_api_success(self, result: Optional[Dict]) -> bool:
        '''判断API响应是否成功。兼容 "success": true 和 "code": 200 两种格式。'''
        if not result:
            return False
        success = result.get("success")
        if success in (True, "true", "True", 1, "1"):
            return True
        code = result.get("code")
        if code in (200, "200"):
            return True
        return False
    
    def _extract_data(self, result: Optional[Dict]) -> Optional[Dict]:
        '''从API响应中提取data字段，自动处理一层或两层嵌套。'''
        if not result:
            return None
        data = result.get("data")
        if not isinstance(data, dict):
            return None
        # 处理两层嵌套: {"data": {"data": {...}}}
        if "data" in data and isinstance(data.get("data"), dict):
            inner = data.get("data")
            # 再检查是否还有第三层（列表接口）
            if "data" in inner and isinstance(inner.get("data"), dict):
                return inner.get("data")
            return inner
        return data
    
    async def _quick_divination(self, question: str = "", method: str = "random") -> Optional[Dict]:
        """快速占卜"""
        payload = {"question": question or "随机占卜", "method": method}
        result = await self._api_request("POST", "/api/standalone/yijing/quick-divination", payload)
        
        if self._is_api_success(result):
            return self._extract_data(result)
        return None
    
    async def _get_hexagram(self, hexagram_id: int) -> Optional[Dict]:
        """获取卦象详情"""
        result = await self._api_request("GET", f"/api/yijing/hexagram/{hexagram_id}")
        
        if self._is_api_success(result):
            data = self._extract_data(result)
            if data and isinstance(data, dict):
                # 校验：如果 API 返回的 name 与本地映射表不一致，记录日志（服务端数据已修正，不应触发）
                correct_name = HEXAGRAM_NAMES.get(hexagram_id)
                api_name = data.get("name")
                if correct_name and api_name and api_name != correct_name:
                    logger.warning(
                        f"API name 异常: id={hexagram_id} "
                        f"api_name='{api_name}' 期望 '{correct_name}'，已自动修正"
                    )
                    data["name"] = correct_name
                return data
            else:
                logger.warning(f"卦象 {hexagram_id} 的 data 为空或类型异常: {type(data)}")
        else:
            logger.warning(f"获取卦象 {hexagram_id} 失败: result={result}")
        
        return None
    
    # ==================== LLM 函数工具 ====================
    
    @filter.llm_tool(name="yijing_divination")
    async def func_divination(self, event: AstrMessageEvent, question: str, method: str = "random") -> str:
        '''进行易经占卜，可针对具体问题给出卦象分析和吉凶趋势。支持时间起卦、随机起卦、钱币起卦三种方式。
        
        Args:
            question(string): 占卜的问题或意图
            method(string): 起卦方法，可选值为 time（时间起卦）、random（随机起卦）、coin（钱币起卦），默认为 random
        '''
        try:
            result = await self._quick_divination(question, method)
            
            if result:
                original = result.get("original", {})
                changed = result.get("changed", {})
                liu_yao = result.get("liu_yao_analysis", {})
                dong_bian = liu_yao.get("dong_bian", {})
                
                return json.dumps({
                    "success": True,
                    "question": question,
                    "method": method,
                    "original_hexagram": original.get("name"),
                    "original_judgment": original.get("judgment", "")[:200],
                    "changed_hexagram": changed.get("name"),
                    "changing_lines": result.get("changing_lines", []),
                    "fortune_tendency": dong_bian.get("fortune_tendency", ""),
                    "interpretation_hint": result.get("interpretation_hint", "")
                }, ensure_ascii=False)
            else:
                return json.dumps({
                    "success": False,
                    "error": "占卜失败，请稍后重试",
                    "question": question
                }, ensure_ascii=False)
        except Exception as e:
            logger.error(f"占卜函数异常: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
    
    @filter.llm_tool(name="yijing_get_hexagram")
    async def func_get_hexagram(self, event: AstrMessageEvent, hexagram_id: int) -> str:
        '''获取易经六十四卦中指定卦象的详细信息，包括卦辞、象辞、爻辞等。
        
        Args:
            hexagram_id(number): 卦象ID，范围1-64
        '''
        try:
            if not isinstance(hexagram_id, int) or hexagram_id < 1 or hexagram_id > 64:
                return json.dumps({
                    "success": False,
                    "error": f"卦象ID必须是1-64之间的整数，收到: {hexagram_id}"
                }, ensure_ascii=False)
            
            data = await self._get_hexagram(hexagram_id)
            
            if data:
                lines = data.get("lines", [])
                formatted_lines = []
                for line in lines[:6]:
                    formatted_lines.append({
                        "position": line.get("position"),
                        "type": "阳" if line.get("type") == "yang" else "阴",
                        "text": line.get("text", ""),
                        "explanation": line.get("textExplanation", "")[:100]
                    })
                
                return json.dumps({
                    "success": True,
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "chinese": data.get("chinese"),
                    "judgment": data.get("judgment", ""),
                    "judgment_explanation": data.get("judgmentExplanation", ""),
                    "image": data.get("image", ""),
                    "meaning": data.get("meaning", ""),
                    "lines": formatted_lines
                }, ensure_ascii=False)
            else:
                return json.dumps({
                    "success": False,
                    "error": f"未找到ID为 {hexagram_id} 的卦象，请检查API服务是否正常"
                }, ensure_ascii=False)
        except Exception as e:
            logger.error(f"获取卦象异常: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
    
    @filter.llm_tool(name="yijing_random_hexagram")
    async def func_random_hexagram(self, event: AstrMessageEvent) -> str:
        '''随机获取一卦，用于随机占卜或介绍易经。
        
        Args:
            无参数
        '''
        random_id = random.randint(1, 64)
        try:
            data = await self._get_hexagram(random_id)
            
            if data:
                lines = data.get("lines", [])
                formatted_lines = []
                for line in lines[:6]:
                    formatted_lines.append({
                        "position": line.get("position"),
                        "type": "阳" if line.get("type") == "yang" else "阴",
                        "text": line.get("text", ""),
                        "explanation": line.get("textExplanation", "")[:100]
                    })
                
                return json.dumps({
                    "success": True,
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "chinese": data.get("chinese"),
                    "judgment": data.get("judgment", ""),
                    "judgment_explanation": data.get("judgmentExplanation", ""),
                    "image": data.get("image", ""),
                    "meaning": data.get("meaning", ""),
                    "lines": formatted_lines
                }, ensure_ascii=False)
            else:
                return json.dumps({
                    "success": False,
                    "error": "随机获取卦象失败"
                }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
    
    @filter.llm_tool(name="yijing_list_hexagrams")
    async def func_list_hexagrams(self, event: AstrMessageEvent, page: int = 1) -> str:
        '''获取六十四卦列表，可按页查看所有卦象名称和ID。
        
        Args:
            page(number): 页码，从1开始，每页16卦，默认为1
        '''
        try:
            items_per_page = 16
            total_items = 64
            total_pages = (total_items + items_per_page - 1) // items_per_page
            
            if page < 1 or page > total_pages:
                page = 1
            
            start = (page - 1) * items_per_page + 1
            end = min(start + items_per_page - 1, total_items)
            
            hexagrams = []
            for i in range(start, end + 1):
                hexagrams.append({
                    "id": i,
                    "name": HEXAGRAM_NAMES.get(i, "未知")
                })
            
            return json.dumps({
                "success": True,
                "page": page,
                "total_pages": total_pages,
                "total_items": total_items,
                "hexagrams": hexagrams
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
    
    # ==================== 传统命令 ====================
    
    @command("yijing div")
    async def cmd_divination(self, event: AstrMessageEvent, question: str = None):
        """快速占卜（随机起卦）"""
        question_text = question if question else "随机占卜"
        
        yield event.plain_result(f"🔮 正在为您占卜「{question_text}」...")
        
        result = await self._quick_divination(question_text, "random")
        
        if result:
            original = result.get("original", {})
            changed = result.get("changed", {})
            liu_yao = result.get("liu_yao_analysis", {})
            dong_bian = liu_yao.get("dong_bian", {})
            
            message = f"""🔮 **易经占卜结果**

📝 **问题**：{question_text}
🎴 **本卦**：{original.get('name', '未知')} ({original.get('chinese', '')})
📜 **卦辞**：{original.get('judgment', '无')[:150]}

🔄 **变卦**：{changed.get('name', '无')} ({changed.get('chinese', '')})
⚡ **动爻**：第{result.get('changing_lines', [])}爻

📊 **趋势**：{dong_bian.get('fortune_tendency', '')}

✨ {result.get('interpretation_hint', '')}

---
本服务提供的是文化与娱乐导向的解读，不应替代医疗，法律，或财务等方面的建议
"""
            yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 占卜失败，请稍后再试。")
    
    @command("yijing time")
    async def cmd_time_divination(self, event: AstrMessageEvent, question: str = None):
        """以当前时间起卦"""
        question_text = question if question else "运势占卜"
        
        yield event.plain_result(f"⏰ 正在以当前时间起卦，为您占卜「{question_text}」...")
        
        result = await self._quick_divination(question_text, "time")
        
        if result:
            original = result.get("original", {})
            changed = result.get("changed", {})
            dong_bian = result.get("liu_yao_analysis", {}).get("dong_bian", {})
            
            message = f"""🔮 **时间起卦结果**

📝 **问题**：{question_text}
🎴 **本卦**：{original.get('name', '未知')}

🔄 **变卦**：{changed.get('name', '无')}
⚡ **动爻**：第{result.get('changing_lines', [])}爻

📊 **趋势**：{dong_bian.get('fortune_tendency', '')}

✨ {result.get('interpretation_hint', '')}

---
本服务提供的是文化与娱乐导向的解读，不应替代医疗，法律，或财务等方面的建议
"""
            yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 占卜失败，请稍后再试。")
    
    @command("yijing coin")
    async def cmd_coin_divination(self, event: AstrMessageEvent, question: str = None):
        """钱币起卦（六爻）"""
        question_text = question if question else "六爻占卜"
        
        yield event.plain_result(f"💰 正在模拟钱币起卦，为您占卜「{question_text}」...")
        
        result = await self._quick_divination(question_text, "coin")
        
        if result:
            original = result.get("original", {})
            changed = result.get("changed", {})
            dong_bian = result.get("liu_yao_analysis", {}).get("dong_bian", {})
            
            message = f"""🔮 **钱币起卦（六爻）结果**

📝 **问题**：{question_text}
🎴 **本卦**：{original.get('name', '未知')}

🔄 **变卦**：{changed.get('name', '无')}
⚡ **动爻**：第{result.get('changing_lines', [])}爻

📊 **趋势**：{dong_bian.get('fortune_tendency', '')}

✨ {result.get('interpretation_hint', '')}

---
本服务提供的是文化与娱乐导向的解读，不应替代医疗，法律，或财务等方面的建议
"""
            yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 占卜失败，请稍后再试。")
    
    @command("yijing hexagram")
    async def cmd_hexagram(self, event: AstrMessageEvent, hexagram_id: str = None):
        """查看卦象详情"""
        if not hexagram_id:
            yield event.plain_result("请提供卦象ID，例如：`/yijing hexagram 1`\n可用 `/yijing list` 查看卦象列表")
            return
        
        try:
            hid = int(hexagram_id)
            if hid < 1 or hid > 64:
                yield event.plain_result("卦象ID范围是 1-64")
                return
        except ValueError:
            yield event.plain_result("请输入数字格式的卦象ID")
            return
        
        data = await self._get_hexagram(hid)
        
        if data:
            lines = data.get("lines", [])
            lines_text = ""
            for line in lines[:3]:
                lines_text += f"  {line.get('position')}. {line.get('text', '')}\n"
            
            message = f"""📖 **{data.get('name', '未知')}卦** ({data.get('chinese', '')})

🔢 **卦序**：{data.get('id')}
☯ **卦象**：上{data.get('upper', '?')}下{data.get('lower', '?')}

📜 **卦辞**：
{data.get('judgment', '无')[:150]}

🌊 **象辞**：
{data.get('image', '无')[:150]}

📝 **卦义**：
{data.get('meaning', '无')[:100]}

**爻辞**：
{lines_text}
"""
            if len(lines) > 3:
                message += f"\n... (共{len(lines)}爻，使用 `/yijing hexagram {hid}` 查看完整)"
            
            message += "\n\n---\n本服务提供的是文化与娱乐导向的解读，不应替代医疗，法律，或财务等方面的建议"
            yield event.plain_result(message)
        else:
            yield event.plain_result(f"❌ 未找到ID为 {hid} 的卦象。")
    
    @command("yijing random")
    async def cmd_random_hexagram(self, event: AstrMessageEvent):
        """随机获取一卦"""
        random_id = random.randint(1, 64)
        data = await self._get_hexagram(random_id)
        
        if data:
            message = f"""🎲 **随机卦象**

📖 **{data.get('name', '未知')}卦** ({data.get('chinese', '')})

📜 **卦辞**：
{data.get('judgment', '无')[:150]}

💡 使用 `/yijing hexagram {random_id}` 查看完整卦象

---
本服务提供的是文化与娱乐导向的解读，不应替代医疗，法律，或财务等方面的建议
"""
            yield event.plain_result(message)
        else:
            yield event.plain_result("❌ 获取卦象失败")
    
    @command("yijing list")
    async def cmd_list_hexagrams(self, event: AstrMessageEvent, page: str = "1"):
        """查看六十四卦列表"""
        try:
            page_num = int(page)
        except ValueError:
            page_num = 1
        
        items_per_page = 16
        total_items = 64
        total_pages = (total_items + items_per_page - 1) // items_per_page
        
        if page_num < 1 or page_num > total_pages:
            yield event.plain_result(f"页数范围是 1-{total_pages}")
            return
        
        start = (page_num - 1) * items_per_page + 1
        end = min(start + items_per_page - 1, total_items)
        
        message = f"📚 **六十四卦列表** (第{page_num}/{total_pages}页)\n\n"
        
        for i in range(start, end + 1):
            name = HEXAGRAM_NAMES.get(i, "未知")
            message += f"`{i:2d}`. {name}\n"
        
        message += f"\n📖 使用 `/yijing hexagram <id>` 查看卦象详情"
        if page_num > 1:
            message += f"\n⏮️ 上一页: `/yijing list {page_num-1}`"
        if page_num < total_pages:
            message += f"\n⏭️ 下一页: `/yijing list {page_num+1}`"
        
        yield event.plain_result(message)
    
    @command("yijing")
    async def cmd_yijing(self, event: AstrMessageEvent):
        """易经占卜主命令"""
        yield event.plain_result(f"""
📜 **易经占卜插件 v1.0.0**

| 命令 | 说明 |
|------|------|
| `/yijing div [问题]` | 快速占卜（随机起卦） |
| `/yijing time [问题]` | 以当前时间起卦 |
| `/yijing coin [问题]` | 钱币起卦（六爻） |
| `/yijing hexagram <id>` | 查看卦象详情（1-64） |
| `/yijing random` | 随机获取一卦 |
| `/yijing list [页码]` | 查看六十四卦列表 |

🤖 **LLM函数工具**: ✅ 已启用
💡 AI可自动调用占卜功能

📚 示例：`/yijing div 今天运势如何`

---
本服务提供的是文化与娱乐导向的解读，不应替代医疗，法律，或财务等方面的建议
        """)
    
    @command("yijing help")
    async def cmd_help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        async for result in self.cmd_yijing(event):
            yield result
    
    async def terminate(self):
        """插件卸载时关闭会话"""
        if self.session and not self.session.closed:
            await self.session.close()

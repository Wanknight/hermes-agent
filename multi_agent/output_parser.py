"""
Output Parser - LLM 输出解析器

负责：
1. 多格式解析（JSON、YAML、文本）
2. Pydantic Schema 验证
3. 自动修复常见错误
4. 容错处理
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional, Type, TypeVar, Union

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class ParseResult:
    """解析结果"""
    
    def __init__(
        self,
        success: bool,
        data: Optional[Dict[str, Any]] = None,
        model: Optional[BaseModel] = None,
        error: Optional[str] = None,
        raw_text: str = "",
        format_detected: str = "",
        fixes_applied: list = None,
    ):
        self.success = success
        self.data = data
        self.model = model
        self.error = error
        self.raw_text = raw_text
        self.format_detected = format_detected
        self.fixes_applied = fixes_applied or []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        if self.model:
            return self.model.model_dump()
        return self.data or {}


class OutputParser:
    """LLM 输出解析器"""
    
    # 字段名映射（常见变体）
    FIELD_MAPPINGS = {
        # 分类输出
        "message_type": "type",
        "msg_type": "type",
        "kind": "type",
        
        # 审议输出
        "approved": "decision",
        "status": "decision",
        "comment": "comments",
        "note": "comments",
        
        # 规划输出
        "phase_list": "phases",
        "step_list": "steps",
        
        # 通用
        "agent_id": "agent",
        "agent_name": "agent",
    }
    
    # 类型修正映射
    TYPE_FIXES = {
        "approve": "approved",
        "reject": "rejected",
        "approve\n": "approved",
        "reject\n": "rejected",
    }
    
    @classmethod
    def parse(cls, text: str) -> ParseResult:
        """解析 LLM 输出文本
        
        自动检测格式并解析
        
        Args:
            text: LLM 输出文本
            
        Returns:
            ParseResult 对象
        """
        if not text:
            return ParseResult(
                success=False,
                error="Empty output",
                raw_text=text
            )
        
        # 尝试各种格式
        data, fmt = cls._try_parse_json(text)
        if data:
            return ParseResult(
                success=True,
                data=data,
                raw_text=text,
                format_detected=fmt
            )
        
        data, fmt = cls._try_parse_yaml(text)
        if data:
            return ParseResult(
                success=True,
                data=data,
                raw_text=text,
                format_detected=fmt
            )
        
        # 尝试智能提取
        data = cls._smart_extract(text)
        if data:
            return ParseResult(
                success=True,
                data=data,
                raw_text=text,
                format_detected="smart_extract"
            )
        
        return ParseResult(
            success=False,
            error="Failed to parse output",
            raw_text=text
        )
    
    @classmethod
    def parse_to_model(
        cls,
        text: str,
        model_class: Type[T],
        auto_fix: bool = True,
    ) -> ParseResult:
        """解析到 Pydantic 模型
        
        Args:
            text: LLM 输出文本
            model_class: Pydantic 模型类
            auto_fix: 是否自动修复错误
            
        Returns:
            ParseResult 对象，model 字段包含验证后的模型实例
        """
        # 先解析为字典
        parse_result = cls.parse(text)
        
        if not parse_result.success:
            return parse_result
        
        data = parse_result.data
        
        # 尝试创建模型
        try:
            model = model_class(**data)
            parse_result.model = model
            return parse_result
        except ValidationError as e:
            if not auto_fix:
                return ParseResult(
                    success=False,
                    error=str(e),
                    data=data,
                    raw_text=text,
                    format_detected=parse_result.format_detected
                )
            
            # 尝试自动修复
            fixed_data, fixes = cls._auto_fix(data, model_class, e)
            parse_result.fixes_applied = fixes
            
            if fixed_data:
                try:
                    model = model_class(**fixed_data)
                    parse_result.model = model
                    parse_result.data = fixed_data
                    logger.info(f"Auto-fixed validation errors: {fixes}")
                    return parse_result
                except ValidationError as e2:
                    logger.warning(f"Auto-fix failed: {e2}")
            
            return ParseResult(
                success=False,
                error=str(e),
                data=data,
                raw_text=text,
                format_detected=parse_result.format_detected,
                fixes_applied=fixes
            )
    
    @classmethod
    def _try_parse_json(cls, text: str) -> tuple[Optional[Dict], str]:
        """尝试解析 JSON
        
        Returns:
            (data, format) 元组，失败返回 (None, "")
        """
        text = text.strip()
        
        # 1. 直接解析
        try:
            return json.loads(text), "json_direct"
        except json.JSONDecodeError:
            pass
        
        # 2. 提取 ```json 代码块
        match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if match:
            try:
                return json.loads(match.group(1)), "json_code_block"
            except json.JSONDecodeError:
                pass
        
        # 3. 提取 ``` 代码块（无语言标记）
        match = re.search(r'```\s*([\s\S]*?)\s*```', text)
        if match:
            try:
                return json.loads(match.group(1)), "json_code_block_plain"
            except json.JSONDecodeError:
                pass
        
        # 4. 提取花括号内容
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group()), "json_braces"
            except json.JSONDecodeError:
                # 尝试修复常见 JSON 错误
                fixed = cls._fix_json(match.group())
                if fixed:
                    try:
                        return json.loads(fixed), "json_fixed"
                    except json.JSONDecodeError:
                        pass
        
        return None, ""
    
    @classmethod
    def _try_parse_yaml(cls, text: str) -> tuple[Optional[Dict], str]:
        """尝试解析 YAML"""
        try:
            import yaml
            data = yaml.safe_load(text)
            if isinstance(data, dict):
                return data, "yaml"
        except Exception:
            pass
        
        # 尝试提取 YAML 代码块
        match = re.search(r'```yaml\s*([\s\S]*?)\s*```', text)
        if match:
            try:
                import yaml
                data = yaml.safe_load(match.group(1))
                if isinstance(data, dict):
                    return data, "yaml_code_block"
            except Exception:
                pass
        
        return None, ""
    
    @classmethod
    def _smart_extract(cls, text: str) -> Optional[Dict]:
        """智能提取关键信息
        
        当无法解析结构化数据时，尝试从文本中提取关键信息
        """
        text_lower = text.lower()
        
        # 检测是否是闲聊
        chat_keywords = ["闲聊", "chat", "问候", "寒暄", "greeting", "打招呼"]
        if any(kw in text_lower for kw in chat_keywords):
            return {
                "type": "chat",
                "response": text
            }
        
        # 检测审批决定
        if "approved" in text_lower or "通过" in text or "同意" in text:
            return {
                "decision": "approved",
                "comments": text
            }
        if "rejected" in text_lower or "驳回" in text or "拒绝" in text:
            return {
                "decision": "rejected",
                "comments": text
            }
        
        # 尝试提取键值对
        result = {}
        
        # 提取 type: xxx
        type_match = re.search(r'type\s*[:：]\s*["\']?(\w+)["\']?', text, re.IGNORECASE)
        if type_match:
            result["type"] = type_match.group(1).lower()
        
        # 提取 decision: xxx
        decision_match = re.search(r'decision\s*[:：]\s*["\']?(\w+)["\']?', text, re.IGNORECASE)
        if decision_match:
            result["decision"] = decision_match.group(1).lower()
        
        return result if result else None
    
    @classmethod
    def _fix_json(cls, json_str: str) -> Optional[str]:
        """修复常见 JSON 错误"""
        import re
        
        # 移除尾部逗号
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
        
        # 修复单引号为双引号
        # 但要小心不要破坏字符串内的单引号
        # 简单处理：替换单引号包裹的键和值
        json_str = re.sub(r"'([^']+)'", r'"\1"', json_str)
        
        # 修复未引用的键
        json_str = re.sub(r'(\w+)\s*:', r'"\1":', json_str)
        # 但这会破坏已引用的键，需要更精细的处理
        
        return json_str
    
    @classmethod
    def _auto_fix(
        cls,
        data: Dict[str, Any],
        model_class: Type[T],
        error: ValidationError,
    ) -> tuple[Optional[Dict], list]:
        """自动修复验证错误
        
        Returns:
            (fixed_data, fixes_list) 元组
        """
        fixes = []
        fixed_data = data.copy()
        
        for err in error.errors():
            loc = err.get("loc", ())
            err_type = err.get("type", "")
            msg = err.get("msg", "")
            
            # 缺少必填字段 - 尝试设置默认值
            if err_type == "missing":
                field_name = loc[0] if loc else ""
                default_value = cls._get_default_value(model_class, field_name)
                if default_value is not None:
                    fixed_data[field_name] = default_value
                    fixes.append(f"Added default value for '{field_name}': {default_value}")
            
            # 类型错误 - 尝试转换
            elif "type" in err_type.lower():
                field_name = loc[0] if loc else ""
                if field_name in fixed_data:
                    converted = cls._convert_type(fixed_data[field_name], err_type)
                    if converted is not None:
                        fixed_data[field_name] = converted
                        fixes.append(f"Converted '{field_name}' type")
            
            # 枚举值错误 - 尝试映射
            elif "enum" in err_type.lower() or "literal" in err_type.lower():
                field_name = loc[0] if loc else ""
                if field_name in fixed_data:
                    mapped = cls._map_enum_value(field_name, fixed_data[field_name])
                    if mapped is not None:
                        fixed_data[field_name] = mapped
                        fixes.append(f"Mapped '{field_name}' value: {fixed_data[field_name]} -> {mapped}")
        
        # 应用字段名映射
        for old_name, new_name in cls.FIELD_MAPPINGS.items():
            if old_name in fixed_data and new_name not in fixed_data:
                fixed_data[new_name] = fixed_data.pop(old_name)
                fixes.append(f"Renamed field '{old_name}' -> '{new_name}'")
        
        # 应用类型值修正
        for key, value in fixed_data.items():
            if isinstance(value, str) and value in cls.TYPE_FIXES:
                fixed_data[key] = cls.TYPE_FIXES[value]
                fixes.append(f"Fixed value '{value}' -> '{cls.TYPE_FIXES[value]}'")
        
        return fixed_data if fixes else None, fixes
    
    @classmethod
    def _get_default_value(cls, model_class: Type[T], field_name: str) -> Any:
        """获取字段的默认值"""
        if hasattr(model_class, "model_fields"):
            field_info = model_class.model_fields.get(field_name)
            if field_info and field_info.default is not None:
                return field_info.default
            if field_info and field_info.default_factory is not None:
                return field_info.default_factory()
        return None
    
    @classmethod
    def _convert_type(cls, value: Any, err_type: str) -> Any:
        """尝试转换类型"""
        if "int" in err_type:
            try:
                return int(value)
            except (ValueError, TypeError):
                pass
        elif "float" in err_type:
            try:
                return float(value)
            except (ValueError, TypeError):
                pass
        elif "bool" in err_type:
            if isinstance(value, str):
                return value.lower() in ("true", "yes", "1")
            return bool(value)
        elif "list" in err_type:
            if isinstance(value, str):
                # 尝试解析为列表
                if "," in value:
                    return [v.strip() for v in value.split(",")]
                return [value]
        return None
    
    @classmethod
    def _map_enum_value(cls, field_name: str, value: Any) -> Optional[str]:
        """映射枚举值"""
        # 决定字段特殊处理
        if field_name == "decision":
            value_str = str(value).lower().strip()
            if value_str in ("approve", "通过", "同意", "yes", "ok"):
                return "approved"
            if value_str in ("reject", "驳回", "拒绝", "no", "deny"):
                return "rejected"
        
        # 类型字段特殊处理
        if field_name == "type":
            value_str = str(value).lower().strip()
            if value_str in ("decree", "旨意", "任务", "task"):
                return "decree"
            if value_str in ("chat", "闲聊", "问候", "greeting"):
                return "chat"
        
        return None


# ============================================================================
# 便捷函数
# ============================================================================

def parse_output(
    text: str,
    model_class: Optional[Type[T]] = None,
    auto_fix: bool = True,
) -> ParseResult:
    """解析 LLM 输出
    
    Args:
        text: LLM 输出文本
        model_class: 可选的 Pydantic 模型类
        auto_fix: 是否自动修复错误
        
    Returns:
        ParseResult 对象
    """
    if model_class:
        return OutputParser.parse_to_model(text, model_class, auto_fix)
    return OutputParser.parse(text)


def parse_classification(text: str) -> ParseResult:
    """解析太子分类输出"""
    from .output_schemas import ClassificationOutput
    return OutputParser.parse_to_model(text, ClassificationOutput)


def parse_plan(text: str) -> ParseResult:
    """解析中书规划输出"""
    from .output_schemas import PlanOutput
    return OutputParser.parse_to_model(text, PlanOutput)


def parse_review(text: str) -> ParseResult:
    """解析门下审议输出"""
    from .output_schemas import ReviewOutput
    return OutputParser.parse_to_model(text, ReviewOutput)


def parse_dispatch(text: str) -> ParseResult:
    """解析尚书画发输出"""
    from .output_schemas import DispatchOutput
    return OutputParser.parse_to_model(text, DispatchOutput)

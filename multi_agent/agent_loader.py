"""
Agent Loader - 加载和管理 Agent 角色定义

支持从 YAML 文件加载 Agent 定义，包括：
- 内置定义 (multi_agent/agents/)
- 用户自定义定义 (~/.hermes/agents/)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml

from hermes_constants import get_hermes_home


@dataclass
class AgentRole:
    """Agent 角色定义"""
    
    id: str                          # 唯一标识符 (e.g., "taizi", "zhongshu")
    name: str                        # 显示名称 (e.g., "太子", "中书省")
    description: str                 # 角色描述
    tier: int                        # 层级: 1=入口, 2=中枢, 3=执行
    prompt: str                      # 系统提示词
    
    # 能力配置
    capabilities: List[str] = field(default_factory=list)
    tools_allowed: List[str] = field(default_factory=list)
    
    # 模型配置
    model: str = ""                  # 空字符串表示使用默认模型
    temperature: float = 0.5
    max_tokens: int = 2000
    timeout: int = 60
    
    # Agent 间调用权限
    can_call: List[str] = field(default_factory=list)
    
    # 是否启用
    enabled: bool = True
    
    def __post_init__(self):
        """验证必要字段"""
        if not self.id:
            raise ValueError("Agent id is required")
        if not self.name:
            raise ValueError("Agent name is required")
        if self.tier < 1 or self.tier > 3:
            raise ValueError(f"Agent tier must be 1, 2, or 3, got {self.tier}")
    
    @classmethod
    def from_yaml(cls, data: Dict[str, Any]) -> "AgentRole":
        """从 YAML 数据创建 AgentRole"""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            tier=data.get("tier", 3),
            prompt=data.get("prompt", ""),
            capabilities=data.get("capabilities", []),
            tools_allowed=data.get("tools_allowed", []),
            model=data.get("model", ""),
            temperature=data.get("temperature", 0.5),
            max_tokens=data.get("max_tokens", 2000),
            timeout=data.get("timeout", 60),
            can_call=data.get("can_call", []),
            enabled=data.get("enabled", True),
        )


class AgentLoader:
    """Agent 角色加载器"""
    
    def __init__(self):
        self._agents: Dict[str, AgentRole] = {}
        self._loaded = False
    
    def load(self, force_reload: bool = False) -> Dict[str, AgentRole]:
        """加载所有 Agent 定义
        
        优先级：
        1. 内置定义 (multi_agent/agents/*.yaml)
        2. 用户自定义定义 (~/.hermes/agents/*.yaml) - 会覆盖内置定义
        """
        if self._loaded and not force_reload:
            return self._agents
        
        self._agents = {}
        
        # 1. 加载内置定义
        builtin_dir = Path(__file__).parent / "agents"
        if builtin_dir.exists():
            for yaml_file in builtin_dir.glob("*.yaml"):
                try:
                    agent = self._load_yaml_file(yaml_file)
                    if agent:
                        self._agents[agent.id] = agent
                except Exception as e:
                    print(f"Warning: Failed to load {yaml_file}: {e}")
        
        # 2. 加载用户自定义定义（覆盖内置）
        user_dir = get_hermes_home() / "agents"
        if user_dir.exists():
            for yaml_file in user_dir.glob("*.yaml"):
                try:
                    agent = self._load_yaml_file(yaml_file)
                    if agent:
                        self._agents[agent.id] = agent
                except Exception as e:
                    print(f"Warning: Failed to load {yaml_file}: {e}")
        
        self._loaded = True
        return self._agents
    
    def _load_yaml_file(self, path: Path) -> Optional[AgentRole]:
        """从 YAML 文件加载单个 Agent 定义"""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        if not data or not isinstance(data, dict):
            return None
        
        return AgentRole.from_yaml(data)
    
    def get(self, agent_id: str) -> Optional[AgentRole]:
        """获取指定 Agent 定义"""
        if not self._loaded:
            self.load()
        return self._agents.get(agent_id)
    
    def get_prompt(self, agent_id: str) -> str:
        """获取指定 Agent 的 prompt"""
        agent = self.get(agent_id)
        if agent:
            return agent.prompt
        return ""
    
    def list_all(self) -> List[AgentRole]:
        """列出所有 Agent"""
        if not self._loaded:
            self.load()
        return list(self._agents.values())
    
    def list_by_tier(self, tier: int) -> List[AgentRole]:
        """列出指定层级的 Agent"""
        return [a for a in self.list_all() if a.tier == tier]
    
    def list_enabled(self) -> List[AgentRole]:
        """列出所有启用的 Agent"""
        return [a for a in self.list_all() if a.enabled]


# 全局单例
_loader: Optional[AgentLoader] = None


def _get_loader() -> AgentLoader:
    """获取全局 AgentLoader 实例"""
    global _loader
    if _loader is None:
        _loader = AgentLoader()
    return _loader


def get_agent_prompt(agent_id: str) -> str:
    """获取指定 Agent 的 prompt"""
    return _get_loader().get_prompt(agent_id)


def list_available_agents() -> List[AgentRole]:
    """列出所有可用的 Agent"""
    return _get_loader().list_enabled()


def get_agent(agent_id: str) -> Optional[AgentRole]:
    """获取指定 Agent 定义"""
    return _get_loader().get(agent_id)

"""
Agent Pool - Agent 角色池管理

负责：
1. 管理 Agent 角色定义
2. 执行 Agent 任务（通过 LLM 调用）
3. 检查 Agent 间调用权限
4. 与 AIAgent 集成
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .agent_loader import AgentLoader, AgentRole
from .error_handler import ErrorHandler, RetryPolicy, CircuitBreaker, get_error_handler

logger = logging.getLogger(__name__)


@dataclass
class AgentExecutionResult:
    """Agent 执行结果"""
    success: bool
    output: str
    agent_id: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AgentPool:
    """Agent 角色池管理"""
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        parent_agent: Optional[Any] = None,
    ):
        """初始化角色池
        
        Args:
            config: 配置字典
            parent_agent: 父 Agent 实例（用于 LLM 调用）
        """
        self._config = config or {}
        self._parent_agent = parent_agent
        self._loader = AgentLoader()
        self._agents: Dict[str, AgentRole] = {}
        
        # 加载所有 Agent
        self._load_agents()
    
    def _load_agents(self):
        """加载所有 Agent 定义"""
        self._agents = self._loader.load()
    
    def reload(self):
        """重新加载 Agent 定义"""
        self._loader.load(force_reload=True)
        self._agents = self._loader._agents
    
    def get_agent(self, agent_id: str) -> Optional[AgentRole]:
        """获取 Agent 定义"""
        return self._agents.get(agent_id)
    
    def get_prompt(self, agent_id: str) -> str:
        """获取 Agent 的 prompt"""
        agent = self.get_agent(agent_id)
        if agent:
            return agent.prompt
        return ""
    
    def list_agents(self, enabled_only: bool = True) -> List[AgentRole]:
        """列出所有 Agent
        
        Args:
            enabled_only: 是否只返回启用的 Agent
        
        Returns:
            Agent 列表
        """
        agents = list(self._agents.values())
        if enabled_only:
            agents = [a for a in agents if a.enabled]
        return agents
    
    def list_by_tier(self, tier: int, enabled_only: bool = True) -> List[AgentRole]:
        """列出指定层级的 Agent"""
        agents = [a for a in self._agents.values() if a.tier == tier]
        if enabled_only:
            agents = [a for a in agents if a.enabled]
        return agents
    
    def can_call(self, from_agent: str, to_agent: str) -> bool:
        """检查 Agent 间调用权限
        
        Args:
            from_agent: 调用方 Agent ID
            to_agent: 被调用方 Agent ID
        
        Returns:
            是否有权限调用
        """
        agent = self.get_agent(from_agent)
        if not agent:
            return False
        
        return to_agent in agent.can_call
    
    def get_agent_config(self, agent_id: str) -> Dict[str, Any]:
        """获取 Agent 的运行时配置
        
        合并默认配置和用户配置
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return {}
        
        # 从配置中获取用户覆盖
        multi_agent_config = self._config.get("multi_agent", {})
        agents_config = multi_agent_config.get("agents", {})
        user_config = agents_config.get(agent_id, {})
        
        return {
            "model": user_config.get("model") or agent.model,
            "temperature": agent.temperature,
            "max_tokens": agent.max_tokens,
            "timeout": agent.timeout,
            "enabled": user_config.get("enabled", agent.enabled),
        }
    
    def set_parent_agent(self, parent_agent: Any):
        """设置父 Agent"""
        self._parent_agent = parent_agent
    
    def execute(
        self,
        agent_id: str,
        task_id: str,
        input_data: str,
        context: Optional[Dict[str, Any]] = None,
        workspace_path: Optional[str] = None,
    ) -> Any:
        """执行 Agent 任务
        
        这是核心方法，负责调用 Agent 执行具体任务。
        
        Args:
            agent_id: Agent ID
            task_id: 任务 ID
            input_data: 输入数据
            context: 执行上下文
            workspace_path: 工作空间路径（用于保存输出）
        
        Returns:
            执行结果
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return AgentExecutionResult(
                success=False,
                output="",
                agent_id=agent_id,
                error=f"Agent '{agent_id}' not found",
            )
        
        if not agent.enabled:
            return AgentExecutionResult(
                success=False,
                output="",
                agent_id=agent_id,
                error=f"Agent '{agent_id}' is disabled",
            )
        
        # 获取配置
        config = self.get_agent_config(agent_id)
        
        # 构建调用上下文
        execution_context = {
            "agent_id": agent_id,
            "agent_name": agent.name,
            "task_id": task_id,
            "input": input_data,
            "context": context or {},
            "config": config,
            "prompt": agent.prompt,
            "tools_allowed": agent.tools_allowed,
            "workspace_path": workspace_path,
        }
        
        # 调用实际执行
        return self._execute_agent(execution_context)
    
    def _execute_agent(self, context: Dict[str, Any]) -> Any:
        """实际执行 Agent（内部方法）
        
        Phase 2 实现：通过 AIAgent 调用真实 LLM。
        """
        agent_id = context.get("agent_id", "unknown")
        agent_name = context.get("agent_name", "Unknown")
        input_data = context.get("input", "")
        agent_prompt = context.get("prompt", "")
        tools_allowed = context.get("tools_allowed", [])
        config = context.get("config", {})
        execution_context = context.get("context", {})  # 获取执行上下文
        
        # 检查是否有父 Agent
        if self._parent_agent is None:
            logger.warning("No parent_agent set, returning simulated result")
            return self._simulate_result(agent_id, agent_name, input_data)
        
        # 使用 AIAgent 执行真实 LLM 调用
        return self._execute_with_llm(
            agent_id=agent_id,
            agent_name=agent_name,
            agent_prompt=agent_prompt,
            input_data=input_data,
            tools_allowed=tools_allowed,
            config=config,
            execution_context=execution_context,
        )
    
    def _execute_with_llm(
        self,
        agent_id: str,
        agent_name: str,
        agent_prompt: str,
        input_data: str,
        tools_allowed: List[str],
        config: Dict[str, Any],
        execution_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """使用 LLM 执行 Agent 任务（带错误处理）"""
        import time
        from run_agent import AIAgent
        
        parent = self._parent_agent
        
        # 获取任务ID用于审计日志
        task_id = execution_context.get("task_id", "unknown") if execution_context else "unknown"
        
        # 获取错误处理器
        error_handler = get_error_handler(agent_id, self._config)
        
        # 构建 Agent 的系统提示
        system_prompt = self._build_agent_system_prompt(
            agent_id=agent_id,
            agent_name=agent_name,
            agent_prompt=agent_prompt,
        )
        
        # 构建用户消息
        user_message = self._build_user_message(agent_id, input_data, execution_context)
        
        # 解析工具集
        toolsets = self._resolve_toolsets(tools_allowed, parent)
        
        # 解析模型配置
        model = config.get("model") or ""
        if not model and hasattr(parent, "model"):
            model = parent.model
        
        # 获取当前Agent可调用的其他Agent
        can_call_agents = self._get_callable_agents(agent_id)
        
        # 记录开始时间
        start_time = time.time()
        
        # 定义 LLM 调用函数
        def _call_llm() -> str:
            """执行实际的 LLM 调用"""
            child = AIAgent(
                base_url=getattr(parent, "base_url", ""),
                api_key=self._get_parent_api_key(parent),
                model=model,
                provider=getattr(parent, "provider", None),
                api_mode=getattr(parent, "api_mode", None),
                max_iterations=config.get("max_iterations", 20),
                max_tokens=config.get("max_tokens"),
                enabled_toolsets=toolsets if toolsets else None,
                quiet_mode=True,
                ephemeral_system_prompt=system_prompt,
                platform=getattr(parent, "platform", None),
                skip_context_files=True,
                skip_memory=True,
                skip_multi_agent=True,  # 防止递归
                clarify_callback=None,
                session_db=getattr(parent, '_session_db', None),
                parent_session_id=getattr(parent, 'session_id', None),
            )
            
            # 注入Agent间调用能力
            if can_call_agents:
                child._multi_agent_pool = self
                child._multi_agent_from = agent_id
            
            # 执行并返回结果
            return child.chat(user_message)
        
        # 使用错误处理器执行
        result, error = error_handler.execute(_call_llm)
        
        # 计算延迟
        latency_ms = int((time.time() - start_time) * 1000)
        
        if error is None:
            # 成功
            # 获取token使用量（如果可用）
            tokens_used = 0
            # 注意：在错误处理器的重试过程中，child 变量已经不可访问
            # 所以这里无法获取 tokens_used，需要从最后一次调用中获取
            # 暂时设为 0，后续可以优化
            
            # 记录审计日志
            self._record_audit_log(
                task_id=task_id,
                agent_id=agent_id,
                agent_name=agent_name,
                action=execution_context.get("action", "execute") if execution_context else "execute",
                input_summary=input_data,
                output_summary=result,
                status="success",
                tokens_used=tokens_used,
                latency_ms=latency_ms,
                model_version=model,
            )
            
            logger.info(f"[{agent_name}] LLM call completed, result length: {len(result)}, latency: {latency_ms}ms")
            return result
        else:
            # 失败
            error_msg = str(error)
            result = json.dumps({
                "error": error_msg,
                "agent": agent_name,
            })
            
            # 记录失败的审计日志
            self._record_audit_log(
                task_id=task_id,
                agent_id=agent_id,
                agent_name=agent_name,
                action=execution_context.get("action", "execute") if execution_context else "execute",
                input_summary=input_data,
                output_summary="",
                status="failed",
                error_message=error_msg,
                latency_ms=latency_ms,
                model_version=model,
            )
            
            logger.error(f"[{agent_name}] LLM call failed after retries: {error}")
            return result
    
    def _record_audit_log(
        self,
        task_id: str,
        agent_id: str,
        agent_name: str,
        action: str,
        input_summary: str,
        output_summary: str,
        status: str = "success",
        error_message: str = "",
        tokens_used: int = 0,
        latency_ms: int = 0,
        model_version: str = "",
    ):
        """记录审计日志
        
        Args:
            task_id: 任务ID
            agent_id: Agent ID
            agent_name: Agent 名称
            action: 操作类型
            input_summary: 输入摘要
            output_summary: 输出摘要
            status: 状态
            error_message: 错误信息
            tokens_used: token使用量
            latency_ms: 延迟毫秒
            model_version: 模型版本
        """
        try:
            from .state_manager import MultiAgentStateManager
            state_manager = MultiAgentStateManager()
            state_manager.add_audit_log(
                task_id=task_id,
                agent_id=agent_id,
                agent_name=agent_name,
                action=action,
                input_summary=input_summary,
                output_summary=output_summary,
                status=status,
                error_message=error_message,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
                model_version=model_version,
            )
        except Exception as e:
            logger.warning(f"记录审计日志失败: {e}")
    
    def _get_callable_agents(self, agent_id: str) -> List[str]:
        """获取当前Agent可调用的其他Agent列表"""
        agent = self.get_agent(agent_id)
        if agent and agent.can_call:
            return agent.can_call
        return []
    
    def dispatch_to_agent(
        self,
        from_agent: str,
        to_agent: str,
        task: str,
        task_id: str = None,
        context: Optional[Dict[str, Any]] = None,
        workspace_path: Optional[str] = None,
    ) -> str:
        """Agent间调用 - 一个Agent调用另一个Agent执行任务
        
        Args:
            from_agent: 调用方Agent ID
            to_agent: 被调用方Agent ID
            task: 任务描述
            task_id: 任务ID（可选）
            context: 上下文信息
            workspace_path: 工作空间路径（用于保存输出）
        
        Returns:
            执行结果字符串
        """
        import uuid
        
        # 1. 检查调用权限
        if not self.can_call(from_agent, to_agent):
            logger.warning(f"[{from_agent}] 无权调用 [{to_agent}]")
            return json.dumps({
                "error": f"权限不足: {from_agent} 无权调用 {to_agent}",
                "success": False,
            })
        
        # 2. 生成子任务ID
        subtask_id = task_id or f"subtask-{uuid.uuid4().hex[:8]}"
        
        logger.info(f"[{from_agent}] -> [{to_agent}] 派发任务: {task[:50]}...")
        
        # 3. 执行目标Agent
        result = self.execute(
            agent_id=to_agent,
            task_id=subtask_id,
            input_data=task,
            context=context,
            workspace_path=workspace_path,
        )
        
        return result
    
    def dispatch_parallel(
        self,
        from_agent: str,
        dispatches: List[Dict[str, str]],
        task_id: str = None,
    ) -> List[Dict[str, Any]]:
        """并行派发任务给多个Agent
        
        Args:
            from_agent: 调用方Agent ID
            dispatches: 派发列表，每项包含 {"agent": "gongbu", "task": "..."}
            task_id: 基础任务ID
        
        Returns:
            结果列表
        """
        import concurrent.futures
        
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            for i, dispatch in enumerate(dispatches):
                to_agent = dispatch.get("agent")
                task = dispatch.get("task", "")
                subtask_id = f"{task_id}-{to_agent}-{i}" if task_id else None
                
                if self.can_call(from_agent, to_agent):
                    future = executor.submit(
                        self.dispatch_to_agent,
                        from_agent,
                        to_agent,
                        task,
                        subtask_id,
                    )
                    futures[future] = to_agent
                else:
                    results.append({
                        "agent": to_agent,
                        "error": f"无权调用 {to_agent}",
                        "success": False,
                    })
            
            for future in concurrent.futures.as_completed(futures):
                to_agent = futures[future]
                try:
                    result = future.result(timeout=300)
                    results.append({
                        "agent": to_agent,
                        "result": result,
                        "success": True,
                    })
                except Exception as e:
                    results.append({
                        "agent": to_agent,
                        "error": str(e),
                        "success": False,
                    })
        
        return results
    
    def _build_agent_system_prompt(
        self,
        agent_id: str,
        agent_name: str,
        agent_prompt: str,
    ) -> str:
        """构建 Agent 的系统提示"""
        # Agent 的 prompt 已经是完整的角色定义
        # 添加输出格式提示
        output_hint = self._get_output_format_hint(agent_id)
        
        return f"""{agent_prompt}

{output_hint}"""
    
    def _get_output_format_hint(self, agent_id: str) -> str:
        """获取输出格式提示"""
        hints = {
            "taizi": "请严格按照 JSON 格式输出分类结果。",
            "zhongshu": "请输出结构化的规划结果，包含 analysis、plan、resources、risks 等字段。",
            "menxia": "请输出审议结果，包含 decision（approved/rejected）、scores、comments 等字段。",
            "shangshu": "请输出执行派发结果，包含 status、summary、results 等字段。",
        }
        return hints.get(agent_id, "请输出 JSON 格式的结果。")
    
    def _build_user_message(self, agent_id: str, input_data: str, context: Optional[Dict[str, Any]] = None) -> str:
        """构建用户消息"""
        action = context.get("action", "") if context else ""
        
        if agent_id == "taizi":
            # 根据 action 决定消息格式
            if action == "summarize":
                # 汇总任务：直接返回汇总提示，不再包装
                return input_data
            else:
                # 分类任务：包装为分类格式
                return f"""请对以下用户消息进行分类：

{input_data}

请判断这是「闲聊」还是「旨意」，并按指定格式输出。"""
        
        elif agent_id == "zhongshu":
            return f"""请对以下任务进行规划：

{input_data}

请输出详细的任务规划和执行方案。"""
        
        elif agent_id == "menxia":
            return f"""请审议以下方案：

{input_data}

请评估方案的可行性、完整性和风险，并做出决定。"""
        
        elif agent_id == "shangshu":
            return f"""请执行派发以下任务：

{input_data}

请将任务分配给合适的部门并执行。"""
        
        else:
            return f"""请处理以下任务：

{input_data}"""
    
    def _resolve_toolsets(
        self,
        tools_allowed: List[str],
        parent_agent: Any,
    ) -> List[str]:
        """解析工具集
        
        将 Agent 允许的工具列表转换为 delegate_task 的 toolsets 参数。
        """
        if not tools_allowed:
            # 如果没有指定，使用父 Agent 的工具集
            return None
        
        # 映射工具名到工具集
        tool_to_toolset = {
            "web_search": "web",
            "web_extract": "web",
            "terminal": "terminal",
            "file": "file",
            "read_file": "file",
            "write_file": "file",
            "browser": "browser",
        }
        
        toolsets = set()
        for tool in tools_allowed:
            ts = tool_to_toolset.get(tool, tool)
            toolsets.add(ts)
        
        return list(toolsets) if toolsets else None
    
    def _get_parent_api_key(self, parent_agent: Any) -> Optional[str]:
        """获取父 Agent 的 API Key"""
        api_key = getattr(parent_agent, "api_key", None)
        if not api_key and hasattr(parent_agent, "_client_kwargs"):
            api_key = parent_agent._client_kwargs.get("api_key")
        return api_key
    
    def _simulate_result(self, agent_id: str, agent_name: str, input_data: str) -> str:
        """模拟执行结果（用于无父 Agent 时的测试）"""
        if agent_id == "taizi":
            if any(kw in input_data.lower() for kw in ["你好", "hello", "嗨", "hi"]):
                return json.dumps({
                    "type": "chat",
                    "response": f"您好！我是{agent_name}，很高兴为您服务～"
                })
            else:
                return json.dumps({
                    "type": "decree",
                    "title": input_data[:50] if len(input_data) > 50 else input_data,
                    "description": input_data,
                    "category": "其他",
                    "urgency": "中",
                    "complexity": "中等",
                    "suggested_agents": ["工部"]
                })
        
        elif agent_id == "zhongshu":
            return json.dumps({
                "analysis": {"background": input_data[:100]},
                "plan": {"phases": [{"name": "执行阶段", "tasks": [input_data[:50]]}]},
                "resources": {},
                "risks": []
            })
        
        elif agent_id == "menxia":
            return json.dumps({
                "decision": "approved",
                "scores": {"feasibility": 8, "completeness": 7},
                "comments": "方案可行"
            })
        
        elif agent_id == "shangshu":
            return json.dumps({
                "status": "success",
                "summary": "任务已派发执行"
            })
        
        else:
            return json.dumps({
                "status": "completed",
                "output": f"{agent_name} 已完成任务"
            })


def get_agent_pool(
    config: Optional[Dict[str, Any]] = None,
    parent_agent: Optional[Any] = None,
) -> AgentPool:
    """获取 AgentPool 实例"""
    return AgentPool(config, parent_agent)

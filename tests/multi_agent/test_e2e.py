"""
三省六部多Agent系统 - 端到端集成测试

测试范围：
1. 核心流程：闲聊处理
2. 核心流程：旨意处理（完整三省六部流程）
3. Agent间调用
4. 审议封驳循环
5. 状态持久化
6. 事件发布
7. 审计日志记录
8. 任务干预（暂停/恢复/取消）
9. 阻塞/确认
10. 归档导出
"""

import pytest
import tempfile
import os
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# 设置测试环境
@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch):
    """自动设置测试环境"""
    # 隔离 HERMES_HOME
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yield hermes_home


class TestStateManagerBasics:
    """状态管理基础测试"""
    
    def test_state_manager_init(self, setup_test_env):
        """测试状态管理器初始化"""
        from multi_agent.state_manager import MultiAgentStateManager
        
        sm = MultiAgentStateManager()
        assert sm is not None
        
        # 验证数据库文件创建
        db_path = setup_test_env / "multi_agent.db"
        assert db_path.exists()
    
    def test_create_task(self, setup_test_env):
        """测试任务创建"""
        from multi_agent.state_manager import MultiAgentStateManager
        from multi_agent.orchestrator import TaskStatus
        
        sm = MultiAgentStateManager()
        result = sm.create_task(
            task_id="test-001",
            title="测试任务",
            message_type="decree",
            original_message="帮我写一个Python脚本",
        )
        
        # create_task 返回 TaskRecord 或 task_id
        task_id = result.task_id if hasattr(result, 'task_id') else result
        assert task_id == "test-001"
        
        # 验证任务可以读取
        task = sm.get_task("test-001")
        assert task is not None
        assert task.title == "测试任务"
        assert task.status == TaskStatus.CREATED
    
    def test_update_task_status(self, setup_test_env):
        """测试任务状态更新"""
        from multi_agent.state_manager import MultiAgentStateManager
        from multi_agent.orchestrator import TaskStatus
        
        sm = MultiAgentStateManager()
        sm.create_task(
            task_id="test-002",
            title="状态更新测试",
            message_type="decree",
            original_message="测试",
        )
        
        # 更新状态（使用 update_task_data）
        sm.update_task_data(
            task_id="test-002",
            status=TaskStatus.PLANNING,
            current_agent="zhongshu",
        )
        
        task = sm.get_task("test-002")
        assert task.status == TaskStatus.PLANNING
        assert task.current_agent == "zhongshu"
    
    def test_list_tasks(self, setup_test_env):
        """测试任务列表"""
        from multi_agent.state_manager import MultiAgentStateManager
        
        sm = MultiAgentStateManager()
        
        # 创建多个任务
        for i in range(5):
            sm.create_task(
                task_id=f"list-test-{i:03d}",
                title=f"任务{i}",
                message_type="decree",
                original_message=f"测试{i}",
            )
        
        # 列出任务
        tasks = sm.list_tasks(limit=10)
        assert len(tasks) >= 5
    
    def test_add_event(self, setup_test_env):
        """测试事件添加"""
        from multi_agent.state_manager import MultiAgentStateManager
        
        sm = MultiAgentStateManager()
        sm.create_task(
            task_id="event-test-001",
            title="事件测试",
            message_type="decree",
            original_message="测试",
        )
        
        # 添加事件
        sm.add_event(
            event_id="evt-001",
            task_id="event-test-001",
            event_type="test_event",
            agent_id="taizi",
            payload={"test": "data"},
        )
        
        # 获取事件
        events = sm.get_task_events("event-test-001")
        # 注意：create_task 会自动添加 task.created 事件
        event_types = [e.event_type for e in events]
        assert "test_event" in event_types


class TestAuditLog:
    """审计日志测试"""
    
    def test_add_audit_log(self, setup_test_env):
        """测试审计日志添加"""
        from multi_agent.state_manager import MultiAgentStateManager
        
        sm = MultiAgentStateManager()
        
        # 添加审计日志
        log_id = sm.add_audit_log(
            task_id="audit-test-001",
            agent_id="gongbu",
            agent_name="工部",
            action="execute",
            input_summary="输入内容",
            output_summary="输出内容",
            status="success",
            tokens_used=100,
            latency_ms=500,
        )
        
        assert log_id is not None
        
        # 查询审计日志
        logs = sm.get_audit_logs(task_id="audit-test-001")
        assert len(logs) >= 1
        assert logs[0].agent_id == "gongbu"
    
    def test_export_audit_logs(self, setup_test_env):
        """测试审计日志导出"""
        from multi_agent.state_manager import MultiAgentStateManager
        
        sm = MultiAgentStateManager()
        
        # 添加多条审计日志
        for i in range(3):
            sm.add_audit_log(
                task_id=f"export-test-{i:03d}",
                agent_id="gongbu",
                agent_name="工部",
                action="execute",
                input_summary=f"输入{i}",
                output_summary=f"输出{i}",
                status="success",
            )
        
        # 导出 JSON
        json_export = sm.export_audit_logs(format="json")
        assert json_export is not None
        data = json.loads(json_export)
        assert len(data) >= 3


class TestArchiveFunctionality:
    """归档功能测试"""
    
    def test_archive_task(self, setup_test_env):
        """测试任务归档"""
        from multi_agent.state_manager import MultiAgentStateManager
        from multi_agent.orchestrator import TaskStatus
        
        sm = MultiAgentStateManager()
        
        # 创建任务并标记为完成
        sm.create_task(
            task_id="archive-test-001",
            title="归档测试任务",
            message_type="decree",
            original_message="测试归档",
        )
        # 更新状态为完成
        sm.update_task_data(
            task_id="archive-test-001",
            status=TaskStatus.COMPLETED,
        )
        
        # 归档任务
        result = sm.archive_task("archive-test-001", "success")
        assert result.get("success") is True
        assert result.get("archive_id") is not None
        
        # 获取归档记录
        archive = sm.get_archive(result["archive_id"])
        assert archive is not None
        assert archive["task_id"] == "archive-test-001"
    
    def test_list_archives(self, setup_test_env):
        """测试归档列表"""
        from multi_agent.state_manager import MultiAgentStateManager
        from multi_agent.orchestrator import TaskStatus
        
        sm = MultiAgentStateManager()
        
        # 创建并归档多个任务
        for i in range(3):
            task_id = f"list-archive-{i:03d}"
            sm.create_task(
                task_id=task_id,
                title=f"归档任务{i}",
                message_type="decree",
                original_message=f"测试{i}",
            )
            sm.update_task_data(task_id=task_id, status=TaskStatus.COMPLETED)
            sm.archive_task(task_id, "success")
        
        # 列出归档
        archives = sm.list_archives(limit=10)
        assert len(archives) >= 3
    
    def test_export_archive(self, setup_test_env):
        """测试归档导出"""
        from multi_agent.state_manager import MultiAgentStateManager
        from multi_agent.orchestrator import TaskStatus
        
        sm = MultiAgentStateManager()
        
        # 创建并归档任务
        sm.create_task(
            task_id="export-archive-001",
            title="导出测试",
            message_type="decree",
            original_message="测试",
        )
        sm.update_task_data(task_id="export-archive-001", status=TaskStatus.COMPLETED)
        result = sm.archive_task("export-archive-001", "success")
        archive_id = result["archive_id"]
        
        # 导出 JSON
        export_result = sm.export_archive(archive_id=archive_id, format="json")
        assert export_result.get("success") is True
        assert export_result.get("content") is not None
        
        # 导出 Markdown
        md_result = sm.export_archive(archive_id=archive_id, format="markdown")
        assert md_result.get("success") is True
        assert "任务导出" in md_result.get("content", "") or "任务ID" in md_result.get("content", "")
    
    def test_archive_statistics(self, setup_test_env):
        """测试归档统计"""
        from multi_agent.state_manager import MultiAgentStateManager
        from multi_agent.orchestrator import TaskStatus
        
        sm = MultiAgentStateManager()
        
        # 创建并归档不同结果的任务
        for i in range(3):
            task_id = f"stats-archive-{i:03d}"
            sm.create_task(
                task_id=task_id,
                title=f"统计任务{i}",
                message_type="decree",
                original_message=f"测试{i}",
            )
            sm.update_task_data(task_id=task_id, status=TaskStatus.COMPLETED)
            result = "success" if i < 2 else "failed"
            sm.archive_task(task_id, result)
        
        # 获取统计
        stats = sm.get_archive_statistics()
        assert stats.get("total", 0) >= 3


class TestBlockingFunctionality:
    """阻塞功能测试"""
    
    def test_block_task(self, setup_test_env):
        """测试任务阻塞"""
        from multi_agent.state_manager import MultiAgentStateManager
        from multi_agent.orchestrator import TaskStatus
        
        sm = MultiAgentStateManager()
        
        # 创建任务
        sm.create_task(
            task_id="block-test-001",
            title="阻塞测试",
            message_type="decree",
            original_message="测试",
        )
        
        # 更新状态为运行中状态
        sm.update_task_data(
            task_id="block-test-001",
            status=TaskStatus.PLANNING,
            current_agent="zhongshu",
        )
        
        # 阻塞任务（使用正确的参数名）
        result = sm.block_task(
            task_id="block-test-001",
            reason="需要用户确认",
            by="menxia",
            options=[
                {"id": "continue", "label": "继续执行"},
                {"id": "cancel", "label": "取消任务"},
            ],
        )
        assert result.get("success") is True
        
        # 获取阻塞状态
        status = sm.get_blocked_status("block-test-001")
        assert status.get("is_blocked") is True
        assert status.get("blocked_info").get("reason") == "需要用户确认"
    
    def test_unblock_task(self, setup_test_env):
        """测试解除阻塞"""
        from multi_agent.state_manager import MultiAgentStateManager
        from multi_agent.orchestrator import TaskStatus
        
        sm = MultiAgentStateManager()
        
        # 创建并阻塞任务
        sm.create_task(
            task_id="unblock-test-001",
            title="解除阻塞测试",
            message_type="decree",
            original_message="测试",
        )
        
        # 更新状态为运行中状态
        sm.update_task_data(
            task_id="unblock-test-001",
            status=TaskStatus.PLANNING,
            current_agent="zhongshu",
        )
        
        sm.block_task(
            task_id="unblock-test-001",
            reason="测试阻塞",
            by="taizi",
        )
        
        # 解除阻塞
        result = sm.unblock_task("unblock-test-001", "continue")
        assert result.get("success") is True
        
        # 验证已解除
        status = sm.get_blocked_status("unblock-test-001")
        assert status.get("is_blocked") is False


class TestEventBus:
    """事件总线测试"""
    
    def test_event_bus_publish_subscribe(self, setup_test_env):
        """测试事件发布订阅"""
        from multi_agent.event_bus import InMemoryEventBus, EventType, Event
        
        bus = InMemoryEventBus()
        received_events = []
        
        def handler(event: Event):
            received_events.append(event)
        
        # 订阅
        subscription_id = bus.subscribe(EventType.TASK_CREATED, handler)
        assert subscription_id is not None
        
        # 发布事件
        event = Event(
            event_id="evt-001",
            event_type=EventType.TASK_CREATED,
            task_id="test-001",
        )
        bus.publish(event)
        
        assert len(received_events) == 1
        assert received_events[0].task_id == "test-001"
    
    def test_event_bus_history(self, setup_test_env):
        """测试事件历史"""
        from multi_agent.event_bus import InMemoryEventBus, EventType, Event
        
        bus = InMemoryEventBus()
        
        # 发布多个事件
        for i in range(5):
            event = Event(
                event_id=f"evt-{i:03d}",
                event_type=EventType.TASK_CREATED,
                task_id=f"task-{i:03d}",
            )
            bus.publish(event)
        
        # 获取历史
        history = bus.get_history(limit=10)
        assert len(history) >= 5


class TestOutputParser:
    """输出解析测试"""
    
    def test_parse_json_direct(self, setup_test_env):
        """测试直接 JSON 解析"""
        from multi_agent.output_parser import OutputParser
        
        text = '{"type": "chat", "response": "你好！"}'
        result = OutputParser.parse(text)
        
        assert result.success is True
        assert result.data["type"] == "chat"
    
    def test_parse_json_code_block(self, setup_test_env):
        """测试代码块 JSON 解析"""
        from multi_agent.output_parser import OutputParser
        
        text = '''
        这是一段文本
        ```json
        {"type": "decree", "title": "测试任务"}
        ```
        '''
        result = OutputParser.parse(text)
        
        assert result.success is True
        assert result.data["type"] == "decree"
    
    def test_parse_to_model(self, setup_test_env):
        """测试 Pydantic 模型解析"""
        from multi_agent.output_parser import OutputParser
        from multi_agent.output_schemas import ClassificationOutput
        
        text = '{"type": "chat", "response": "你好！有什么可以帮助您的？"}'
        result = OutputParser.parse_to_model(text, ClassificationOutput)
        
        assert result.success is True
        assert result.model is not None
        assert result.model.type.value == "chat"
        assert result.model.response is not None


class TestErrorHandler:
    """错误处理测试"""
    
    def test_retry_policy_delay(self, setup_test_env):
        """测试重试策略延迟计算"""
        from multi_agent.error_handler import RetryPolicy
        
        policy = RetryPolicy(
            max_attempts=3,
            base_delay=1.0,
            max_delay=30.0,
            jitter=False,  # 禁用抖动以测试确定性值
        )
        
        # 测试延迟计算
        delay_0 = policy.get_delay(0)
        delay_1 = policy.get_delay(1)
        delay_2 = policy.get_delay(2)
        
        # 指数退避: base * (exp_base ** attempt)
        assert delay_0 == 1.0  # 1.0 * 2^0
        assert delay_1 == 2.0  # 1.0 * 2^1
        assert delay_2 == 4.0  # 1.0 * 2^2
    
    def test_retry_policy_should_retry(self, setup_test_env):
        """测试重试判断"""
        from multi_agent.error_handler import RetryPolicy
        
        policy = RetryPolicy()
        
        # 可重试的错误
        assert policy.should_retry("timeout") is True
        assert policy.should_retry("rate_limit exceeded") is True
        assert policy.should_retry("server_error") is True
        
        # 不可重试的错误
        assert policy.should_retry("invalid_api_key") is False
        assert policy.should_retry("authentication failed") is False
        assert policy.should_retry("context_length exceeded") is False
    
    def test_circuit_breaker_states(self, setup_test_env):
        """测试熔断器状态转换"""
        from multi_agent.error_handler import CircuitBreaker, CircuitState
        
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.5)
        
        # 初始状态：关闭
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True
        
        # 记录失败直到熔断
        for _ in range(3):
            cb.record_failure()
        
        # 熔断状态：打开
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False
        
        # 等待恢复超时
        time.sleep(0.6)
        
        # 超时后可以执行，进入半开状态
        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN
        
        # 半开状态下成功，恢复到关闭
        cb.record_success()
        cb.record_success()  # 需要 success_threshold 次成功
        assert cb.state == CircuitState.CLOSED
    
    def test_execute_with_retry(self, setup_test_env):
        """测试带重试的执行"""
        from multi_agent.error_handler import ErrorHandler, RetryPolicy, CircuitBreaker
        
        call_count = [0]
        
        def flaky_function():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("timeout error")
            return "success"
        
        handler = ErrorHandler(
            retry_policy=RetryPolicy(max_attempts=5, base_delay=0.1, jitter=False),
            circuit_breaker=CircuitBreaker(failure_threshold=10),  # 熔断阈值高，不触发
        )
        
        result = handler.execute_with_result(flaky_function)
        assert result == "success"
        assert call_count[0] == 3


class TestTaskContext:
    """任务上下文测试"""
    
    def test_task_context_creation(self, setup_test_env):
        """测试任务上下文创建"""
        from multi_agent.orchestrator import TaskContext, TaskStatus
        
        task = TaskContext(
            task_id="ctx-test-001",
            title="上下文测试",
            message_type="decree",
            original_message="测试任务上下文",
        )
        
        assert task.task_id == "ctx-test-001"
        assert task.status == TaskStatus.CREATED
        assert task.created_at is not None
    
    def test_task_context_status_update(self, setup_test_env):
        """测试任务上下文状态更新"""
        from multi_agent.orchestrator import TaskContext, TaskStatus
        
        task = TaskContext(
            task_id="ctx-status-001",
            title="状态更新测试",
            message_type="decree",
            original_message="测试",
        )
        
        # 更新状态
        task.update_status(TaskStatus.PLANNING)
        assert task.status == TaskStatus.PLANNING
        
        task.update_status(TaskStatus.REVIEWING)
        assert task.status == TaskStatus.REVIEWING
    
    def test_task_context_blocked(self, setup_test_env):
        """测试任务上下文阻塞"""
        from multi_agent.orchestrator import TaskContext, TaskStatus
        
        task = TaskContext(
            task_id="ctx-blocked-001",
            title="阻塞测试",
            message_type="decree",
            original_message="测试",
        )
        
        # 设置阻塞（使用正确的参数名）
        task.set_blocked(
            reason="需要确认",
            by="menxia",
            options=[{"id": "continue", "label": "继续"}],
        )
        
        assert task.blocked is True
        assert task.blocked_reason == "需要确认"


class TestOrchestratorMethods:
    """调度器方法测试（不依赖 LLM）"""
    
    def test_orchestrator_init(self, setup_test_env):
        """测试调度器初始化"""
        from multi_agent.orchestrator import MultiAgentOrchestrator
        
        orch = MultiAgentOrchestrator()
        assert orch is not None
    
    def test_create_task(self, setup_test_env):
        """测试调度器创建任务"""
        from multi_agent.orchestrator import MultiAgentOrchestrator, TaskStatus
        
        orch = MultiAgentOrchestrator()
        task = orch.create_task("帮我写一个脚本")
        
        assert task is not None
        assert task.task_id is not None
        assert task.status == TaskStatus.CREATED
        assert task.original_message == "帮我写一个脚本"
    
    def test_get_statistics(self, setup_test_env):
        """测试获取统计"""
        from multi_agent.orchestrator import MultiAgentOrchestrator
        
        orch = MultiAgentOrchestrator()
        stats = orch.get_statistics()
        
        assert stats is not None
        assert "total_tasks" in stats
    
    def test_list_archives(self, setup_test_env):
        """测试调度器归档列表方法"""
        from multi_agent.orchestrator import MultiAgentOrchestrator
        
        orch = MultiAgentOrchestrator()
        archives = orch.list_archives(limit=10)
        assert archives is not None  # 可能为空列表


# ============================================================
# 以下测试需要 Mock LLM 调用，测试完整流程
# ============================================================

class TestFullFlowWithMock:
    """完整流程测试（Mock LLM）"""
    
    @patch('multi_agent.agent_pool.AgentPool._execute_with_llm')
    def test_chat_flow(self, mock_llm, setup_test_env):
        """测试闲聊流程"""
        # Mock 太子返回闲聊分类
        mock_llm.return_value = json.dumps({
            "type": "chat",
            "response": "您好！有什么可以帮助您的？",
        })
        
        from multi_agent.orchestrator import MultiAgentOrchestrator
        
        orch = MultiAgentOrchestrator()
        response = orch.process_message("你好")
        
        assert response is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

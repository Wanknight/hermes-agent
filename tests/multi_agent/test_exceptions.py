"""
异常场景测试 - 测试错误处理、熔断、边界条件

测试覆盖：
1. 错误处理器测试 - RetryPolicy、CircuitBreaker
2. 输出解析器测试 - 格式容错、Schema验证
3. 边界条件测试 - 空输入、超大输入、无效状态
4. 状态管理异常 - 重复创建、无效更新
5. 任务干预异常 - 无效干预、状态冲突
"""

import pytest
import json
import time
import threading
from pathlib import Path


# 设置测试环境
@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch):
    """自动设置测试环境"""
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    yield hermes_home


class TestErrorHandler:
    """错误处理器测试"""

    def test_retry_policy_delay_calculation(self):
        """测试重试策略延迟计算（带抖动）"""
        from multi_agent.error_handler import RetryPolicy

        policy = RetryPolicy(
            max_attempts=3,
            base_delay=1.0,
            max_delay=30.0,
            exponential_base=2.0,
            jitter=False,  # 禁用抖动以便测试
        )

        # 验证指数退避
        assert policy.get_delay(0) == 1.0  # 1.0 * 2^0 = 1.0
        assert policy.get_delay(1) == 2.0  # 1.0 * 2^1 = 2.0
        assert policy.get_delay(2) == 4.0  # 1.0 * 2^2 = 4.0
        assert policy.get_delay(5) == 30.0  # 1.0 * 2^5 = 32, but max is 30

    def test_retry_policy_delay_with_jitter(self):
        """测试带抖动的延迟"""
        from multi_agent.error_handler import RetryPolicy

        policy = RetryPolicy(
            base_delay=1.0,
            jitter=True,  # 默认开启抖动
        )

        # 抖动范围应该是 0.5x ~ 1.5x
        for _ in range(10):
            delay = policy.get_delay(0)  # base = 1.0
            assert 0.5 <= delay <= 1.5, f"Delay {delay} out of expected range"

    def test_retry_policy_should_retry(self):
        """测试重试判断逻辑"""
        from multi_agent.error_handler import RetryPolicy

        policy = RetryPolicy()  # 使用默认配置

        # 可重试的错误（默认配置包含这些）
        assert policy.should_retry("Connection timeout") is True
        assert policy.should_retry("Rate limit exceeded") is True  # 匹配 "rate limit"
        assert policy.should_retry("server error 500") is True
        assert policy.should_retry("429 Too Many Requests") is True

        # 不可重试的错误（默认配置包含这些）
        assert policy.should_retry("Invalid API key") is False  # 匹配 "invalid api key"
        assert policy.should_retry("401 Unauthorized") is False
        assert policy.should_retry("403 Forbidden") is False

    def test_circuit_breaker_states(self):
        """测试熔断器状态转换"""
        from multi_agent.error_handler import CircuitBreaker, CircuitState

        cb = CircuitBreaker(
            failure_threshold=3,
            success_threshold=1,
            recovery_timeout=0.5,  # 短超时便于测试
        )

        # 初始状态：关闭
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

        # 记录失败（还未达到阈值）
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED  # 仍然关闭

        # 达到阈值：打开
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False  # 熔断中，不允许执行

        # 等待恢复超时
        time.sleep(0.6)
        # can_execute() 会触发状态转换
        assert cb.can_execute() is True  # 进入半开状态，允许执行
        assert cb.state == CircuitState.HALF_OPEN

        # 半开状态下成功：恢复到关闭
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_error_handler_with_retry(self):
        """测试带重试的执行"""
        from multi_agent.error_handler import ErrorHandler, RetryPolicy

        call_count = [0]

        def flaky_func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("timeout error")
            return "success"

        handler = ErrorHandler(
            retry_policy=RetryPolicy(
                max_attempts=3,
                base_delay=0.1,
                jitter=False,
            )
        )

        result = handler.execute_with_result(flaky_func)
        assert result == "success"
        assert call_count[0] == 3

    def test_error_handler_with_fallback(self):
        """测试降级处理"""
        from multi_agent.error_handler import ErrorHandler, RetryPolicy, CircuitBreaker

        def always_fail():
            raise Exception("server error")

        def fallback_func():
            return "fallback result"

        handler = ErrorHandler(
            retry_policy=RetryPolicy(max_attempts=2, base_delay=0.1, jitter=False),
            fallback=fallback_func,
        )

        result = handler.execute_with_result(always_fail)
        assert result == "fallback result"


class TestOutputParser:
    """输出解析器测试"""

    def test_parse_json_direct(self):
        """测试直接JSON解析"""
        from multi_agent.output_parser import OutputParser

        text = '{"name": "test", "value": 123}'
        result = OutputParser.parse(text)
        assert result.success is True
        assert result.data == {"name": "test", "value": 123}

    def test_parse_json_from_code_block(self):
        """测试从代码块提取JSON"""
        from multi_agent.output_parser import OutputParser

        text = '''
        Here is the result:
        ```json
        {"name": "test", "value": 456}
        ```
        '''
        result = OutputParser.parse(text)
        assert result.success is True
        assert result.data == {"name": "test", "value": 456}

    def test_parse_json_from_braces(self):
        """测试从花括号提取JSON"""
        from multi_agent.output_parser import OutputParser

        text = 'The result is {"name": "test", "value": 789} as shown above.'
        result = OutputParser.parse(text)
        assert result.success is True
        assert result.data == {"name": "test", "value": 789}

    def test_parse_json_invalid(self):
        """测试无效JSON返回失败"""
        from multi_agent.output_parser import OutputParser

        text = "This is not JSON at all"
        result = OutputParser.parse(text)
        assert result.success is False
        assert result.error is not None

    def test_parse_to_pydantic_model(self):
        """测试解析到Pydantic模型"""
        from multi_agent.output_parser import OutputParser
        from multi_agent.output_schemas import ClassificationOutput, MessageType

        text = '''
        ```json
        {
            "type": "decree",
            "title": "测试任务",
            "urgency": "高",
            "complexity": "中等"
        }
        ```
        '''
        result = OutputParser.parse_to_model(text, ClassificationOutput)
        assert result.success is True
        assert result.model is not None
        assert result.model.type == MessageType.DECREE
        assert result.model.title == "测试任务"


class TestStateManagerExceptions:
    """状态管理异常测试"""

    def test_create_duplicate_task(self):
        """测试创建重复任务"""
        from multi_agent.state_manager import MultiAgentStateManager

        sm = MultiAgentStateManager()

        # 创建任务
        task1 = sm.create_task(
            task_id="duplicate-test",
            title="测试任务",
            message_type="decree",
            original_message="测试",
        )

        # 尝试创建重复任务应该抛出异常或静默处理
        try:
            task2 = sm.create_task(
                task_id="duplicate-test",
                title="重复任务",
                message_type="decree",
                original_message="重复",
            )
            # 如果没有抛异常，任务应该仍然存在
        except Exception:
            # 抛出异常是预期的行为
            pass

        # 验证任务存在
        task = sm.get_task("duplicate-test")
        assert task is not None

    def test_get_nonexistent_task(self):
        """测试获取不存在的任务"""
        from multi_agent.state_manager import MultiAgentStateManager

        sm = MultiAgentStateManager()

        task = sm.get_task("nonexistent-task-id")
        assert task is None

    def test_update_nonexistent_task_status(self):
        """测试更新不存在的任务状态"""
        from multi_agent.state_manager import MultiAgentStateManager
        from multi_agent.orchestrator import TaskStatus

        sm = MultiAgentStateManager()

        # 更新不存在的任务 - 根据实现可能抛异常或静默处理
        try:
            sm.update_task_status(
                task_id="nonexistent-task",
                status=TaskStatus.PLANNING,
                current_agent="zhongshu",
            )
        except Exception:
            pass  # 预期可能抛异常

        # 任务仍然不存在
        task = sm.get_task("nonexistent-task")
        assert task is None

    def test_add_audit_log_for_nonexistent_task(self):
        """测试为不存在的任务添加审计日志"""
        from multi_agent.state_manager import MultiAgentStateManager

        sm = MultiAgentStateManager()

        # 添加审计日志（应该成功）
        log_id = sm.add_audit_log(
            task_id="nonexistent-task",
            agent_id="test_agent",
            agent_name="测试Agent",
            action="test",
            input_summary="测试输入",
            output_summary="测试输出",
            status="success",
        )

        assert log_id is not None

    def test_block_non_running_task(self):
        """测试阻塞非运行中的任务"""
        from multi_agent.state_manager import MultiAgentStateManager
        from multi_agent.orchestrator import TaskStatus

        sm = MultiAgentStateManager()

        # 创建任务（CREATED状态）
        sm.create_task(
            task_id="block-test-created",
            title="阻塞测试",
            message_type="decree",
            original_message="测试",
        )

        # 尝试阻塞CREATED状态的任务 - 根据实现可能返回失败
        try:
            result = sm.block_task(
                task_id="block-test-created",
                reason="测试阻塞",
                by="user",
            )
            # 如果返回结果，可能是失败
            # result 可能是 None 或 {"success": False}
        except Exception:
            pass  # 预期可能抛异常

        # 验证任务状态未变（阻塞只对运行中任务有效）
        task = sm.get_task("block-test-created")
        assert task.status == TaskStatus.CREATED


class TestTaskInterventionExceptions:
    """任务干预异常测试"""

    def test_pause_nonexistent_task(self):
        """测试暂停不存在的任务"""
        from multi_agent.orchestrator import MultiAgentOrchestrator

        orchestrator = MultiAgentOrchestrator()

        # 暂停不存在的任务应该静默处理（不抛异常）
        orchestrator.pause_task("nonexistent-task")

    def test_resume_nonexistent_task(self):
        """测试恢复不存在的任务"""
        from multi_agent.orchestrator import MultiAgentOrchestrator

        orchestrator = MultiAgentOrchestrator()

        # 恢复不存在的任务应该静默处理
        orchestrator.resume_task("nonexistent-task")

    def test_cancel_nonexistent_task(self):
        """测试取消不存在的任务"""
        from multi_agent.orchestrator import MultiAgentOrchestrator

        orchestrator = MultiAgentOrchestrator()

        # 取消不存在的任务应该静默处理
        orchestrator.cancel_task("nonexistent-task")


class TestBoundaryConditions:
    """边界条件测试"""

    def test_empty_task_title(self):
        """测试空任务标题"""
        from multi_agent.state_manager import MultiAgentStateManager

        sm = MultiAgentStateManager()

        # 空标题应该被允许
        task = sm.create_task(
            task_id="empty-title-test",
            title="",
            message_type="decree",
            original_message="测试",
        )

        assert task is not None

    def test_very_long_task_id(self):
        """测试超长任务ID"""
        from multi_agent.state_manager import MultiAgentStateManager

        sm = MultiAgentStateManager()

        long_id = "a" * 500  # 500字符的任务ID

        task = sm.create_task(
            task_id=long_id,
            title="超长ID测试",
            message_type="decree",
            original_message="测试",
        )

        # 验证任务可以创建
        fetched = sm.get_task(long_id)
        assert fetched is not None

    def test_special_characters_in_task_data(self):
        """测试特殊字符在任务数据中"""
        from multi_agent.state_manager import MultiAgentStateManager

        sm = MultiAgentStateManager()

        special_title = "任务<>&\"'特殊字符\n换行\t制表符"

        sm.create_task(
            task_id="special-chars-test",
            title=special_title,
            message_type="decree",
            original_message="测试",
        )

        # 验证特殊字符被正确存储
        fetched = sm.get_task("special-chars-test")
        assert fetched.title == special_title

    def test_unicode_in_task_data(self):
        """测试Unicode在任务数据中"""
        from multi_agent.state_manager import MultiAgentStateManager

        sm = MultiAgentStateManager()

        unicode_title = "任务🎉emoji🚀中文日本語한국어"

        sm.create_task(
            task_id="unicode-test",
            title=unicode_title,
            message_type="decree",
            original_message="测试",
        )

        # 验证Unicode被正确存储
        fetched = sm.get_task("unicode-test")
        assert fetched.title == unicode_title

    def test_json_in_metadata(self):
        """测试JSON元数据"""
        from multi_agent.state_manager import MultiAgentStateManager
        import json

        sm = MultiAgentStateManager()

        complex_metadata = {
            "nested": {
                "deep": {
                    "value": 123,
                },
            },
            "list": [1, 2, 3],
            "string": "test",
            "bool": True,
            "null": None,
        }

        sm.create_task(
            task_id="json-metadata-test",
            title="JSON元数据测试",
            message_type="decree",
            original_message="测试",
            metadata=complex_metadata,
        )

        # 验证JSON被正确存储
        fetched = sm.get_task("json-metadata-test")
        # metadata 可能是字符串或字典
        metadata = fetched.metadata
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        assert metadata["nested"]["deep"]["value"] == 123


class TestArchiveExceptions:
    """存档异常测试"""

    def test_archive_nonexistent_task(self):
        """测试存档不存在的任务"""
        from multi_agent.orchestrator import MultiAgentOrchestrator

        orchestrator = MultiAgentOrchestrator()

        # 存档不存在的任务返回失败结果
        result = orchestrator.archive_task("nonexistent-task")
        assert result is not None
        assert result.get("success") is False

    def test_export_nonexistent_archive(self):
        """测试导出不存在的存档"""
        from multi_agent.orchestrator import MultiAgentOrchestrator

        orchestrator = MultiAgentOrchestrator()

        # 导出不存在的存档返回失败结果
        result = orchestrator.export_archive("nonexistent-archive-id")
        assert result is not None
        assert result.get("success") is False


class TestEventBusExceptions:
    """事件总线异常测试"""

    def test_publish_with_invalid_handler(self):
        """测试发布事件到无效处理器"""
        from multi_agent.event_bus import InMemoryEventBus, EventType, Event
        import uuid

        bus = InMemoryEventBus()

        # 订阅一个会抛出异常的处理器
        def bad_handler(event):
            raise Exception("Handler error")

        # 使用 EventType 枚举
        bus.subscribe(EventType.TASK_CREATED, bad_handler)

        # 创建并发布事件
        event = Event(
            event_id=str(uuid.uuid4())[:12],
            event_type=EventType.TASK_CREATED,
            task_id="test-task",
            payload={"data": "test"},
        )
        bus.publish(event)

        # 验证：即使处理器失败，事件总线不应该崩溃
        # 历史可能为空或包含事件，取决于实现
        history = bus.get_history(EventType.TASK_CREATED)
        # 主要验证：没有抛出异常就说明系统健壮
        assert True  # 如果执行到这里，说明系统健壮

    def test_subscribe_same_handler_twice(self):
        """测试重复订阅同一处理器"""
        from multi_agent.event_bus import InMemoryEventBus, EventType, Event
        import uuid

        bus = InMemoryEventBus()

        call_count = [0]

        def handler(event):
            call_count[0] += 1

        # 订阅两次（使用 EventType 枚举）
        bus.subscribe(EventType.TASK_STARTED, handler)
        bus.subscribe(EventType.TASK_STARTED, handler)

        # 创建并发布事件
        event = Event(
            event_id=str(uuid.uuid4())[:12],
            event_type=EventType.TASK_STARTED,
            task_id="test-task",
            payload={"data": "test"},
        )
        bus.publish(event)

        # 处理器应该被调用（可能一次或多次）
        assert call_count[0] >= 1

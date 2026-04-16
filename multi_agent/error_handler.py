"""
Error Handler - 错误处理增强

负责：
1. 智能重试策略（指数退避）
2. 熔断器（Circuit Breaker）
3. 优雅降级
4. 错误日志记录
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """熔断器状态"""
    CLOSED = "closed"          # 正常状态，允许所有请求
    OPEN = "open"              # 熔断状态，拒绝所有请求
    HALF_OPEN = "half_open"    # 半开状态，允许试探性请求


@dataclass
class RetryPolicy:
    """重试策略
    
    实现指数退避重试机制
    """
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True  # 添加随机抖动防止惊群效应
    
    # 可重试的错误类型
    retryable_errors: List[str] = field(default_factory=lambda: [
        "timeout",
        "rate_limit",
        "rate limit",
        "server_error",
        "server error",
        "internal error",
        "connection_error",
        "connection error",
        "connection reset",
        "network error",
        "503",
        "502",
        "500",
        "429",
        "overloaded",
        "capacity",
    ])
    
    # 不可重试的错误类型（优先级更高）
    non_retryable_errors: List[str] = field(default_factory=lambda: [
        "invalid_api_key",
        "invalid api key",
        "authentication",
        "unauthorized",
        "forbidden",
        "401",
        "403",
        "context_length",
        "context length",
        "token limit",
    ])
    
    def get_delay(self, attempt: int) -> float:
        """计算重试延迟（指数退避 + 抖动）
        
        Args:
            attempt: 当前尝试次数（从0开始）
            
        Returns:
            延迟秒数
        """
        # 指数退避
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        # 添加抖动（0.5x ~ 1.5x）
        if self.jitter:
            delay = delay * (0.5 + random.random())
        
        return delay
    
    def should_retry(self, error: str) -> bool:
        """判断是否应该重试
        
        Args:
            error: 错误信息
            
        Returns:
            是否应该重试
        """
        error_lower = error.lower()
        
        # 先检查不可重试的错误
        for non_retryable in self.non_retryable_errors:
            if non_retryable in error_lower:
                return False
        
        # 再检查可重试的错误
        for retryable in self.retryable_errors:
            if retryable in error_lower:
                return True
        
        # 默认不重试
        return False


@dataclass
class CircuitBreaker:
    """熔断器
    
    实现熔断模式，防止级联失败
    """
    failure_threshold: int = 5       # 触发熔断的失败次数
    success_threshold: int = 2       # 恢复到关闭状态的成功次数
    recovery_timeout: float = 60.0   # 熔断恢复超时时间（秒）
    
    # 状态
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0
    last_state_change: float = 0
    
    # 统计
    total_requests: int = 0
    total_failures: int = 0
    total_successes: int = 0
    
    def record_success(self) -> None:
        """记录成功"""
        self.total_requests += 1
        self.total_successes += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._transition_to(CircuitState.CLOSED)
                logger.info("Circuit breaker recovered: HALF_OPEN -> CLOSED")
        elif self.state == CircuitState.CLOSED:
            # 重置失败计数
            self.failure_count = 0
    
    def record_failure(self) -> None:
        """记录失败"""
        self.total_requests += 1
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # 半开状态下失败，立即回到熔断状态
            self._transition_to(CircuitState.OPEN)
            logger.warning("Circuit breaker tripped: HALF_OPEN -> OPEN")
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self._transition_to(CircuitState.OPEN)
                logger.warning(
                    f"Circuit breaker tripped: CLOSED -> OPEN "
                    f"(failures: {self.failure_count})"
                )
    
    def can_execute(self) -> bool:
        """检查是否可以执行请求
        
        Returns:
            是否允许执行
        """
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # 检查是否可以进入半开状态
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
                logger.info(
                    f"Circuit breaker entering recovery: OPEN -> HALF_OPEN "
                    f"(elapsed: {elapsed:.1f}s)"
                )
                return True
            return False
        
        # HALF_OPEN: 允许试探性请求
        return True
    
    def _transition_to(self, new_state: CircuitState) -> None:
        """状态转换"""
        old_state = self.state
        self.state = new_state
        self.last_state_change = time.time()
        
        # 重置计数器
        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self.success_count = 0
        elif new_state == CircuitState.OPEN:
            self.success_count = 0
        
        logger.debug(f"Circuit breaker state: {old_state.value} -> {new_state.value}")
    
    def reset(self) -> None:
        """重置熔断器"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info("Circuit breaker reset to CLOSED")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "failure_rate": (
                self.total_failures / self.total_requests 
                if self.total_requests > 0 else 0
            ),
        }


class ErrorHandler:
    """错误处理器
    
    组合重试策略和熔断器，提供完整的错误处理能力
    """
    
    def __init__(
        self,
        retry_policy: Optional[RetryPolicy] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        fallback: Optional[Callable] = None,
        name: str = "default",
    ):
        """初始化错误处理器
        
        Args:
            retry_policy: 重试策略
            circuit_breaker: 熔断器
            fallback: 降级函数
            name: 处理器名称（用于日志）
        """
        self.retry_policy = retry_policy or RetryPolicy()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.fallback = fallback
        self.name = name
    
    def execute(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> Tuple[Any, Optional[Exception]]:
        """执行函数（带重试和熔断保护）
        
        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            (result, error) 元组，error 为 None 表示成功
        """
        last_error: Optional[Exception] = None
        
        for attempt in range(self.retry_policy.max_attempts):
            # 检查熔断器
            if not self.circuit_breaker.can_execute():
                if self.fallback:
                    logger.warning(
                        f"[{self.name}] Circuit breaker OPEN, using fallback"
                    )
                    try:
                        return self.fallback(*args, **kwargs), None
                    except Exception as e:
                        return None, e
                return None, Exception("Circuit breaker is OPEN")
            
            try:
                result = func(*args, **kwargs)
                self.circuit_breaker.record_success()
                return result, None
                
            except Exception as e:
                last_error = e
                error_str = str(e)
                
                # 判断是否应该重试
                if not self.retry_policy.should_retry(error_str):
                    self.circuit_breaker.record_failure()
                    logger.error(
                        f"[{self.name}] Non-retryable error: {error_str[:100]}"
                    )
                    return None, e
                
                # 检查是否还有重试机会
                if attempt < self.retry_policy.max_attempts - 1:
                    delay = self.retry_policy.get_delay(attempt)
                    logger.warning(
                        f"[{self.name}] Attempt {attempt + 1}/{self.retry_policy.max_attempts} "
                        f"failed: {error_str[:50]}, retrying in {delay:.1f}s"
                    )
                    time.sleep(delay)
                else:
                    # 所有重试失败
                    self.circuit_breaker.record_failure()
                    logger.error(
                        f"[{self.name}] All {self.retry_policy.max_attempts} "
                        f"attempts failed: {error_str[:100]}"
                    )
        
        # 尝试降级
        if self.fallback:
            logger.warning(f"[{self.name}] Using fallback after all retries failed")
            try:
                return self.fallback(*args, **kwargs), None
            except Exception as e:
                return None, e
        
        return None, last_error
    
    def execute_with_result(self, func: Callable, *args, **kwargs) -> Any:
        """执行函数并返回结果（失败时抛出异常）
        
        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            函数返回值
            
        Raises:
            Exception: 所有重试失败后抛出最后一个异常
        """
        result, error = self.execute(func, *args, **kwargs)
        if error:
            raise error
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "name": self.name,
            "circuit_breaker": self.circuit_breaker.get_stats(),
            "retry_policy": {
                "max_attempts": self.retry_policy.max_attempts,
                "base_delay": self.retry_policy.base_delay,
            },
        }


# ============================================================================
# 装饰器
# ============================================================================

def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    retryable_errors: Optional[List[str]] = None,
    fallback: Optional[Callable] = None,
):
    """重试装饰器
    
    用法:
        @with_retry(max_attempts=3)
        def my_function():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = ErrorHandler(
                retry_policy=RetryPolicy(
                    max_attempts=max_attempts,
                    base_delay=base_delay,
                    retryable_errors=retryable_errors or [
                        "timeout", "rate_limit", "server_error", "connection_error"
                    ],
                ),
                fallback=fallback,
                name=func.__name__,
            )
            return handler.execute_with_result(func, *args, **kwargs)
        return wrapper
    return decorator


def with_circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    fallback: Optional[Callable] = None,
):
    """熔断器装饰器
    
    用法:
        @with_circuit_breaker(failure_threshold=3)
        def my_function():
            ...
    """
    def decorator(func):
        handler = ErrorHandler(
            circuit_breaker=CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
            ),
            fallback=fallback,
            name=func.__name__,
        )
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return handler.execute_with_result(func, *args, **kwargs)
        
        # 暴露 handler 以便查询状态
        wrapper.handler = handler
        return wrapper
    return decorator


# ============================================================================
# 全局错误处理器管理
# ============================================================================

# 按 Agent ID 存储错误处理器
_error_handlers: Dict[str, ErrorHandler] = {}


def get_error_handler(
    agent_id: str,
    config: Optional[Dict[str, Any]] = None,
) -> ErrorHandler:
    """获取或创建 Agent 的错误处理器
    
    Args:
        agent_id: Agent ID
        config: 配置字典
        
    Returns:
        ErrorHandler 实例
    """
    if agent_id not in _error_handlers:
        config = config or {}
        error_config = config.get("error_handling", {})
        
        retry_config = error_config.get("retry", {})
        cb_config = error_config.get("circuit_breaker", {})
        
        handler = ErrorHandler(
            retry_policy=RetryPolicy(
                max_attempts=retry_config.get("max_attempts", 3),
                base_delay=retry_config.get("base_delay", 1.0),
                max_delay=retry_config.get("max_delay", 30.0),
                exponential_base=retry_config.get("exponential_base", 2.0),
            ),
            circuit_breaker=CircuitBreaker(
                failure_threshold=cb_config.get("failure_threshold", 5),
                recovery_timeout=cb_config.get("recovery_timeout", 60.0),
            ),
            name=agent_id,
        )
        _error_handlers[agent_id] = handler
    
    return _error_handlers[agent_id]


def reset_all_circuit_breakers() -> None:
    """重置所有熔断器"""
    for handler in _error_handlers.values():
        handler.circuit_breaker.reset()
    logger.info("All circuit breakers reset")


def get_all_stats() -> Dict[str, Any]:
    """获取所有错误处理器的统计信息"""
    return {
        agent_id: handler.get_stats()
        for agent_id, handler in _error_handlers.items()
    }

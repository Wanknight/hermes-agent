"""
Multi-Agent State Manager - 状态持久化管理

负责：
1. SQLite 数据库管理
2. 任务状态持久化
3. Agent 执行记录
4. 事件日志存储
5. 历史查询
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)


# 数据库版本
DB_VERSION = 3  # v3: 添加归档表


@dataclass
class TaskRecord:
    """任务记录"""
    task_id: str
    title: str
    status: str
    message_type: str
    current_agent: str = ""
    creator: str = "user"
    original_message: str = ""
    classification: str = "{}"
    plan: str = "{}"
    review_result: str = "{}"
    execution_results: str = "[]"
    final_response: str = ""
    review_round: int = 0
    created_at: str = ""
    updated_at: str = ""
    metadata: str = "{}"


@dataclass
class AgentRunRecord:
    """Agent 执行记录"""
    run_id: str
    task_id: str
    agent_id: str
    agent_name: str
    input_data: str
    output: str = ""
    status: str = "pending"
    error: str = ""
    started_at: str = ""
    completed_at: str = ""
    tokens_used: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    latency_ms: int = 0
    model_version: str = ""
    metadata: str = "{}"


@dataclass
class EventRecord:
    """事件记录"""
    event_id: str
    task_id: str
    event_type: str
    agent_id: str
    payload: str = "{}"
    created_at: str = ""


@dataclass
class AuditLogRecord:
    """审计日志记录"""
    log_id: str
    task_id: str
    agent_id: str
    agent_name: str
    action: str  # 'call', 'dispatch', 'review', 'execute', 'classify', 'plan', 'dispatch'
    input_summary: str
    output_summary: str = ""
    status: str = "success"  # 'success', 'failed', 'timeout'
    error_message: str = ""
    tokens_used: int = 0
    latency_ms: int = 0
    model_version: str = ""
    created_at: str = ""


class MultiAgentStateManager:
    """多Agent状态管理器
    
    使用 SQLite 存储任务状态、执行记录和事件日志。
    数据库文件位置：~/.hermes/multi_agent.db
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """初始化状态管理器
        
        Args:
            db_path: 数据库文件路径，默认为 ~/.hermes/multi_agent.db
        """
        if db_path:
            self._db_path = Path(db_path)
        else:
            self._db_path = get_hermes_home() / "multi_agent.db"
        
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def _ensure_db(self):
        """确保数据库和表结构存在"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 创建任务表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ma_tasks (
                task_id TEXT PRIMARY KEY,
                title TEXT,
                status TEXT,
                message_type TEXT,
                current_agent TEXT,
                creator TEXT,
                original_message TEXT,
                classification TEXT,
                plan TEXT,
                review_result TEXT,
                execution_results TEXT,
                final_response TEXT,
                review_round INTEGER,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                metadata TEXT
            )
        """)
        
        # 创建 Agent 执行记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ma_agent_runs (
                run_id TEXT PRIMARY KEY,
                task_id TEXT,
                agent_id TEXT,
                agent_name TEXT,
                input_data TEXT,
                output TEXT,
                status TEXT,
                error TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                tokens_used INTEGER,
                metadata TEXT,
                FOREIGN KEY (task_id) REFERENCES ma_tasks(task_id)
            )
        """)
        
        # 创建事件日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ma_events (
                event_id TEXT PRIMARY KEY,
                task_id TEXT,
                event_type TEXT,
                agent_id TEXT,
                payload TEXT,
                created_at TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES ma_tasks(task_id)
            )
        """)
        
        # 创建审计日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ma_audit_log (
                log_id TEXT PRIMARY KEY,
                task_id TEXT,
                agent_id TEXT,
                agent_name TEXT,
                action TEXT,
                input_summary TEXT,
                output_summary TEXT,
                status TEXT,
                error_message TEXT,
                tokens_used INTEGER,
                latency_ms INTEGER,
                model_version TEXT,
                created_at TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES ma_tasks(task_id)
            )
        """)
        
        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_status 
            ON ma_tasks(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_created 
            ON ma_tasks(created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_task 
            ON ma_agent_runs(task_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_task 
            ON ma_events(task_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_type 
            ON ma_events(event_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_task 
            ON ma_audit_log(task_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_agent 
            ON ma_audit_log(agent_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_action 
            ON ma_audit_log(action)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_created 
            ON ma_audit_log(created_at)
        """)
        
        # 创建归档表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ma_archives (
                archive_id TEXT PRIMARY KEY,
                task_id TEXT,
                title TEXT,
                message_type TEXT,
                original_message TEXT,
                classification TEXT,
                plan TEXT,
                review_result TEXT,
                execution_results TEXT,
                final_response TEXT,
                status TEXT,
                result TEXT,
                created_at TIMESTAMP,
                completed_at TIMESTAMP,
                archived_at TIMESTAMP,
                metadata TEXT
            )
        """)
        
        # 归档表索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_archives_task 
            ON ma_archives(task_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_archives_created 
            ON ma_archives(created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_archives_status 
            ON ma_archives(status)
        """)
        
        # 创建版本表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ma_version (
                version INTEGER PRIMARY KEY
            )
        """)
        
        # 检查版本并执行迁移
        cursor.execute("SELECT version FROM ma_version")
        row = cursor.fetchone()
        current_version = row["version"] if row else 0
        
        if row is None:
            cursor.execute("INSERT INTO ma_version (version) VALUES (?)", (DB_VERSION,))
        elif current_version < DB_VERSION:
            # 执行版本迁移
            self._migrate_db(current_version, cursor)
            cursor.execute("UPDATE ma_version SET version = ?", (DB_VERSION,))
        
        conn.commit()
        logger.info(f"数据库初始化完成: {self._db_path}")
    
    def _migrate_db(self, from_version: int, cursor: sqlite3.Cursor):
        """数据库版本迁移
        
        Args:
            from_version: 当前版本
            cursor: 数据库游标
        """
        if from_version < 2:
            # v1 -> v2: 添加审计日志表
            logger.info("执行数据库迁移 v1 -> v2: 添加审计日志表")
            # 表已在 _ensure_db 中创建，这里只需处理旧表结构变更
            # 检查 ma_agent_runs 是否有新字段
            cursor.execute("PRAGMA table_info(ma_agent_runs)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if "tokens_input" not in columns:
                cursor.execute("ALTER TABLE ma_agent_runs ADD COLUMN tokens_input INTEGER DEFAULT 0")
            if "tokens_output" not in columns:
                cursor.execute("ALTER TABLE ma_agent_runs ADD COLUMN tokens_output INTEGER DEFAULT 0")
            if "latency_ms" not in columns:
                cursor.execute("ALTER TABLE ma_agent_runs ADD COLUMN latency_ms INTEGER DEFAULT 0")
            if "model_version" not in columns:
                cursor.execute("ALTER TABLE ma_agent_runs ADD COLUMN model_version TEXT DEFAULT ''")
            
            logger.info("数据库迁移 v1 -> v2 完成")
        
        if from_version < 3:
            # v2 -> v3: 添加归档表
            logger.info("执行数据库迁移 v2 -> v3: 添加归档表")
            # 表已在 _ensure_db 中创建，无需额外操作
            logger.info("数据库迁移 v2 -> v3 完成")
    
    # ==================== 任务操作 ====================
    
    def create_task(
        self,
        task_id: str,
        title: str,
        message_type: str = "decree",
        creator: str = "user",
        original_message: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskRecord:
        """创建任务
        
        Args:
            task_id: 任务ID
            title: 任务标题
            message_type: 消息类型 (chat/decree)
            creator: 创建者
            original_message: 原始消息
            metadata: 元数据
        
        Returns:
            任务记录
        """
        now = datetime.now().isoformat()
        
        record = TaskRecord(
            task_id=task_id,
            title=title,
            status="created",
            message_type=message_type,
            creator=creator,
            original_message=original_message,
            created_at=now,
            updated_at=now,
            metadata=json.dumps(metadata or {}, ensure_ascii=False),
        )
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO ma_tasks (
                task_id, title, status, message_type, current_agent,
                creator, original_message, classification, plan,
                review_result, execution_results, final_response,
                review_round, created_at, updated_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.task_id, record.title, record.status, record.message_type,
            record.current_agent, record.creator, record.original_message,
            record.classification, record.plan, record.review_result,
            record.execution_results, record.final_response, record.review_round,
            record.created_at, record.updated_at, record.metadata,
        ))
        
        conn.commit()
        logger.info(f"任务创建: {task_id} - {title}")
        
        # 添加创建事件
        self.add_event(
            task_id=task_id,
            event_type="task.created",
            agent_id="system",
            payload={"title": title, "message_type": message_type},
        )
        
        return record
    
    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        """获取任务
        
        Args:
            task_id: 任务ID
        
        Returns:
            任务记录，不存在返回 None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM ma_tasks WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        return TaskRecord(
            task_id=row["task_id"],
            title=row["title"],
            status=row["status"],
            message_type=row["message_type"],
            current_agent=row["current_agent"],
            creator=row["creator"],
            original_message=row["original_message"],
            classification=row["classification"],
            plan=row["plan"],
            review_result=row["review_result"],
            execution_results=row["execution_results"],
            final_response=row["final_response"],
            review_round=row["review_round"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=row["metadata"],
        )
    
    def update_task_status(
        self,
        task_id: str,
        status: str,
        current_agent: Optional[str] = None,
    ) -> bool:
        """更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            current_agent: 当前执行的Agent
        
        Returns:
            是否更新成功
        """
        now = datetime.now().isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if current_agent:
            cursor.execute("""
                UPDATE ma_tasks 
                SET status = ?, current_agent = ?, updated_at = ?
                WHERE task_id = ?
            """, (status, current_agent, now, task_id))
        else:
            cursor.execute("""
                UPDATE ma_tasks 
                SET status = ?, updated_at = ?
                WHERE task_id = ?
            """, (status, now, task_id))
        
        conn.commit()
        
        if cursor.rowcount > 0:
            # 添加状态变更事件
            self.add_event(
                task_id=task_id,
                event_type=f"task.status.{status}",
                agent_id=current_agent or "system",
                payload={"status": status},
            )
            return True
        
        return False
    
    def update_task_data(
        self,
        task_id: str,
        **kwargs,
    ) -> bool:
        """更新任务数据
        
        Args:
            task_id: 任务ID
            **kwargs: 要更新的字段
        
        Returns:
            是否更新成功
        """
        if not kwargs:
            return False
        
        now = datetime.now().isoformat()
        kwargs["updated_at"] = now
        
        # 构建更新语句
        fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [task_id]
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(f"UPDATE ma_tasks SET {fields} WHERE task_id = ?", values)
        conn.commit()
        
        return cursor.rowcount > 0
    
    def list_tasks(
        self,
        status: Optional[str] = None,
        message_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[TaskRecord]:
        """列出任务
        
        Args:
            status: 状态过滤
            message_type: 消息类型过滤
            limit: 返回数量限制
            offset: 偏移量
        
        Returns:
            任务列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM ma_tasks"
        conditions = []
        params = []
        
        if status:
            conditions.append("status = ?")
            params.append(status)
        if message_type:
            conditions.append("message_type = ?")
            params.append(message_type)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [
            TaskRecord(
                task_id=row["task_id"],
                title=row["title"],
                status=row["status"],
                message_type=row["message_type"],
                current_agent=row["current_agent"],
                creator=row["creator"],
                original_message=row["original_message"],
                classification=row["classification"],
                plan=row["plan"],
                review_result=row["review_result"],
                execution_results=row["execution_results"],
                final_response=row["final_response"],
                review_round=row["review_round"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                metadata=row["metadata"],
            )
            for row in rows
        ]
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务
        
        Args:
            task_id: 任务ID
        
        Returns:
            是否删除成功
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 先删除关联记录
        cursor.execute("DELETE FROM ma_events WHERE task_id = ?", (task_id,))
        cursor.execute("DELETE FROM ma_agent_runs WHERE task_id = ?", (task_id,))
        cursor.execute("DELETE FROM ma_tasks WHERE task_id = ?", (task_id,))
        
        conn.commit()
        
        return cursor.rowcount > 0
    
    # ==================== Agent 执行记录 ====================
    
    def add_agent_run(
        self,
        run_id: str,
        task_id: str,
        agent_id: str,
        agent_name: str,
        input_data: str,
        status: str = "pending",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentRunRecord:
        """添加 Agent 执行记录
        
        Args:
            run_id: 执行ID
            task_id: 任务ID
            agent_id: Agent ID
            agent_name: Agent 名称
            input_data: 输入数据
            status: 状态
            metadata: 元数据
        
        Returns:
            执行记录
        """
        now = datetime.now().isoformat()
        
        record = AgentRunRecord(
            run_id=run_id,
            task_id=task_id,
            agent_id=agent_id,
            agent_name=agent_name,
            input_data=input_data,
            status=status,
            started_at=now,
            metadata=json.dumps(metadata or {}, ensure_ascii=False),
        )
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO ma_agent_runs (
                run_id, task_id, agent_id, agent_name, input_data,
                output, status, error, started_at, completed_at,
                tokens_used, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.run_id, record.task_id, record.agent_id, record.agent_name,
            record.input_data, record.output, record.status, record.error,
            record.started_at, record.completed_at, record.tokens_used, record.metadata,
        ))
        
        conn.commit()
        
        # 更新任务当前Agent
        self.update_task_status(task_id, status="running", current_agent=agent_id)
        
        return record
    
    def update_agent_run(
        self,
        run_id: str,
        output: Optional[str] = None,
        status: Optional[str] = None,
        error: Optional[str] = None,
        tokens_used: Optional[int] = None,
    ) -> bool:
        """更新 Agent 执行记录
        
        Args:
            run_id: 执行ID
            output: 输出结果
            status: 状态
            error: 错误信息
            tokens_used: 使用的token数
        
        Returns:
            是否更新成功
        """
        updates = {}
        
        if output is not None:
            updates["output"] = output
        if status is not None:
            updates["status"] = status
        if error is not None:
            updates["error"] = error
        if tokens_used is not None:
            updates["tokens_used"] = tokens_used
        
        # 如果状态是完成，记录完成时间
        if status in ("completed", "failed"):
            updates["completed_at"] = datetime.now().isoformat()
        
        if not updates:
            return False
        
        fields = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [run_id]
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(f"UPDATE ma_agent_runs SET {fields} WHERE run_id = ?", values)
        conn.commit()
        
        return cursor.rowcount > 0
    
    def get_task_runs(self, task_id: str) -> List[AgentRunRecord]:
        """获取任务的所有执行记录
        
        Args:
            task_id: 任务ID
        
        Returns:
            执行记录列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM ma_agent_runs WHERE task_id = ? ORDER BY started_at",
            (task_id,)
        )
        rows = cursor.fetchall()
        
        return [
            AgentRunRecord(
                run_id=row["run_id"],
                task_id=row["task_id"],
                agent_id=row["agent_id"],
                agent_name=row["agent_name"],
                input_data=row["input_data"],
                output=row["output"],
                status=row["status"],
                error=row["error"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
                tokens_used=row["tokens_used"],
                metadata=row["metadata"],
            )
            for row in rows
        ]
    
    # ==================== 事件日志 ====================
    
    def add_event(
        self,
        task_id: str,
        event_type: str,
        agent_id: str,
        payload: Optional[Dict[str, Any]] = None,
        event_id: Optional[str] = None,
    ) -> EventRecord:
        """添加事件
        
        Args:
            task_id: 任务ID
            event_type: 事件类型
            agent_id: Agent ID
            payload: 事件数据
            event_id: 事件ID（可选）
        
        Returns:
            事件记录
        """
        now = datetime.now().isoformat()
        
        record = EventRecord(
            event_id=event_id or f"evt-{uuid.uuid4().hex[:8]}",
            task_id=task_id,
            event_type=event_type,
            agent_id=agent_id,
            payload=json.dumps(payload or {}, ensure_ascii=False),
            created_at=now,
        )
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO ma_events (event_id, task_id, event_type, agent_id, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            record.event_id, record.task_id, record.event_type,
            record.agent_id, record.payload, record.created_at,
        ))
        
        conn.commit()
        
        return record
    
    def get_task_events(
        self,
        task_id: str,
        event_type: Optional[str] = None,
    ) -> List[EventRecord]:
        """获取任务的事件历史
        
        Args:
            task_id: 任务ID
            event_type: 事件类型过滤
        
        Returns:
            事件列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if event_type:
            cursor.execute(
                "SELECT * FROM ma_events WHERE task_id = ? AND event_type = ? ORDER BY created_at",
                (task_id, event_type)
            )
        else:
            cursor.execute(
                "SELECT * FROM ma_events WHERE task_id = ? ORDER BY created_at",
                (task_id,)
            )
        
        rows = cursor.fetchall()
        
        return [
            EventRecord(
                event_id=row["event_id"],
                task_id=row["task_id"],
                event_type=row["event_type"],
                agent_id=row["agent_id"],
                payload=row["payload"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
    
    # ==================== 统计与查询 ====================
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            统计数据
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 任务统计
        cursor.execute("SELECT COUNT(*) FROM ma_tasks")
        total_tasks = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM ma_tasks WHERE status = 'completed'")
        completed_tasks = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM ma_tasks WHERE status = 'failed'")
        failed_tasks = cursor.fetchone()[0]
        
        # 执行记录统计
        cursor.execute("SELECT COUNT(*) FROM ma_agent_runs")
        total_runs = cursor.fetchone()[0]
        
        # 事件统计
        cursor.execute("SELECT COUNT(*) FROM ma_events")
        total_events = cursor.fetchone()[0]
        
        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "active_tasks": total_tasks - completed_tasks - failed_tasks,
            "total_agent_runs": total_runs,
            "total_events": total_events,
        }
    
    # ==================== 审计日志 ====================
    
    def add_audit_log(
        self,
        task_id: str,
        agent_id: str,
        agent_name: str,
        action: str,
        input_summary: str,
        output_summary: str = "",
        status: str = "success",
        error_message: str = "",
        tokens_used: int = 0,
        latency_ms: int = 0,
        model_version: str = "",
        log_id: Optional[str] = None,
    ) -> AuditLogRecord:
        """添加审计日志
        
        Args:
            task_id: 任务ID
            agent_id: Agent ID
            agent_name: Agent 名称
            action: 操作类型 (call, dispatch, review, execute, classify, plan)
            input_summary: 输入摘要
            output_summary: 输出摘要
            status: 状态 (success, failed, timeout)
            error_message: 错误信息
            tokens_used: 使用的token数
            latency_ms: 延迟毫秒数
            model_version: 模型版本
            log_id: 日志ID（可选）
        
        Returns:
            审计日志记录
        """
        now = datetime.now().isoformat()
        
        # 截断输入输出摘要（最多500字符）
        input_summary = input_summary[:500] if input_summary else ""
        output_summary = output_summary[:500] if output_summary else ""
        
        record = AuditLogRecord(
            log_id=log_id or f"audit-{uuid.uuid4().hex[:8]}",
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
            created_at=now,
        )
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO ma_audit_log (
                log_id, task_id, agent_id, agent_name, action,
                input_summary, output_summary, status, error_message,
                tokens_used, latency_ms, model_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.log_id, record.task_id, record.agent_id, record.agent_name,
            record.action, record.input_summary, record.output_summary,
            record.status, record.error_message, record.tokens_used,
            record.latency_ms, record.model_version, record.created_at,
        ))
        
        conn.commit()
        
        logger.debug(f"审计日志记录: [{agent_name}] {action} - {status}")
        return record
    
    def get_audit_logs(
        self,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        action: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditLogRecord]:
        """查询审计日志
        
        Args:
            task_id: 任务ID过滤
            agent_id: Agent ID过滤
            action: 操作类型过滤
            status: 状态过滤
            limit: 返回数量限制
            offset: 偏移量
        
        Returns:
            审计日志列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM ma_audit_log"
        conditions = []
        params = []
        
        if task_id:
            conditions.append("task_id = ?")
            params.append(task_id)
        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if action:
            conditions.append("action = ?")
            params.append(action)
        if status:
            conditions.append("status = ?")
            params.append(status)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [
            AuditLogRecord(
                log_id=row["log_id"],
                task_id=row["task_id"],
                agent_id=row["agent_id"],
                agent_name=row["agent_name"],
                action=row["action"],
                input_summary=row["input_summary"],
                output_summary=row["output_summary"],
                status=row["status"],
                error_message=row["error_message"],
                tokens_used=row["tokens_used"],
                latency_ms=row["latency_ms"],
                model_version=row["model_version"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
    
    def get_task_audit_logs(self, task_id: str) -> List[AuditLogRecord]:
        """获取任务的所有审计日志
        
        Args:
            task_id: 任务ID
        
        Returns:
            审计日志列表
        """
        return self.get_audit_logs(task_id=task_id, limit=1000)
    
    def export_audit_logs(
        self,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        action: Optional[str] = None,
        format: str = "json",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 1000,
    ) -> str:
        """导出审计日志
        
        Args:
            task_id: 任务ID过滤
            agent_id: Agent ID过滤
            action: 操作类型过滤
            format: 导出格式 (json, csv)
            start_time: 开始时间
            end_time: 结束时间
            limit: 导出数量限制
        
        Returns:
            导出的数据字符串
        """
        import csv
        import io
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM ma_audit_log"
        conditions = []
        params = []
        
        if task_id:
            conditions.append("task_id = ?")
            params.append(task_id)
        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if action:
            conditions.append("action = ?")
            params.append(action)
        if start_time:
            conditions.append("created_at >= ?")
            params.append(start_time)
        if end_time:
            conditions.append("created_at <= ?")
            params.append(end_time)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        if format == "json":
            records = []
            for row in rows:
                records.append({
                    "log_id": row["log_id"],
                    "task_id": row["task_id"],
                    "agent_id": row["agent_id"],
                    "agent_name": row["agent_name"],
                    "action": row["action"],
                    "input_summary": row["input_summary"],
                    "output_summary": row["output_summary"],
                    "status": row["status"],
                    "error_message": row["error_message"],
                    "tokens_used": row["tokens_used"],
                    "latency_ms": row["latency_ms"],
                    "model_version": row["model_version"],
                    "created_at": row["created_at"],
                })
            return json.dumps(records, ensure_ascii=False, indent=2)
        
        elif format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            
            # 写入表头
            writer.writerow([
                "log_id", "task_id", "agent_id", "agent_name", "action",
                "input_summary", "output_summary", "status", "error_message",
                "tokens_used", "latency_ms", "model_version", "created_at"
            ])
            
            # 写入数据
            for row in rows:
                writer.writerow([
                    row["log_id"], row["task_id"], row["agent_id"], row["agent_name"],
                    row["action"], row["input_summary"], row["output_summary"],
                    row["status"], row["error_message"], row["tokens_used"],
                    row["latency_ms"], row["model_version"], row["created_at"],
                ])
            
            return output.getvalue()
        
        else:
            raise ValueError(f"不支持的导出格式: {format}")
    
    # ==================== Agent 统计 ====================
    
    def get_agent_stats_today(self) -> Dict[str, Dict[str, Any]]:
        """获取今日 Agent 调用统计
        
        Returns:
            Agent 统计字典，key 为 agent_id，value 为统计信息
        """
        from hermes_time import now as _hermes_now
        
        now = _hermes_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 查询今日审计日志中的 Agent 调用
        cursor.execute("""
            SELECT 
                agent_id,
                agent_name,
                COUNT(*) as calls,
                SUM(tokens_used) as total_tokens,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count
            FROM ma_audit_log
            WHERE created_at >= ?
            GROUP BY agent_id
            ORDER BY calls DESC
        """, (today_start.isoformat(),))
        
        rows = cursor.fetchall()
        
        result = {}
        for row in rows:
            agent_id = row["agent_id"]
            total = row["calls"]
            success = row["success_count"]
            success_rate = success / total if total > 0 else 1.0
            
            result[agent_id] = {
                "name": row["agent_name"],
                "calls": row["calls"],
                "tokens": row["total_tokens"] or 0,
                "success_rate": success_rate,
            }
        
        return result
    
    # ==================== 任务干预操作 ====================
    
    def cancel_task(
        self,
        task_id: str,
        reason: str = "",
        by: str = "user",
    ) -> Dict[str, Any]:
        """取消任务
        
        Args:
            task_id: 任务ID
            reason: 取消原因
            by: 操作者
            
        Returns:
            操作结果 {"success": bool, "message": str, "task": Optional[TaskRecord]}
        """
        task = self.get_task(task_id)
        if not task:
            return {"success": False, "message": f"任务不存在: {task_id}"}
        
        # 检查是否可以取消
        if task.status in ("completed", "failed", "cancelled"):
            return {
                "success": False,
                "message": f"任务状态为 {task.status}，无法取消",
                "task": task,
            }
        
        # 更新状态
        now = datetime.now().isoformat()
        metadata = json.loads(task.metadata) if task.metadata else {}
        metadata["intervention"] = {
            "type": "cancel",
            "reason": reason,
            "by": by,
            "at": now,
        }
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE ma_tasks 
            SET status = 'cancelled', metadata = ?, updated_at = ?
            WHERE task_id = ?
        """, (json.dumps(metadata), now, task_id))
        
        conn.commit()
        
        if cursor.rowcount > 0:
            # 添加干预事件
            self.add_event(
                task_id=task_id,
                event_type="task.cancelled",
                agent_id="system",
                payload={"reason": reason, "by": by},
            )
            
            updated_task = self.get_task(task_id)
            return {
                "success": True,
                "message": f"任务已取消: {task_id}",
                "task": updated_task,
            }
        
        return {"success": False, "message": "更新失败", "task": task}
    
    def pause_task(
        self,
        task_id: str,
        reason: str = "",
        by: str = "user",
    ) -> Dict[str, Any]:
        """暂停任务
        
        Args:
            task_id: 任务ID
            reason: 暂停原因
            by: 操作者
            
        Returns:
            操作结果 {"success": bool, "message": str, "task": Optional[TaskRecord]}
        """
        task = self.get_task(task_id)
        if not task:
            return {"success": False, "message": f"任务不存在: {task_id}"}
        
        # 检查是否可以暂停
        pausable_statuses = ("classifying", "planning", "reviewing", "dispatching", "executing")
        if task.status not in pausable_statuses:
            return {
                "success": False,
                "message": f"任务状态为 {task.status}，无法暂停（只能在运行中状态暂停）",
                "task": task,
            }
        
        # 更新状态
        now = datetime.now().isoformat()
        metadata = json.loads(task.metadata) if task.metadata else {}
        metadata["intervention"] = {
            "type": "pause",
            "reason": reason,
            "by": by,
            "at": now,
            "previous_status": task.status,
        }
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE ma_tasks 
            SET status = 'paused', metadata = ?, updated_at = ?
            WHERE task_id = ?
        """, (json.dumps(metadata), now, task_id))
        
        conn.commit()
        
        if cursor.rowcount > 0:
            # 添加干预事件
            self.add_event(
                task_id=task_id,
                event_type="task.paused",
                agent_id="system",
                payload={"reason": reason, "by": by, "previous_status": task.status},
            )
            
            updated_task = self.get_task(task_id)
            return {
                "success": True,
                "message": f"任务已暂停: {task_id}（原状态: {task.status}）",
                "task": updated_task,
            }
        
        return {"success": False, "message": "更新失败", "task": task}
    
    def resume_task(
        self,
        task_id: str,
        by: str = "user",
    ) -> Dict[str, Any]:
        """恢复暂停的任务
        
        Args:
            task_id: 任务ID
            by: 操作者
            
        Returns:
            操作结果 {"success": bool, "message": str, "task": Optional[TaskRecord]}
        """
        task = self.get_task(task_id)
        if not task:
            return {"success": False, "message": f"任务不存在: {task_id}"}
        
        # 检查是否可以恢复
        if task.status != "paused":
            return {
                "success": False,
                "message": f"任务状态为 {task.status}，无法恢复（只能在暂停状态恢复）",
                "task": task,
            }
        
        # 获取暂停前的状态
        metadata = json.loads(task.metadata) if task.metadata else {}
        intervention = metadata.get("intervention", {})
        previous_status = intervention.get("previous_status", "created")
        
        # 更新状态
        now = datetime.now().isoformat()
        metadata["intervention"] = {
            "type": "resume",
            "by": by,
            "at": now,
            "previous_intervention": intervention,
        }
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE ma_tasks 
            SET status = ?, metadata = ?, updated_at = ?
            WHERE task_id = ?
        """, (previous_status, json.dumps(metadata), now, task_id))
        
        conn.commit()
        
        if cursor.rowcount > 0:
            # 添加干预事件
            self.add_event(
                task_id=task_id,
                event_type="task.resumed",
                agent_id="system",
                payload={"by": by, "resumed_to": previous_status},
            )
            
            updated_task = self.get_task(task_id)
            return {
                "success": True,
                "message": f"任务已恢复: {task_id}（恢复到: {previous_status}）",
                "task": updated_task,
            }
        
        return {"success": False, "message": "更新失败", "task": task}
    
    def get_intervention_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务的干预状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            干预状态信息
        """
        task = self.get_task(task_id)
        if not task:
            return {"exists": False, "message": f"任务不存在: {task_id}"}
        
        metadata = json.loads(task.metadata) if task.metadata else {}
        intervention = metadata.get("intervention", {})
        
        return {
            "exists": True,
            "task_id": task_id,
            "status": task.status,
            "is_cancellable": task.status not in ("completed", "failed", "cancelled"),
            "is_pausable": task.status in ("classifying", "planning", "reviewing", "dispatching", "executing"),
            "is_resumable": task.status == "paused" and intervention.get("previous_status"),
            "intervention": intervention if intervention else None,
        }
    
    def block_task(
        self,
        task_id: str,
        reason: str,
        by: str = "",
        context: Dict[str, Any] = None,
        options: List[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """阻塞任务，等待用户确认
        
        Args:
            task_id: 任务ID
            reason: 阻塞原因
            by: 阻塞方（agent_id）
            context: 阻塞上下文信息
            options: 用户可选项列表
            
        Returns:
            操作结果 {"success": bool, "message": str, "task": Optional[TaskRecord]}
        """
        task = self.get_task(task_id)
        if not task:
            return {"success": False, "message": f"任务不存在: {task_id}"}
        
        # 检查是否可以阻塞
        blockable_statuses = ("classifying", "planning", "reviewing", "dispatching", "executing")
        if task.status not in blockable_statuses:
            return {
                "success": False,
                "message": f"任务状态为 {task.status}，无法阻塞（只能在运行中状态阻塞）",
                "task": task,
            }
        
        # 更新状态
        now = datetime.now().isoformat()
        metadata = json.loads(task.metadata) if task.metadata else {}
        metadata["blocked"] = {
            "reason": reason,
            "by": by,
            "at": now,
            "previous_status": task.status,
            "context": context or {},
            "options": options or [],
        }
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE ma_tasks 
            SET status = 'blocked', metadata = ?, updated_at = ?
            WHERE task_id = ?
        """, (json.dumps(metadata), now, task_id))
        
        conn.commit()
        
        if cursor.rowcount > 0:
            # 添加阻塞事件
            self.add_event(
                task_id=task_id,
                event_type="task.blocked",
                agent_id=by or "system",
                payload={"reason": reason, "previous_status": task.status, "options": options},
            )
            
            updated_task = self.get_task(task_id)
            return {
                "success": True,
                "message": f"任务已阻塞: {task_id}",
                "task": updated_task,
                "options": options,
            }
        
        return {"success": False, "message": "更新失败", "task": task}
    
    def unblock_task(
        self,
        task_id: str,
        user_decision: str = "continue",
        by: str = "user",
    ) -> Dict[str, Any]:
        """解除任务阻塞状态
        
        Args:
            task_id: 任务ID
            user_decision: 用户决策 ("continue", "cancel", 或自定义选项ID)
            by: 操作者
            
        Returns:
            操作结果 {"success": bool, "message": str, "task": Optional[TaskRecord]}
        """
        task = self.get_task(task_id)
        if not task:
            return {"success": False, "message": f"任务不存在: {task_id}"}
        
        if task.status != "blocked":
            return {
                "success": False,
                "message": f"任务状态为 {task.status}，不在阻塞状态",
                "task": task,
            }
        
        # 获取之前的状态
        metadata = json.loads(task.metadata) if task.metadata else {}
        blocked_info = metadata.get("blocked", {})
        previous_status = blocked_info.get("previous_status", "created")
        
        now = datetime.now().isoformat()
        
        # 处理用户决策
        if user_decision == "cancel":
            # 用户选择取消任务
            new_status = "cancelled"
            metadata["blocked"]["user_decision"] = "cancel"
            metadata["blocked"]["decision_by"] = by
            metadata["blocked"]["decision_at"] = now
        else:
            # 继续执行
            new_status = previous_status
            metadata["blocked"]["user_decision"] = user_decision
            metadata["blocked"]["decision_by"] = by
            metadata["blocked"]["decision_at"] = now
        
        # 清除阻塞标记但保留历史记录
        del metadata["blocked"]
        metadata["block_history"] = metadata.get("block_history", [])
        metadata["block_history"].append(blocked_info)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE ma_tasks 
            SET status = ?, metadata = ?, updated_at = ?
            WHERE task_id = ?
        """, (new_status, json.dumps(metadata), now, task_id))
        
        conn.commit()
        
        if cursor.rowcount > 0:
            # 添加解阻塞事件
            self.add_event(
                task_id=task_id,
                event_type="task.unblocked",
                agent_id="system",
                payload={"decision": user_decision, "new_status": new_status, "by": by},
            )
            
            updated_task = self.get_task(task_id)
            return {
                "success": True,
                "message": f"任务已解除阻塞: {task_id}（决策: {user_decision}, 状态: {new_status}）",
                "task": updated_task,
                "new_status": new_status,
            }
        
        return {"success": False, "message": "更新失败", "task": task}
    
    def get_blocked_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务的阻塞状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            阻塞状态信息
        """
        task = self.get_task(task_id)
        if not task:
            return {"exists": False, "message": f"任务不存在: {task_id}"}
        
        metadata = json.loads(task.metadata) if task.metadata else {}
        blocked_info = metadata.get("blocked", {})
        
        return {
            "exists": True,
            "task_id": task_id,
            "is_blocked": task.status == "blocked",
            "status": task.status,
            "blocked_info": blocked_info if blocked_info else None,
            "options": blocked_info.get("options", []) if blocked_info else [],
        }
    
    # ==================== 归档操作 ====================
    
    def archive_task(self, task_id: str, result: str = "success") -> Dict[str, Any]:
        """归档任务
        
        Args:
            task_id: 任务ID
            result: 任务结果 ("success", "failed", "cancelled")
            
        Returns:
            操作结果 {"success": bool, "message": str, "archive_id": str}
        """
        task = self.get_task(task_id)
        if not task:
            return {"success": False, "message": f"任务不存在: {task_id}"}
        
        # 检查任务是否已完成
        if task.status not in ("completed", "failed", "cancelled"):
            return {"success": False, "message": f"任务状态为 {task.status}，无法归档（只能归档已完成的任务）"}
        
        # 检查是否已归档
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT archive_id FROM ma_archives WHERE task_id = ?", (task_id,))
        if cursor.fetchone():
            return {"success": False, "message": f"任务已归档: {task_id}"}
        
        # 生成归档ID
        archive_id = f"arch-{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        
        # 插入归档记录
        cursor.execute("""
            INSERT INTO ma_archives (
                archive_id, task_id, title, message_type, original_message,
                classification, plan, review_result, execution_results,
                final_response, status, result, created_at, completed_at, archived_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            archive_id,
            task_id,
            task.title,
            task.message_type,
            task.original_message,
            task.classification,
            task.plan,
            task.review_result,
            task.execution_results,
            task.final_response,
            task.status,
            result,
            task.created_at,
            task.updated_at,
            now,
            task.metadata,
        ))
        
        # 添加归档事件
        self.add_event(
            task_id=task_id,
            event_type="task.archived",
            agent_id="system",
            payload={"archive_id": archive_id, "result": result},
        )
        
        conn.commit()
        
        return {
            "success": True,
            "message": f"任务已归档: {task_id}",
            "archive_id": archive_id,
        }
    
    def get_archive(self, archive_id: str) -> Optional[Dict[str, Any]]:
        """获取归档记录
        
        Args:
            archive_id: 归档ID
            
        Returns:
            归档记录或 None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM ma_archives WHERE archive_id = ?", (archive_id,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        
        # 尝试按 task_id 查找
        cursor.execute("SELECT * FROM ma_archives WHERE task_id = ?", (archive_id,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        
        return None
    
    def list_archives(
        self,
        status: str = None,
        result: str = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """列出归档记录
        
        Args:
            status: 任务状态过滤
            result: 结果过滤
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            归档记录列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM ma_archives WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if result:
            query += " AND result = ?"
            params.append(result)
        
        if start_date:
            query += " AND DATE(created_at) >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND DATE(created_at) <= ?"
            params.append(end_date)
        
        query += " ORDER BY archived_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def export_archive(
        self,
        archive_id: str = None,
        task_id: str = None,
        format: str = "json",
    ) -> Dict[str, Any]:
        """导出归档记录
        
        Args:
            archive_id: 归档ID
            task_id: 任务ID（二选一）
            format: 导出格式 ("json", "markdown")
            
        Returns:
            导出结果 {"success": bool, "content": str, "format": str}
        """
        archive = None
        if archive_id:
            archive = self.get_archive(archive_id)
        elif task_id:
            archive = self.get_archive(task_id)
        
        if not archive:
            return {"success": False, "message": "归档记录不存在"}
        
        if format == "json":
            content = json.dumps(archive, ensure_ascii=False, indent=2)
            return {
                "success": True,
                "content": content,
                "format": "json",
                "archive_id": archive["archive_id"],
            }
        
        elif format == "markdown":
            md = self._format_archive_markdown(archive)
            return {
                "success": True,
                "content": md,
                "format": "markdown",
                "archive_id": archive["archive_id"],
            }
        
        else:
            return {"success": False, "message": f"不支持的导出格式: {format}"}
    
    def _format_archive_markdown(self, archive: Dict[str, Any]) -> str:
        """将归档记录格式化为Markdown
        
        Args:
            archive: 归档记录
            
        Returns:
            Markdown格式文本
        """
        md = f"""# 奏折归档 - {archive['archive_id']}

## 基本信息
- **任务ID**: {archive['task_id']}
- **标题**: {archive['title']}
- **状态**: {archive['status']}
- **结果**: {archive['result']}
- **创建时间**: {archive['created_at']}
- **完成时间**: {archive['completed_at']}
- **归档时间**: {archive['archived_at']}

## 原始消息
{archive['original_message']}

"""
        
        # 分类结果
        if archive.get('classification'):
            try:
                classification = json.loads(archive['classification']) if isinstance(archive['classification'], str) else archive['classification']
                md += f"""## 分类结果
```json
{json.dumps(classification, ensure_ascii=False, indent=2)}
```

"""
            except:
                pass
        
        # 规划方案
        if archive.get('plan'):
            try:
                plan = json.loads(archive['plan']) if isinstance(archive['plan'], str) else archive['plan']
                md += f"""## 规划方案
```json
{json.dumps(plan, ensure_ascii=False, indent=2)}
```

"""
            except:
                pass
        
        # 审议结果
        if archive.get('review_result'):
            try:
                review = json.loads(archive['review_result']) if isinstance(archive['review_result'], str) else archive['review_result']
                md += f"""## 审议结果
```json
{json.dumps(review, ensure_ascii=False, indent=2)}
```

"""
            except:
                pass
        
        # 执行结果
        if archive.get('execution_results'):
            try:
                execution = json.loads(archive['execution_results']) if isinstance(archive['execution_results'], str) else archive['execution_results']
                md += f"""## 执行结果
```json
{json.dumps(execution, ensure_ascii=False, indent=2)}
```

"""
            except:
                pass
        
        # 最终响应
        if archive.get('final_response'):
            md += f"""## 最终响应
{archive['final_response']}
"""
        
        return md
    
    def export_archives_batch(
        self,
        start_date: str = None,
        end_date: str = None,
        status: str = None,
        format: str = "json",
    ) -> Dict[str, Any]:
        """批量导出归档记录
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            status: 状态过滤
            format: 导出格式
            
        Returns:
            导出结果
        """
        archives = self.list_archives(
            status=status,
            start_date=start_date,
            end_date=end_date,
            limit=1000,
        )
        
        if not archives:
            return {"success": False, "message": "没有找到符合条件的归档记录"}
        
        if format == "json":
            content = json.dumps(archives, ensure_ascii=False, indent=2)
            return {
                "success": True,
                "content": content,
                "format": "json",
                "count": len(archives),
            }
        
        elif format == "markdown":
            parts = [f"# 奏折归档汇总\n\n共 {len(archives)} 条记录\n\n---\n"]
            for archive in archives:
                parts.append(self._format_archive_markdown(archive))
                parts.append("\n---\n")
            return {
                "success": True,
                "content": "\n".join(parts),
                "format": "markdown",
                "count": len(archives),
            }
        
        return {"success": False, "message": f"不支持的导出格式: {format}"}
    
    def delete_archive(self, archive_id: str) -> Dict[str, Any]:
        """删除归档记录
        
        Args:
            archive_id: 归档ID
            
        Returns:
            操作结果
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM ma_archives WHERE archive_id = ?", (archive_id,))
        conn.commit()
        
        if cursor.rowcount > 0:
            return {"success": True, "message": f"归档记录已删除: {archive_id}"}
        else:
            return {"success": False, "message": f"归档记录不存在: {archive_id}"}
    
    def get_archive_statistics(self) -> Dict[str, Any]:
        """获取归档统计信息
        
        Returns:
            统计信息
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 总数
        cursor.execute("SELECT COUNT(*) as count FROM ma_archives")
        total = cursor.fetchone()["count"]
        
        # 按结果统计
        cursor.execute("""
            SELECT result, COUNT(*) as count 
            FROM ma_archives 
            GROUP BY result
        """)
        by_result = {row["result"]: row["count"] for row in cursor.fetchall()}
        
        # 按状态统计
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM ma_archives 
            GROUP BY status
        """)
        by_status = {row["status"]: row["count"] for row in cursor.fetchall()}
        
        # 今日归档
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute(
            "SELECT COUNT(*) as count FROM ma_archives WHERE DATE(archived_at) = ?",
            (today,)
        )
        today_count = cursor.fetchone()["count"]
        
        return {
            "total": total,
            "by_result": by_result,
            "by_status": by_status,
            "today": today_count,
        }
    
    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

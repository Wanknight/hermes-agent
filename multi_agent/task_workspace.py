"""
任务工作空间管理模块

每个任务创建独立的工作空间目录，用于存储各环节的产出文件。
支持环节间的资源共享和文件传递。
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)


# 阶段名称映射
STAGE_NAMES = {
    "classification": "太子分类",
    "plan": "中书省规划",
    "review": "门下省审议",
    "dispatch": "尚书省派发",
    "hubu": "户部",
    "gongbu": "工部",
    "libu": "礼部",
    "bingbu": "兵部",
    "xingbu": "刑部",
    "libu_hr": "吏部",
    "zaochao": "早朝官",
}

# Agent ID 列表（六部）
AGENT_IDS = ["hubu", "gongbu", "libu", "bingbu", "xingbu", "libu_hr", "zaochao"]


@dataclass
class FileInfo:
    """文件信息"""
    path: Path
    stage: str
    agent_id: Optional[str] = None
    size: int = 0
    created_at: str = ""
    content_type: str = "text"  # text, json, binary
    
    def to_dict(self) -> Dict:
        return {
            "path": str(self.path),
            "stage": self.stage,
            "agent_id": self.agent_id,
            "size": self.size,
            "created_at": self.created_at,
            "content_type": self.content_type,
        }


class TaskWorkspace:
    """任务工作空间管理
    
    为每个任务创建独立的文件目录，管理各阶段产出。
    
    目录结构:
    ~/.hermes/tasks/{task_id}/
    ├── .task.json              # 任务元数据
    ├── classification.json     # 太子分类
    ├── plan.md                 # 中书省规划
    ├── review.json             # 门下省审议
    ├── dispatch.json           # 尚书省派发
    ├── outputs/                # 六部产出
    │   ├── hubu/
    │   ├── gongbu/
    │   └── libu/
    └── final/                  # 最终结果
        └── summary.md
    """
    
    def __init__(self, task_id: str, base_path: Path = None):
        """初始化工作空间
        
        Args:
            task_id: 任务ID
            base_path: 基础路径，默认为 ~/.hermes/tasks
        """
        self.task_id = task_id
        self.base_path = base_path or get_hermes_home() / "tasks"
        self.workspace_path = self.base_path / task_id
        self._metadata: Dict[str, Any] = {}
    
    def create(self) -> Path:
        """创建工作空间目录结构
        
        Returns:
            工作空间根路径
        """
        # 创建主目录
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        
        # 创建子目录
        (self.workspace_path / "outputs").mkdir(exist_ok=True)
        (self.workspace_path / "final").mkdir(exist_ok=True)
        
        # 为每个Agent创建输出目录
        for agent_id in AGENT_IDS:
            (self.workspace_path / "outputs" / agent_id).mkdir(exist_ok=True)
        
        logger.info(f"已创建任务工作空间: {self.workspace_path}")
        return self.workspace_path
    
    def exists(self) -> bool:
        """检查工作空间是否存在"""
        return self.workspace_path.exists()
    
    # ==================== 阶段产出保存 ====================
    
    def save_classification(self, classification: Dict[str, Any]) -> Path:
        """保存太子分类结果
        
        Args:
            classification: 分类结果字典
            
        Returns:
            保存的文件路径
        """
        filepath = self.workspace_path / "classification.json"
        filepath.write_text(json.dumps(classification, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug(f"已保存分类结果: {filepath}")
        return filepath
    
    def save_plan(self, plan: Union[Dict, str]) -> Path:
        """保存中书省规划
        
        Args:
            plan: 规划内容（JSON或Markdown）
            
        Returns:
            保存的文件路径
        """
        if isinstance(plan, dict):
            # JSON格式保存
            filepath = self.workspace_path / "plan.json"
            filepath.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            # Markdown格式保存
            filepath = self.workspace_path / "plan.md"
            filepath.write_text(str(plan), encoding="utf-8")
        
        logger.debug(f"已保存规划: {filepath}")
        return filepath
    
    def save_review(self, review: Dict[str, Any]) -> Path:
        """保存门下省审议结果
        
        Args:
            review: 审议结果
            
        Returns:
            保存的文件路径
        """
        filepath = self.workspace_path / "review.json"
        filepath.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug(f"已保存审议结果: {filepath}")
        return filepath
    
    def save_dispatch(self, dispatch: Dict[str, Any]) -> Path:
        """保存尚书省派发决策
        
        Args:
            dispatch: 派发决策
            
        Returns:
            保存的文件路径
        """
        filepath = self.workspace_path / "dispatch.json"
        filepath.write_text(json.dumps(dispatch, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug(f"已保存派发决策: {filepath}")
        return filepath
    
    # ==================== Agent 产出管理 ====================
    
    def get_output_dir(self, agent_id: str) -> Path:
        """获取指定Agent的输出目录
        
        Args:
            agent_id: Agent ID
            
        Returns:
            输出目录路径
        """
        output_dir = self.workspace_path / "outputs" / agent_id
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
    
    def save_agent_output(
        self, 
        agent_id: str, 
        filename: str, 
        content: Union[str, bytes, Dict],
    ) -> Path:
        """保存Agent产出文件
        
        Args:
            agent_id: Agent ID
            filename: 文件名
            content: 文件内容（字符串、字节或字典）
            
        Returns:
            保存的文件路径
        """
        output_dir = self.get_output_dir(agent_id)
        filepath = output_dir / filename
        
        if isinstance(content, dict):
            filepath.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        elif isinstance(content, bytes):
            filepath.write_bytes(content)
        else:
            filepath.write_text(str(content), encoding="utf-8")
        
        logger.info(f"已保存 {agent_id} 产出: {filepath}")
        return filepath
    
    def get_agent_output(self, agent_id: str, filename: str) -> Optional[str]:
        """读取Agent产出文件
        
        Args:
            agent_id: Agent ID
            filename: 文件名
            
        Returns:
            文件内容，不存在返回None
        """
        filepath = self.workspace_path / "outputs" / agent_id / filename
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        return None
    
    def get_agent_output_path(self, agent_id: str, filename: str) -> Path:
        """获取Agent产出文件的完整路径
        
        Args:
            agent_id: Agent ID
            filename: 文件名
            
        Returns:
            文件路径（不一定存在）
        """
        return self.workspace_path / "outputs" / agent_id / filename
    
    def list_agent_outputs(self, agent_id: str = None) -> List[FileInfo]:
        """列出Agent产出文件
        
        Args:
            agent_id: 可选，指定Agent ID
            
        Returns:
            文件信息列表
        """
        outputs_dir = self.workspace_path / "outputs"
        if not outputs_dir.exists():
            return []
        
        files = []
        
        if agent_id:
            # 列出指定Agent的产出
            agent_dir = outputs_dir / agent_id
            if agent_dir.exists():
                for f in agent_dir.iterdir():
                    if f.is_file() and not f.name.startswith("."):
                        files.append(FileInfo(
                            path=f,
                            stage="execution",
                            agent_id=agent_id,
                            size=f.stat().st_size,
                            created_at=datetime.fromtimestamp(f.stat().st_ctime).isoformat(),
                        ))
        else:
            # 列出所有Agent的产出
            for agent_dir in outputs_dir.iterdir():
                if agent_dir.is_dir():
                    for f in agent_dir.iterdir():
                        if f.is_file() and not f.name.startswith("."):
                            files.append(FileInfo(
                                path=f,
                                stage="execution",
                                agent_id=agent_dir.name,
                                size=f.stat().st_size,
                                created_at=datetime.fromtimestamp(f.stat().st_ctime).isoformat(),
                            ))
        
        return sorted(files, key=lambda x: x.created_at)
    
    # ==================== 最终结果 ====================
    
    def save_final(self, content: Union[str, Dict], filename: str = "summary.md") -> Path:
        """保存最终结果
        
        Args:
            content: 最终内容
            filename: 文件名
            
        Returns:
            保存的文件路径
        """
        final_dir = self.workspace_path / "final"
        final_dir.mkdir(exist_ok=True)
        
        filepath = final_dir / filename
        
        if isinstance(content, dict):
            filepath.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            filepath.write_text(str(content), encoding="utf-8")
        
        logger.info(f"已保存最终结果: {filepath}")
        return filepath
    
    # ==================== 读取阶段产出 ====================
    
    def get_classification(self) -> Optional[Dict]:
        """读取分类结果"""
        filepath = self.workspace_path / "classification.json"
        if filepath.exists():
            return json.loads(filepath.read_text(encoding="utf-8"))
        return None
    
    def get_plan(self) -> Optional[Union[Dict, str]]:
        """读取规划"""
        # 优先读取JSON格式
        json_path = self.workspace_path / "plan.json"
        if json_path.exists():
            return json.loads(json_path.read_text(encoding="utf-8"))
        
        # 其次读取Markdown格式
        md_path = self.workspace_path / "plan.md"
        if md_path.exists():
            return md_path.read_text(encoding="utf-8")
        
        return None
    
    def get_review(self) -> Optional[Dict]:
        """读取审议结果"""
        filepath = self.workspace_path / "review.json"
        if filepath.exists():
            return json.loads(filepath.read_text(encoding="utf-8"))
        return None
    
    def get_dispatch(self) -> Optional[Dict]:
        """读取派发决策"""
        filepath = self.workspace_path / "dispatch.json"
        if filepath.exists():
            return json.loads(filepath.read_text(encoding="utf-8"))
        return None
    
    # ==================== 工作空间信息 ====================
    
    def list_all_files(self) -> List[FileInfo]:
        """列出工作空间所有文件"""
        files = []
        
        if not self.workspace_path.exists():
            return files
        
        # 阶段文件
        for stage_file in ["classification.json", "plan.json", "plan.md", "review.json", "dispatch.json"]:
            filepath = self.workspace_path / stage_file
            if filepath.exists():
                files.append(FileInfo(
                    path=filepath,
                    stage=stage_file.split(".")[0],
                    size=filepath.stat().st_size,
                    created_at=datetime.fromtimestamp(filepath.stat().st_ctime).isoformat(),
                ))
        
        # Agent产出
        files.extend(self.list_agent_outputs())
        
        # 最终结果
        final_dir = self.workspace_path / "final"
        if final_dir.exists():
            for f in final_dir.iterdir():
                if f.is_file():
                    files.append(FileInfo(
                        path=f,
                        stage="final",
                        size=f.stat().st_size,
                        created_at=datetime.fromtimestamp(f.stat().st_ctime).isoformat(),
                    ))
        
        return sorted(files, key=lambda x: x.created_at)
    
    def get_workspace_info(self) -> Dict[str, Any]:
        """获取工作空间信息"""
        files = self.list_all_files()
        
        return {
            "task_id": self.task_id,
            "workspace_path": str(self.workspace_path),
            "exists": self.exists(),
            "total_files": len(files),
            "total_size": sum(f.size for f in files),
            "files": [f.to_dict() for f in files],
            "stages": {
                "classification": (self.workspace_path / "classification.json").exists(),
                "plan": (self.workspace_path / "plan.json").exists() or (self.workspace_path / "plan.md").exists(),
                "review": (self.workspace_path / "review.json").exists(),
                "dispatch": (self.workspace_path / "dispatch.json").exists(),
            },
        }
    
    def get_context_for_agent(self, agent_id: str, input_files: List[str] = None) -> Dict[str, Any]:
        """获取Agent执行上下文
        
        Args:
            agent_id: 执行任务的Agent ID
            input_files: 需要读取的上游产出文件列表（格式: "agent_id/filename"）
            
        Returns:
            包含工作空间信息的上下文字典
        """
        context = {
            "workspace_path": str(self.workspace_path),
            "output_dir": str(self.get_output_dir(agent_id)),
            "agent_id": agent_id,
        }
        
        # 添加输入文件路径
        if input_files:
            input_paths = []
            for ref in input_files:
                # ref 格式: "hubu/data.csv"
                parts = ref.split("/")
                if len(parts) == 2:
                    path = self.get_agent_output_path(parts[0], parts[1])
                    if path.exists():
                        input_paths.append(str(path))
            if input_paths:
                context["input_files"] = input_paths
        
        # 添加规划信息
        plan = self.get_plan()
        if plan:
            context["plan"] = plan
        
        return context
    
    def cleanup(self):
        """清理工作空间（谨慎使用）"""
        import shutil
        if self.workspace_path.exists():
            shutil.rmtree(self.workspace_path)
            logger.info(f"已清理工作空间: {self.workspace_path}")


# ==================== 全局函数 ====================

def get_workspace(task_id: str) -> TaskWorkspace:
    """获取任务工作空间
    
    Args:
        task_id: 任务ID
        
    Returns:
        TaskWorkspace 实例
    """
    return TaskWorkspace(task_id)


def create_workspace(task_id: str) -> TaskWorkspace:
    """创建并返回任务工作空间
    
    Args:
        task_id: 任务ID
        
    Returns:
        已创建的 TaskWorkspace 实例
    """
    workspace = TaskWorkspace(task_id)
    workspace.create()
    return workspace

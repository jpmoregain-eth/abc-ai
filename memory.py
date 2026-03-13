"""
Memory Module for ABC AI
SQLite-based persistent memory
"""

import json
import sqlite3
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class AgentMemory:
    """Manages persistent memory for ABC AI Agent"""
    
    def __init__(self, db_path: str = "agent_memory.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Conversations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Context/knowledge table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                category TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Agent actions history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                action_data TEXT NOT NULL,
                result TEXT,
                success BOOLEAN,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Session summaries table (compressed old sessions)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                summary TEXT NOT NULL,
                key_facts TEXT,
                message_count INTEGER,
                compressed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                original_start TIMESTAMP,
                original_end TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Agent memory database initialized")
    
    def store_message(self, session_id: str, role: str, content: str, metadata: Dict = None):
        """Store a conversation message"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO conversations (session_id, role, content, metadata)
            VALUES (?, ?, ?, ?)
        ''', (session_id, role, content, json.dumps(metadata) if metadata else None))
        
        conn.commit()
        conn.close()
        
        # Optional: Auto-trim only if session gets extremely large (10000+ messages)
        # This prevents database corruption from runaway sessions
        # Most conversations won't hit this limit
        self._trim_session_if_excessive(session_id, max_messages=10000)
    
    def get_conversation_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        """Get conversation history for a session"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT role, content, metadata, timestamp
            FROM conversations
            WHERE session_id = ?
            ORDER BY timestamp ASC
            LIMIT ?
        ''', (session_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'role': row[0],
                'content': row[1],
                'metadata': json.loads(row[2]) if row[2] else None,
                'timestamp': row[3]
            }
            for row in rows
        ]
    
    def store_context(self, key: str, value: Any, category: str = None):
        """Store context/knowledge"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO context (key, value, category, updated_at)
            VALUES (?, ?, ?, ?)
        ''', (key, json.dumps(value), category, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_context(self, key: str) -> Optional[Any]:
        """Get context value"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT value FROM context WHERE key = ?
        ''', (key,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return None
    
    def get_context_by_category(self, category: str) -> Dict[str, Any]:
        """Get all context in a category"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT key, value FROM context WHERE category = ?
        ''', (category,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return {row[0]: json.loads(row[1]) for row in rows}
    
    def log_action(self, action_type: str, action_data: Dict, result: str = None, success: bool = True):
        """Log an agent action"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO actions (action_type, action_data, result, success)
            VALUES (?, ?, ?, ?)
        ''', (action_type, json.dumps(action_data), result, success))
        
        conn.commit()
        conn.close()
    
    def get_recent_actions(self, action_type: str = None, limit: int = 20) -> List[Dict]:
        """Get recent actions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if action_type:
            cursor.execute('''
                SELECT action_type, action_data, result, success, timestamp
                FROM actions
                WHERE action_type = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (action_type, limit))
        else:
            cursor.execute('''
                SELECT action_type, action_data, result, success, timestamp
                FROM actions
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'action_type': row[0],
                'action_data': json.loads(row[1]),
                'result': row[2],
                'success': row[3],
                'timestamp': row[4]
            }
            for row in rows
        ]
    
    def clear_session(self, session_id: str):
        """Clear conversation history for a session"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM conversations WHERE session_id = ?
        ''', (session_id,))
        
        conn.commit()
        conn.close()
    
    def _trim_session_if_excessive(self, session_id: str, max_messages: int = 10000):
        """Only trim if session has excessive messages (safety measure)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check current count
        cursor.execute('''
            SELECT COUNT(*) FROM conversations WHERE session_id = ?
        ''', (session_id,))
        count = cursor.fetchone()[0]
        
        # Only trim if extremely excessive (prevents runaway DB growth)
        if count > max_messages:
            # Keep last 90% to preserve most context
            keep_count = int(max_messages * 0.9)
            
            cursor.execute('''
                DELETE FROM conversations
                WHERE session_id = ?
                AND id NOT IN (
                    SELECT id FROM conversations
                    WHERE session_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                )
            ''', (session_id, session_id, keep_count))
            
            deleted = cursor.rowcount
            conn.commit()
            logging.getLogger(__name__).warning(
                f"Session {session_id} had {count} messages, trimmed {deleted} old ones"
            )
        
        conn.close()
    
    def cleanup_old_sessions(self, days: int = 30):
        """Remove sessions older than N days"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM conversations
            WHERE timestamp < datetime('now', '-' || ? || ' days')
        ''', (days,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted > 0:
            logging.getLogger(__name__).info(f"Cleaned up {deleted} messages older than {days} days")
    
    def compress_session(self, session_id: str, summary: str, key_facts: List[str] = None) -> bool:
        """
        Compress a session by storing summary and deleting full conversation.
        Use this for old sessions to save space while keeping important context.
        
        Args:
            session_id: The session to compress
            summary: LLM-generated summary of the conversation
            key_facts: List of key facts to remember from the session
        
        Returns:
            True if successful
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get session metadata before deleting
            cursor.execute('''
                SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
                FROM conversations
                WHERE session_id = ?
            ''', (session_id,))
            
            row = cursor.fetchone()
            message_count = row[0]
            original_start = row[1]
            original_end = row[2]
            
            if message_count == 0:
                logger.warning(f"No messages found for session {session_id}")
                conn.close()
                return False
            
            # Store summary
            cursor.execute('''
                INSERT OR REPLACE INTO session_summaries
                (session_id, summary, key_facts, message_count, original_start, original_end)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                summary,
                json.dumps(key_facts) if key_facts else None,
                message_count,
                original_start,
                original_end
            ))
            
            # Delete full conversation (compressed now)
            cursor.execute('''
                DELETE FROM conversations WHERE session_id = ?
            ''', (session_id,))
            
            conn.commit()
            logger.info(
                f"Compressed session {session_id}: {message_count} messages -> summary "
                f"({len(summary)} chars, {len(key_facts) if key_facts else 0} key facts)"
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to compress session {session_id}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_session_summary(self, session_id: str) -> Optional[Dict]:
        """Get compressed summary of a session"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT summary, key_facts, message_count, compressed_at, 
                   original_start, original_end
            FROM session_summaries
            WHERE session_id = ?
        ''', (session_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'session_id': session_id,
                'summary': row[0],
                'key_facts': json.loads(row[1]) if row[1] else [],
                'message_count': row[2],
                'compressed_at': row[3],
                'original_start': row[4],
                'original_end': row[5]
            }
        return None
    
    def get_all_summaries(self, limit: int = 100) -> List[Dict]:
        """Get all compressed session summaries"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT session_id, summary, key_facts, message_count, 
                   compressed_at, original_start, original_end
            FROM session_summaries
            ORDER BY compressed_at DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'session_id': row[0],
                'summary': row[1],
                'key_facts': json.loads(row[2]) if row[2] else [],
                'message_count': row[3],
                'compressed_at': row[4],
                'original_start': row[5],
                'original_end': row[6]
            }
            for row in rows
        ]
    
    def compress_old_sessions(self, days: int = 30, llm_summarizer = None) -> int:
        """
        Compress sessions older than N days.
        
        Args:
            days: Compress sessions older than this many days
            llm_summarizer: Optional function to generate summaries 
                           (if None, uses simple "Session from [date]" summary)
        
        Returns:
            Number of sessions compressed
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Find old sessions
        cursor.execute('''
            SELECT DISTINCT session_id, COUNT(*)
            FROM conversations
            WHERE timestamp < datetime('now', '-' || ? || ' days')
            GROUP BY session_id
        ''', (days,))
        
        old_sessions = cursor.fetchall()
        conn.close()
        
        compressed_count = 0
        
        for session_id, message_count in old_sessions:
            # Get conversation for summarization
            history = self.get_conversation_history(session_id, limit=1000)
            
            if llm_summarizer:
                # Use LLM to generate summary
                try:
                    conversation_text = "\n".join([
                        f"{msg['role']}: {msg['content'][:200]}" 
                        for msg in history[:50]  # First 50 messages for summary
                    ])
                    summary = llm_summarizer(f"Summarize this conversation:\n{conversation_text}")
                except Exception as e:
                    logger.warning(f"LLM summarization failed for {session_id}: {e}")
                    summary = f"Session from {history[0]['timestamp'] if history else 'unknown'}"
            else:
                # Simple summary without LLM
                summary = f"Session with {message_count} messages"
            
            # Extract key facts (simplified - could be enhanced with LLM)
            key_facts = []
            for msg in history:
                content = msg.get('content', '')
                # Look for statements with "I am", "My name is", etc.
                if 'my name is' in content.lower() or 'i am' in content.lower():
                    key_facts.append(content[:100])
                if len(key_facts) >= 5:  # Limit key facts
                    break
            
            # Compress the session
            if self.compress_session(session_id, summary, key_facts):
                compressed_count += 1
        
        if compressed_count > 0:
            logger.info(f"Compressed {compressed_count} old sessions")
        
        return compressed_count
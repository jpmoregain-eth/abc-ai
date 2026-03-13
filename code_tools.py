"""
Code Operations Tools for ABC AI Agent
Provides code generation, review, debugging, and documentation capabilities
All powered by the LLM - no external APIs required
"""

import re
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class CodeTools:
    """Code operation tools powered by LLM"""
    
    def __init__(self, agent_chat_func):
        """
        Initialize code tools
        
        Args:
            agent_chat_func: Function to call LLM chat
        """
        self.chat = agent_chat_func
        logger.info("📝 Code tools initialized")
    
    def generate_code(self, description: str, language: str = "python", context: str = "") -> Dict:
        """
        Generate code from natural language description
        
        Args:
            description: What the code should do
            language: Programming language (default: python)
            context: Additional context or constraints
            
        Returns:
            Dict with generated code and explanation
        """
        prompt = f"""Generate {language} code for the following task:

**Task Description:**
{description}

**Requirements:**
- Write clean, well-commented code
- Include error handling where appropriate
- Follow best practices for {language}
- Add a brief docstring explaining the function
{f"- Additional context: {context}" if context else ""}

Please provide:
1. The code in a code block
2. A brief explanation of how it works
3. Example usage

Format your response with the code first, then the explanation."""

        try:
            result = self.chat(prompt, session_id="code_gen_session")
            return {
                "success": True,
                "code": result.get('response', ''),
                "language": language,
                "task": description
            }
        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def review_code(self, code: str, language: str = "python", focus_areas: list = None) -> Dict:
        """
        Review code for issues, improvements, and best practices
        
        Args:
            code: The code to review
            language: Programming language
            focus_areas: Specific areas to focus on (e.g., ["security", "performance"])
            
        Returns:
            Dict with review results
        """
        focus = ", ".join(focus_areas) if focus_areas else "general code quality, bugs, security, and performance"
        
        prompt = f"""Review the following {language} code:

**Code to Review:**
```{language}
{code}
```

**Focus Areas:** {focus}

Please provide a comprehensive code review including:
1. **Summary** - Overall assessment
2. **Issues Found** - Bugs, security risks, performance problems
3. **Suggestions** - Specific improvements with code examples
4. **Best Practices** - What's done well and what could be better
5. **Rating** - Give an overall rating (Excellent/Good/Needs Work/Poor)

Be constructive and specific in your feedback."""

        try:
            result = self.chat(prompt, session_id="code_review_session")
            return {
                "success": True,
                "review": result.get('response', ''),
                "language": language,
                "focus_areas": focus_areas or ["general"]
            }
        except Exception as e:
            logger.error(f"Code review failed: {e}")
            return {"success": False, "error": str(e)}
    
    def debug_code(self, code: str = "", error_message: str = "", language: str = "python") -> Dict:
        """
        Debug code based on error message or code analysis
        
        Args:
            code: The code with issues (optional)
            error_message: The error message (optional)
            language: Programming language
            
        Returns:
            Dict with debugging results and fixed code
        """
        if not code and not error_message:
            return {"success": False, "error": "Please provide either code or an error message to debug"}
        
        context_parts = []
        if error_message:
            context_parts.append(f"**Error Message:**\n```\n{error_message}\n```")
        if code:
            context_parts.append(f"**Code:**\n```{language}\n{code}\n```")
        
        context = "\n\n".join(context_parts)
        
        prompt = f"""Debug the following {language} issue:

{context}

**Task:**
1. Analyze the error or code to identify the root cause
2. Explain what's going wrong
3. Provide the fixed code
4. Explain how to prevent this issue in the future

Please format your response with:
- **Problem Analysis:** What's causing the issue
- **Root Cause:** Why it's happening
- **Fixed Code:** The corrected code in a code block
- **Prevention:** Tips to avoid this in the future"""

        try:
            result = self.chat(prompt, session_id="debug_session")
            return {
                "success": True,
                "analysis": result.get('response', ''),
                "language": language,
                "has_code": bool(code),
                "has_error": bool(error_message)
            }
        except Exception as e:
            logger.error(f"Debug failed: {e}")
            return {"success": False, "error": str(e)}
    
    def generate_documentation(self, code: str, language: str = "python", style: str = "google") -> Dict:
        """
        Generate documentation (docstrings, comments) for code
        
        Args:
            code: The code to document
            language: Programming language
            style: Documentation style (google, numpy, sphinx)
            
        Returns:
            Dict with documented code
        """
        prompt = f"""Add comprehensive documentation to the following {language} code using {style} style:

**Original Code:**
```{language}
{code}
```

**Requirements:**
1. Add docstrings to all functions/classes following {style} format
2. Add inline comments for complex logic
3. Include type hints if appropriate for {language}
4. Add module-level docstring if missing
5. Ensure the code is self-documenting

Please provide:
1. The fully documented code in a code block
2. A summary of what was added/changed
3. Any recommendations for further documentation improvements"""

        try:
            result = self.chat(prompt, session_id="doc_session")
            return {
                "success": True,
                "documented_code": result.get('response', ''),
                "language": language,
                "style": style
            }
        except Exception as e:
            logger.error(f"Documentation generation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def detect_and_execute(self, message: str) -> Optional[Dict]:
        """
        Detect code-related commands and execute them
        
        Args:
            message: User message
            
        Returns:
            Result dict if a code command was executed, None otherwise
        """
        msg_lower = message.lower().strip()
        
        # Code generation patterns
        gen_patterns = [
            r'(?:generate|create|write)\s+(?:a\s+)?(.+?)\s+(?:function|code|script|program)',
            r'(?:generate|create|write)\s+(?:code\s+)?(?:for|to)\s+(.+)',
            r'(?:how\s+to|show\s+me\s+how\s+to)\s+(.+)\s+in\s+(python|javascript|java|go|ruby)',
        ]
        
        for pattern in gen_patterns:
            match = re.search(pattern, msg_lower)
            if match:
                description = match.group(1)
                # Try to extract language
                lang_match = re.search(r'\b(python|javascript|js|java|go|golang|ruby|php|c\+\+|cpp|c#|csharp|rust|typescript|ts)\b', msg_lower)
                language = lang_match.group(1) if lang_match else "python"
                # Normalize language names
                lang_map = {"js": "javascript", "golang": "go", "cpp": "c++", "csharp": "c#", "ts": "typescript"}
                language = lang_map.get(language, language)
                return self.generate_code(description, language)
        
        # Code review patterns
        review_patterns = [
            r'(?:review|check|analyze)\s+(?:this\s+)?code',
            r'(?:what\s+do\s+you\s+think\s+of|how\s+is)\s+(?:this\s+)?code',
            r'(?:code\s+)?review:',
        ]
        
        for pattern in review_patterns:
            if re.search(pattern, msg_lower):
                # Extract code from message (look for code blocks)
                code_match = re.search(r'```(\w+)?\n(.*?)```', message, re.DOTALL)
                if code_match:
                    language = code_match.group(1) or "python"
                    code = code_match.group(2).strip()
                    return self.review_code(code, language)
                else:
                    # Look for code without code blocks
                    lines = message.split('\n')
                    code_lines = []
                    for line in lines:
                        if not line.lower().startswith(('review', 'check', 'analyze', 'what', 'how')):
                            code_lines.append(line)
                    if code_lines:
                        code = '\n'.join(code_lines).strip()
                        if len(code) > 20:  # Only if there's substantial code
                            return self.review_code(code, "python")
        
        # Debug patterns
        debug_patterns = [
            r'(?:debug|fix|solve)\s+(?:this\s+)?(?:error|issue|problem|bug)',
            r'(?:what\s+is\s+wrong\s+with|why\s+does)\s+(?:this\s+)?(?:code|error)',
            r'(?:help\s+me\s+debug|debug\s+help)',
        ]
        
        for pattern in debug_patterns:
            if re.search(pattern, msg_lower):
                # Extract error message
                error_match = re.search(r'(?:error|exception|traceback):?\s*(.+?)(?=\n\n|$)', message, re.DOTALL | re.IGNORECASE)
                error_message = error_match.group(1).strip() if error_match else ""
                
                # Extract code
                code_match = re.search(r'```(\w+)?\n(.*?)```', message, re.DOTALL)
                code = code_match.group(2).strip() if code_match else ""
                
                if code or error_message:
                    language = code_match.group(1) if code_match else "python"
                    return self.debug_code(code, error_message, language)
        
        # Documentation patterns
        doc_patterns = [
            r'(?:add|generate|write)\s+(?:documentation|docstring|comments?)',
            r'(?:document\s+this\s+code|code\s+documentation)',
        ]
        
        for pattern in doc_patterns:
            if re.search(pattern, msg_lower):
                code_match = re.search(r'```(\w+)?\n(.*?)```', message, re.DOTALL)
                if code_match:
                    language = code_match.group(1) or "python"
                    code = code_match.group(2).strip()
                    return self.generate_documentation(code, language)
        
        return None


# For testing
if __name__ == "__main__":
    # Mock chat function for testing
    def mock_chat(prompt, session_id=None):
        return {"response": f"[Mock LLM Response]\n\nGenerated code for: {prompt[:50]}..."}
    
    tools = CodeTools(mock_chat)
    
    print("Testing code generation...")
    result = tools.generate_code("function to reverse a string", "python")
    print(f"Success: {result['success']}")
    
    print("\nTesting code review...")
    result = tools.review_code("def test(): pass", "python")
    print(f"Success: {result['success']}")
    
    print("\nTesting debug...")
    result = tools.debug_code(code="def test(): return 1/0", error_message="ZeroDivisionError")
    print(f"Success: {result['success']}")
    
    print("\nTesting documentation...")
    result = tools.generate_documentation("def add(a, b): return a + b", "python")
    print(f"Success: {result['success']}")
    
    print("\n✅ All code tool tests passed!")

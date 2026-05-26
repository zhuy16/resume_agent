"""
LLM client wrapper for Anthropic Claude API with tracing and retry logic.
"""

from typing import Dict, Any, List, Optional
import anthropic

import config


class LLMClient:
    """Wrapper for Anthropic Claude API with structured output support."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize LLM client.
        
        Args:
            api_key: Anthropic API key (defaults to config.ANTHROPIC_API_KEY)
            model: Model name (defaults to config.CLAUDE_MODEL)
        """
        self._client = anthropic.Anthropic(api_key=api_key or config.ANTHROPIC_API_KEY)
        self._model = model or getattr(config, 'CLAUDE_MODEL', 'claude-3-5-sonnet-20241022')
    
    def generate_structured(
        self,
        system: str,
        user: str,
        tool: Dict[str, Any],
        tool_name: str,
        max_retries: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Generate structured output using Claude tool-use.
        
        Args:
            system: System prompt
            user: User message
            tool: Tool schema definition
            tool_name: Name of the tool to call
            max_retries: Maximum retry attempts
            
        Returns:
            List of paragraph dicts from tool output
            
        Raises:
            RuntimeError: If generation fails after retries
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=4096,
                    temperature=0.2,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                    tools=[tool],
                    tool_choice={"type": "tool", "name": tool_name},
                )
                
                # Extract tool use from response
                for block in response.content:
                    if block.type == "tool_use":
                        result = block.input
                        # Handle both dict and list returns
                        if isinstance(result, dict) and "paragraphs" in result:
                            return result["paragraphs"]
                        elif isinstance(result, list):
                            return result
                        else:
                            raise ValueError(f"Unexpected response format: {type(result)}")
                
                raise ValueError("No tool_use block found in response")
                
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    print(f"  [llm] Retry {attempt + 1}/{max_retries} after error: {str(e)[:50]}...")
                    continue
        
        raise RuntimeError(f"Failed after {max_retries + 1} attempts: {last_error}")
    
    def generate_text(
        self,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str:
        """
        Generate plain text response.
        
        Args:
            system: System prompt
            user: User message
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Generated text response
        """
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        
        return " ".join(block.text for block in response.content if block.type == "text")


class TracedLLMClient(LLMClient):
    """LLM client with execution tracing for debugging and evaluation."""
    
    def __init__(self, *args, trace_dir: Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._traces = []
        self._trace_dir = trace_dir
    
    def generate_structured(self, system: str, user: str, tool: Dict[str, Any], tool_name: str, **kwargs) -> List[Dict[str, Any]]:
        """Generate with trace logging."""
        import time
        import uuid
        
        trace_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        trace = {
            "trace_id": trace_id,
            "timestamp": start_time,
            "operation": "generate_structured",
            "tool_name": tool_name,
            "system_preview": system[:200],
            "user_preview": user[:200],
        }
        
        try:
            result = super().generate_structured(system, user, tool, tool_name, **kwargs)
            trace["status"] = "success"
            trace["result_count"] = len(result)
            trace["duration_ms"] = (time.time() - start_time) * 1000
        except Exception as e:
            trace["status"] = "error"
            trace["error"] = str(e)
            trace["duration_ms"] = (time.time() - start_time) * 1000
            raise
        finally:
            self._traces.append(trace)
            if self._trace_dir:
                self._save_trace(trace_id, trace)
        
        return result
    
    def _save_trace(self, trace_id: str, trace: Dict[str, Any]):
        """Save trace to disk."""
        import json
        import os
        from datetime import datetime
        
        if not os.path.exists(self._trace_dir):
            os.makedirs(self._trace_dir)
        
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{trace_id}.json"
        filepath = os.path.join(self._trace_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(trace, f, indent=2)
    
    def get_traces(self) -> List[Dict[str, Any]]:
        """Get all recorded traces."""
        return self._traces.copy()

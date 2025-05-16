# backend/token_tracer.py
import logging
from typing import Any, List, Dict, Optional, Union
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult, ChatGeneration, Generation
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)

class TokenUsageCallbackHandler(BaseCallbackHandler):
    """
    A callback handler to track token usage and execution steps in LangChain.
    Handles potential NoneType for serialized objects in chain/tool/agent events.
    """
    def __init__(self) -> None:
        super().__init__()
        self.total_tokens_used: int = 0
        self.prompt_tokens_used: int = 0
        self.completion_tokens_used: int = 0
        self.successful_llm_requests: int = 0
        self.llm_errors: int = 0
        self.steps: List[Dict[str, Any]] = []
        self._current_chain_ids: List[UUID] = [] 

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Run when LLM starts running."""
        llm_type = serialized.get("id", ["<unknown_llm>"])[-1] if serialized and serialized.get("id") else "<unknown_llm>"
        logger.info(f"LLM Start (Run ID: {run_id}, Type: {llm_type})")
        self.steps.append({
            "type": "llm_start",
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "llm_type": llm_type,
        })

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run when LLM ends running."""
        self.successful_llm_requests += 1
        step_total_tokens = 0
        step_prompt_tokens = 0
        step_completion_tokens = 0
        token_info_source = "unknown"

        for gen_list in response.generations:
            for gen in gen_list:
                if isinstance(gen, ChatGeneration) and hasattr(gen, 'message'):
                    message = gen.message
                    if isinstance(message, AIMessage) and hasattr(message, 'usage_metadata') and message.usage_metadata:
                        metadata = message.usage_metadata
                        prompt_tokens = metadata.get('input_tokens', 0)
                        completion_tokens = metadata.get('output_tokens', 0)
                        total_tokens = metadata.get('total_tokens', 0)

                        if total_tokens == 0 and (prompt_tokens > 0 or completion_tokens > 0):
                            total_tokens = prompt_tokens + completion_tokens
                        
                        if total_tokens > 0:
                            step_prompt_tokens += prompt_tokens
                            step_completion_tokens += completion_tokens
                            step_total_tokens += total_tokens
                            token_info_source = "AIMessage.usage_metadata"
        
        if step_total_tokens == 0 and response.llm_output and 'token_usage' in response.llm_output:
            token_usage_data = response.llm_output['token_usage']
            if isinstance(token_usage_data, dict):
                step_prompt_tokens = token_usage_data.get('prompt_tokens', 0)
                step_completion_tokens = token_usage_data.get('completion_tokens', 0)
                step_total_tokens = token_usage_data.get('total_tokens', step_prompt_tokens + step_completion_tokens)
                if step_total_tokens > 0:
                    token_info_source = "llm_output.token_usage"
            elif isinstance(token_usage_data, (int, float)) and int(token_usage_data) > 0: 
                step_total_tokens = int(token_usage_data)
                token_info_source = "llm_output.token_usage (total only)"


        if step_total_tokens > 0:
            self.prompt_tokens_used += step_prompt_tokens
            self.completion_tokens_used += step_completion_tokens
            self.total_tokens_used += step_total_tokens
            log_msg = (
                f"LLM End (Run ID: {run_id}). Tokens this step: Total={step_total_tokens} "
                f"(P={step_prompt_tokens}, C={step_completion_tokens}). Source: {token_info_source}."
            )
            logger.info(log_msg)
        else:
            warning_msg = f"LLM End (Run ID: {run_id}). Could not extract token usage for this LLM step. "
            if response.generations and isinstance(response.generations[0][0], ChatGeneration) and \
               hasattr(response.generations[0][0].message, 'usage_metadata') and \
               not response.generations[0][0].message.usage_metadata:
                warning_msg += "AIMessage.usage_metadata was present but empty. "
            elif response.llm_output and 'token_usage' in response.llm_output and not response.llm_output['token_usage']:
                 warning_msg += "llm_output.token_usage was present but empty. "
            warning_msg += "Token counts may be incomplete. Check LLM provider's response structure."
            logger.info(warning_msg)


        logger.info(
            f"Cumulative tokens after LLM call (Run ID: {run_id}): Total={self.total_tokens_used} "
            f"(Prompt={self.prompt_tokens_used}, Completion={self.completion_tokens_used})"
        )

        self.steps.append({
            "type": "llm_end",
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "tokens_used_this_step": step_total_tokens,
            "prompt_tokens_this_step": step_prompt_tokens,
            "completion_tokens_this_step": step_completion_tokens,
            "cumulative_total_tokens": self.total_tokens_used,
            "cumulative_prompt_tokens": self.prompt_tokens_used,
            "cumulative_completion_tokens": self.completion_tokens_used,
            "token_info_source": token_info_source,
        })

    def on_llm_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        self.llm_errors += 1
        logger.error(f"LLM Error (Run ID: {run_id}): {error}", exc_info=True)
        self.steps.append({
            "type": "llm_error",
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "error": str(error)
        })

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        self._current_chain_ids.append(run_id)
        if serialized is None:
            logger.info(f"Chain Start (Run ID: {run_id}): Received None for 'serialized' object. Cannot determine chain name.")
            chain_name = "<unknown_chain_type_due_to_none_serialized>"
        else:
            chain_name_parts = serialized.get("id", ["<unknown_chain>"])
            chain_name = chain_name_parts[-1] if chain_name_parts else "<unknown_chain>"
        
        logger.info(f"Chain Start (Run ID: {run_id}, Name: {chain_name}).")
        self.steps.append({
            "type": "chain_start",
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "name": chain_name,
        })

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        if self._current_chain_ids and self._current_chain_ids[-1] == run_id:
            self._current_chain_ids.pop()
        
        chain_name = "<unknown_chain_ended>"
        for step in reversed(self.steps): 
            if step.get("run_id") == str(run_id) and step.get("type") == "chain_start":
                chain_name = step.get("name", chain_name)
                break
        
        logger.info(f"Chain End (Run ID: {run_id}, Name: {chain_name}).") 
        self.steps.append({
            "type": "chain_end",
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "name": chain_name,
        })

    def on_chain_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        if self._current_chain_ids and self._current_chain_ids[-1] == run_id:
            self._current_chain_ids.pop()
        logger.error(f"Chain Error (Run ID: {run_id}): {error}", exc_info=True)
        self.steps.append({
            "type": "chain_error",
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "error": str(error)
        })

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        if serialized is None:
            logger.warning(f"Tool Start (Run ID: {run_id}): Received None for 'serialized' object. Cannot determine tool name.")
            tool_name = "<unknown_tool_type_due_to_none_serialized>"
        else:
            tool_name = serialized.get("name", serialized.get("id", ["<unknown_tool>"])[-1])
            
        logger.info(f"Tool Start (Run ID: {run_id}, Name: {tool_name}). Input: '{input_str}'")
        self.steps.append({
            "type": "tool_start",
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "name": tool_name,
            "input_str": input_str
        })

    def on_tool_end(
        self,
        output: str, 
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        tool_name = "<unknown_tool_ended>"
        for step in reversed(self.steps):
            if step.get("run_id") == str(run_id) and step.get("type") == "tool_start":
                tool_name = step.get("name", tool_name)
                break
        logger.info(f"Tool End (Run ID: {run_id}, Name: {tool_name}). Output length: {len(output)}")
        self.steps.append({
            "type": "tool_end",
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "name": tool_name, 
        })

    def on_tool_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        tool_name = "<unknown_tool_errored>"
        for step in reversed(self.steps):
            if step.get("run_id") == str(run_id) and step.get("type") == "tool_start":
                tool_name = step.get("name", tool_name)
                break
        logger.error(f"Tool Error (Run ID: {run_id}, Name: {tool_name}): {error}", exc_info=True)
        self.steps.append({
            "type": "tool_error",
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "name": tool_name, 
            "error": str(error)
        })
    
    def on_agent_action(
        self,
        action: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        tool_log = action.log.strip().replace('\n', ' ')
        logger.info(f"Agent Action (Run ID: {run_id}): Tool: {action.tool}, Input: '{action.tool_input}', Log: '{tool_log}'")
        self.steps.append({
            "type": "agent_action",
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "tool": action.tool,
            "tool_input": action.tool_input,
            "log": action.log 
        })

    def on_agent_finish(
        self,
        finish: Any, 
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        logger.info(f"Agent Finish (Run ID: {run_id}). Return values: {finish.return_values}")
        self.steps.append({
            "type": "agent_finish",
            "run_id": str(run_id),
            "parent_run_id": str(parent_run_id) if parent_run_id else None,
            "return_values": finish.return_values
        })

    def get_report(self) -> Dict[str, Any]:
        return {
            "total_tokens_used": self.total_tokens_used,
            "prompt_tokens_used": self.prompt_tokens_used,
            "completion_tokens_used": self.completion_tokens_used,
            "successful_llm_requests": self.successful_llm_requests,
            "llm_errors": self.llm_errors,
            "detailed_steps": self.steps 
        }

    def reset(self) -> None:
        self.total_tokens_used = 0
        self.prompt_tokens_used = 0
        self.completion_tokens_used = 0
        self.successful_llm_requests = 0
        self.llm_errors = 0
        self.steps = []
        self._current_chain_ids = []
        logger.info("TokenUsageCallbackHandler has been reset.")


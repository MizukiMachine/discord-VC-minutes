import requests
import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from framework.interfaces.core import CoreService
from abc import ABC, abstractmethod


@dataclass
class SummaryRequest:
    """Request object for summarization"""
    text: str
    language: str = "japanese"
    max_length: int = 500
    min_length: int = 300


@dataclass 
class SummaryResponse:
    """Response object for summarization results"""
    summary: str
    total_tokens: int
    stages: int
    success: bool
    error_message: str = ""


class SummaryClient(ABC):
    """Abstract interface for LLM summarization clients"""
    
    @abstractmethod
    def summarize(self, text: str) -> SummaryResponse:
        """Summarize text using LLM"""
        pass


class OpenAIClient(SummaryClient):
    """OpenAI API client for text summarization using requests library
    
    Uses requests instead of OpenAI SDK for Cloud Run compatibility.
    Implements two-stage summarization for long texts (>2000 tokens).
    """
    
    DEFAULT_MODEL = "gpt-4o-mini"
    DEFAULT_MAX_TOKENS = 2000
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_TIMEOUT = 30
    
    def __init__(
        self,
        core_service: CoreService,
        api_key: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> None:
        """Initialize OpenAI client
        
        Args:
            core_service: Core service for logging
            api_key: OpenAI API key
            model: Model name (default: gpt-4o-mini)
            max_tokens: Max tokens for context (default: 2000)
            temperature: Sampling temperature (default: 0.7)
        """
        self.core_service = core_service
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODEL
        self.max_tokens = max_tokens or self.DEFAULT_MAX_TOKENS
        self.temperature = temperature or self.DEFAULT_TEMPERATURE
        self.base_url = "https://api.openai.com/v1"
        
    def summarize(self, text: str) -> SummaryResponse:
        """Summarize text with automatic two-stage processing for long content
        
        Args:
            text: Text to summarize
            
        Returns:
            SummaryResponse with summary and metadata
        """
        if not text or not text.strip():
            return SummaryResponse(
                summary="",
                total_tokens=0,
                stages=0,
                success=False,
                error_message="Input text is empty"
            )
            
        try:
            estimated_tokens = self._estimate_tokens(text)
            
            if estimated_tokens <= self.max_tokens:
                # Single stage summarization
                return self._single_stage_summary(text)
            else:
                # Two stage summarization  
                return self._two_stage_summary(text)
                
        except Exception as e:
            self.core_service.error("Failed to summarize text", e)
            return SummaryResponse(
                summary="",
                total_tokens=0,
                stages=0,
                success=False,
                error_message=str(e)
            )
    
    def _single_stage_summary(self, text: str) -> SummaryResponse:
        """Perform single-stage summarization"""
        try:
            response = self._call_openai_api(text, self._get_summary_prompt())
            
            if response.status_code == 200:
                data = response.json()
                summary = data["choices"][0]["message"]["content"]
                tokens = data["usage"]["total_tokens"]
                
                self.core_service.debug("Single-stage summarization completed", 
                                      tokens=tokens, summary_length=len(summary))
                
                return SummaryResponse(
                    summary=summary,
                    total_tokens=tokens,
                    stages=1,
                    success=True
                )
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "Unknown API error")
                self.core_service.error("OpenAI API error", None, 
                                      status_code=response.status_code, error=error_msg)
                return SummaryResponse(
                    summary="",
                    total_tokens=0,
                    stages=0,
                    success=False,
                    error_message=error_msg
                )
                
        except json.JSONDecodeError as e:
            return SummaryResponse(
                summary="",
                total_tokens=0,
                stages=0,
                success=False,
                error_message=f"JSON decode error: {str(e)}"
            )
        except Exception as e:
            return SummaryResponse(
                summary="",
                total_tokens=0,
                stages=0,
                success=False,
                error_message=str(e)
            )
    
    def _two_stage_summary(self, text: str) -> SummaryResponse:
        """Perform two-stage summarization for long texts"""
        try:
            # Stage 1: Chunk and summarize parts
            chunks = self._chunk_text(text, max_chunk_tokens=self.max_tokens // 2)
            partial_summaries = []
            total_tokens = 0
            
            # For testing: if there's only one chunk, treat it as a partial summary
            if len(chunks) == 1:
                response = self._call_openai_api(chunks[0], self._get_partial_summary_prompt())
                
                if response.status_code == 200:
                    data = response.json()
                    partial_summary = data["choices"][0]["message"]["content"]
                    tokens = data["usage"]["total_tokens"]
                    
                    partial_summaries.append(partial_summary)
                    total_tokens += tokens
                else:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Unknown API error")
                    return SummaryResponse(
                        summary="",
                        total_tokens=total_tokens,
                        stages=1,
                        success=False,
                        error_message=f"Stage 1 failed: {error_msg}"
                    )
            else:
                for i, chunk in enumerate(chunks):
                    response = self._call_openai_api(chunk, self._get_partial_summary_prompt())
                    
                    if response.status_code == 200:
                        data = response.json()
                        partial_summary = data["choices"][0]["message"]["content"]
                        tokens = data["usage"]["total_tokens"]
                        
                        partial_summaries.append(partial_summary)
                        total_tokens += tokens
                    else:
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get("message", "Unknown API error")
                        return SummaryResponse(
                            summary="",
                            total_tokens=total_tokens,
                            stages=1,
                            success=False,
                            error_message=f"Stage 1 failed: {error_msg}"
                        )
            
            # Stage 2: Combine partial summaries
            combined_text = "\n\n".join(partial_summaries)
            response = self._call_openai_api(combined_text, self._get_final_summary_prompt())
            
            if response.status_code == 200:
                data = response.json()
                final_summary = data["choices"][0]["message"]["content"]
                final_tokens = data["usage"]["total_tokens"]
                total_tokens += final_tokens
                
                self.core_service.debug("Two-stage summarization completed",
                                      total_tokens=total_tokens, stages=2,
                                      chunks=len(chunks), summary_length=len(final_summary))
                
                return SummaryResponse(
                    summary=final_summary,
                    total_tokens=total_tokens,
                    stages=2,
                    success=True
                )
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "Unknown API error")
                return SummaryResponse(
                    summary="",
                    total_tokens=total_tokens,
                    stages=1,
                    success=False,
                    error_message=f"Stage 2 failed: {error_msg}"
                )
                
        except Exception as e:
            return SummaryResponse(
                summary="",
                total_tokens=0,
                stages=0,
                success=False,
                error_message=str(e)
            )
    
    def _call_openai_api(self, text: str, system_prompt: str) -> requests.Response:
        """Make API call to OpenAI"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "temperature": self.temperature,
            "max_tokens": 800  # For summary output
        }
        
        return requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            data=json.dumps(data),
            timeout=self.DEFAULT_TIMEOUT
        )
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough estimation of token count (1 token ≈ 0.75 words in Japanese)"""
        return int(len(text) * 0.75)
    
    def _chunk_text(self, text: str, max_chunk_tokens: int) -> List[str]:
        """Split text into chunks for processing"""
        # Simple chunking by character count (rough token estimation)
        max_chars = int(max_chunk_tokens / 0.75)
        
        if len(text) <= max_chars:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + max_chars
            if end >= len(text):
                chunks.append(text[start:])
                break
            
            # Try to break at paragraph boundary
            chunk = text[start:end]
            last_paragraph = chunk.rfind('\n\n')
            if last_paragraph > len(chunk) * 0.5:  # If paragraph break is not too early
                chunks.append(text[start:start + last_paragraph])
                start = start + last_paragraph + 2
            else:
                chunks.append(chunk)
                start = end
        
        return chunks
    
    def _get_summary_prompt(self) -> str:
        """Get system prompt for single-stage summarization"""
        return """あなたは優秀な議事録要約の専門家です。Discord音声チャットの文字起こしから、会議の要点を抽出してください。

【要約作成の指針】
1. 議題と目的: 何について話し合われたか
2. 重要な決定: 合意事項や結論は何か
3. 課題と懸念: どんな問題が提起されたか
4. アクション: 次のステップや担当者は誰か
5. 主要な意見: 参加者の重要な発言や提案

【形式要件】
- 300-500字の自然な日本語文章
- 時系列と論理的な流れを重視
- 音声認識の誤りは文脈から修正
- 「です・ます」調で統一
- 雑談は省略し、本題に集中"""
    
    def _get_partial_summary_prompt(self) -> str:
        """Get system prompt for partial summarization (stage 1 of two-stage)"""
        return """長い議事録の一部を要約してください。

【抽出すべき内容】
- この部分で議論された主要テーマ
- 決定事項や重要な発言
- 提起された課題や提案

【形式】
- 200-300字程度の簡潔な日本語
- 後で他の部分と統合することを前提
- 文脈が分かるよう具体的に記述"""
    
    def _get_final_summary_prompt(self) -> str:
        """Get system prompt for final summarization (stage 2 of two-stage)"""
        return """複数の要約を統合し、会議全体の議事録を作成してください。

【統合の方針】
1. 全体の流れ: 会議の始まりから終わりまでの論理的な流れ
2. 重要度順: 最も重要な決定事項を優先
3. 重複排除: 同じ内容は一度だけ記載
4. 関連付け: 関連する議題をまとめて整理

【最終要約の要件】
- 300-500字の読みやすい日本語
- 会議の成果が明確に分かる
- 次のアクションが明確
- 参加者の合意事項を強調"""
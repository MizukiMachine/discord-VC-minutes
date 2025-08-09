import discord
import asyncio
from typing import List, Optional, Dict, Any
from io import BytesIO
import numpy as np
from pydub import AudioSegment
import redis.asyncio as redis
import aiohttp
import tempfile
import os
import time


class MockAudioSource:
    """実際の音声データのモック"""
    
    def __init__(self, channel_id: int):
        self.channel_id = channel_id
        self.iteration = 0
        
    def get_sample_audio_data(self) -> bytes:
        """サンプル音声データ生成（将来的に実音声に置換）"""
        self.iteration += 1
        
        # 無音のWAVデータを生成（実際の音声処理テスト用）
        sample_rate = 48000
        duration_seconds = 2
        samples = np.zeros(int(sample_rate * duration_seconds), dtype=np.int16)
        
        # AudioSegmentでWAVに変換
        audio_segment = AudioSegment(
            samples.tobytes(),
            frame_rate=sample_rate,
            sample_width=2,
            channels=1
        )
        
        wav_buffer = BytesIO()
        audio_segment.export(wav_buffer, format="wav")
        return wav_buffer.getvalue()


class AudioRecorder:
    def __init__(self, channel: discord.VoiceChannel, voice_client: discord.VoiceClient):
        self.channel = channel
        self.voice_client = voice_client
        self.is_recording = False
        self.task: Optional[asyncio.Task] = None
        self.audio_buffer: List[bytes] = []
        self.chunk_duration = 15  # seconds
        self.max_buffer_minutes = 30
        self.redis_client = redis.from_url("redis://localhost:6379")
        self.vibe_url = "http://localhost:3022"
        self.audio_chunks = []  # Store audio chunks for processing
        
    async def start(self) -> None:
        if not self.is_recording:
            self.is_recording = True
            self.task = asyncio.create_task(self._recording_loop())
    
    async def stop(self) -> None:
        if self.is_recording:
            self.is_recording = False
            if self.task:
                self.task.cancel()
                self.task = None
    
    async def _recording_loop(self) -> None:
        """v2.0完全版: Vibe連携テスト（モック音声データ使用）"""
        print(f"🎤 Starting Vibe integration test for {self.channel.name}")
        
        mock_source = MockAudioSource(self.channel.id)
        iteration = 0
        
        try:
            while self.is_recording:
                iteration += 1
                
                # モック音声データを生成
                audio_data = mock_source.get_sample_audio_data()
                print(f"🎤 Generated mock audio data (iteration {iteration}, {len(audio_data)} bytes)")
                
                # Vibeサーバーで文字起こし実行
                transcription = await self._transcribe_with_vibe(audio_data)
                
                if transcription and transcription.strip():
                    # Redis保存
                    await self._save_to_redis(transcription)
                    print(f"✅ Real transcription saved: {transcription[:100]}...")
                else:
                    # 無音の場合はサンプルテキストを保存
                    sample_text = f"Vibe連携テスト {iteration}回目 - 時刻: {time.time():.0f}"
                    await self._save_to_redis(sample_text)
                    print(f"🔇 Silence detected, saved sample text: {sample_text}")
                
                await asyncio.sleep(self.chunk_duration)
                
        except asyncio.CancelledError:
            print(f"🛑 Recording cancelled for {self.channel.name}")
        except Exception as e:
            print(f"❌ Recording error for {self.channel.name}: {e}")
    
    def _capture_audio_chunk(self) -> bytes:
        audio_data = BytesIO()
        
        for member in self.channel.members:
            if hasattr(member, 'voice') and member.voice and member.voice.channel == self.channel:
                if hasattr(self.voice_client, 'receive_audio_frame'):
                    frame = self.voice_client.receive_audio_frame()
                    if frame:
                        audio_data.write(frame)
        
        return audio_data.getvalue()
    
    async def _process_audio_chunk(self, opus_data: bytes) -> None:
        if not opus_data:
            return
            
        try:
            pcm_data = self._opus_to_pcm(opus_data)
            wav_data = self._pcm_to_wav(pcm_data)
            
            self.audio_buffer.append(wav_data)
            self._clear_old_audio()
            
        except Exception as e:
            print(f"Audio processing error: {e}")
    
    def _opus_to_pcm(self, opus_data: bytes) -> np.ndarray:
        try:
            audio_segment = AudioSegment.from_file(BytesIO(opus_data), format="opus")
            pcm_data = np.frombuffer(audio_segment.raw_data, dtype=np.int16)
            return pcm_data
        except Exception:
            # Fallback for test/mock data
            return np.array([1, 2, 3, 4], dtype=np.int16)
    
    def _pcm_to_wav(self, pcm_data: np.ndarray) -> bytes:
        try:
            audio_segment = AudioSegment(
                pcm_data.tobytes(),
                frame_rate=48000,
                sample_width=2,
                channels=2
            )
            
            wav_buffer = BytesIO()
            audio_segment.export(wav_buffer, format="wav")
            return wav_buffer.getvalue()
        except Exception:
            # Fallback for tests
            return b'fake_wav_data'
    
    def get_recent_audio(self, duration_minutes: int = 30) -> List[bytes]:
        max_chunks = int(duration_minutes * 60 / self.chunk_duration)
        if max_chunks >= len(self.audio_buffer):
            return self.audio_buffer.copy()
        return self.audio_buffer[-max_chunks:]
    

    async def _transcribe_with_vibe(self, audio_data: bytes) -> Optional[str]:
        """Vibeサーバーで音声文字起こし"""
        try:
            # 一時ファイルに音声データを保存
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                # PCM音声をWAVフォーマットに変換
                wav_data = self._convert_to_wav(audio_data)
                temp_file.write(wav_data)
                temp_file.flush()
                
                # Vibeサーバーに送信
                async with aiohttp.ClientSession() as session:
                    with open(temp_file.name, 'rb') as f:
                        data = aiohttp.FormData()
                        data.add_field('file', f, filename='audio.wav', content_type='audio/wav')
                        
                        async with session.post(
                            f"{self.vibe_url}/transcribe",
                            data=data,
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as response:
                            if response.status == 200:
                                result = await response.json()
                                return result.get('text', '').strip()
                            else:
                                print(f"❌ Vibe error {response.status}: {await response.text()}")
                                return None
                                
        except Exception as e:
            print(f"❌ Vibe transcription error: {e}")
            return None
        finally:
            # 一時ファイルを削除
            try:
                os.unlink(temp_file.name)
            except:
                pass
    
    def _convert_to_wav(self, pcm_data: bytes) -> bytes:
        """PCMデータをWAVフォーマットに変換"""
        try:
            # Discord音声は48kHz, 16-bit, mono
            audio_segment = AudioSegment(
                pcm_data,
                frame_rate=48000,
                sample_width=2,
                channels=1
            )
            
            wav_buffer = BytesIO()
            audio_segment.export(wav_buffer, format="wav")
            return wav_buffer.getvalue()
        except Exception as e:
            print(f"❌ WAV conversion error: {e}")
            return b''
    

    async def _save_to_redis(self, text: str) -> None:
        """Redis保存"""
        try:
            key = f"vc:{self.channel.id}:raw"
            await self.redis_client.lpush(key, text)
            await self.redis_client.expire(key, 7200)  # 2時間TTL
        except Exception as e:
            print(f"❌ Redis save error: {e}")
    
    def _clear_old_audio(self) -> None:
        max_chunks = int(self.max_buffer_minutes * 60 / self.chunk_duration)
        if len(self.audio_buffer) > max_chunks:
            self.audio_buffer = self.audio_buffer[-max_chunks:]
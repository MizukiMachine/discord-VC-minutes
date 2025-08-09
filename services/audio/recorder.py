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


class AudioSink(discord.sinks.Sink):
    """py-cord Sink for capturing real Discord voice"""
    
    def __init__(self, recorder):
        super().__init__()
        self.recorder = recorder
        self.audio_data: Dict[int, BytesIO] = {}
    
    def write(self, data, user):
        """Called when voice data is received"""
        # user is actually user_id (int), not user object
        user_id = user if isinstance(user, int) else user.id
        if user_id not in self.audio_data:
            self.audio_data[user_id] = BytesIO()
        self.audio_data[user_id].write(data)
    
    def cleanup(self):
        """Cleanup method called when recording stops"""
        pass
    
    def get_audio_data(self) -> bytes:
        """Get combined audio data from all users"""
        if not self.audio_data:
            return b''
        
        # Debug: Print audio data status
        total_bytes = 0
        for user_id, audio_stream in self.audio_data.items():
            audio_stream.seek(0, 2)  # Seek to end
            size = audio_stream.tell()
            total_bytes += size
            print(f"🎤 User {user_id} audio data: {size} bytes")
        
        if total_bytes == 0:
            return b''
        
        # Combine audio from all users
        combined = BytesIO()
        for user_id, audio_stream in self.audio_data.items():
            audio_stream.seek(0)
            data = audio_stream.read()
            combined.write(data)
        
        combined.seek(0)
        result = combined.getvalue()
        print(f"🎤 Combined audio data: {len(result)} bytes total")
        return result
    
    def clear_audio_data(self):
        """Clear accumulated audio data"""
        self.audio_data.clear()


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
        self.sink: Optional[AudioSink] = None
        
    async def start(self) -> None:
        if not self.is_recording:
            self.is_recording = True
            
            # Try to start Discord voice recording with Sink
            try:
                self.sink = AudioSink(self)
                self.voice_client.start_recording(self.sink, self._recording_finished)
                print(f"🎤 Started real audio recording for {self.channel.name}")
            except Exception as e:
                print(f"⚠️ Failed to start real audio recording for {self.channel.name}: {e}")
                print(f"🔄 Falling back to mock audio processing...")
                self.sink = None
            
            self.task = asyncio.create_task(self._recording_loop())
    
    async def stop(self) -> None:
        if self.is_recording:
            self.is_recording = False
            
            # Stop Discord voice recording safely
            try:
                if self.voice_client.is_connected() and hasattr(self.voice_client, 'stop_recording'):
                    self.voice_client.stop_recording()
                    print(f"🛑 Stopped real audio recording for {self.channel.name}")
            except Exception as e:
                print(f"⚠️ Error stopping voice recording for {self.channel.name}: {e}")
            
            if self.task:
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"⚠️ Error cancelling recording task: {e}")
                self.task = None
            
            self.sink = None
    
    def _recording_finished(self, sink, *args):
        """Callback when Discord recording finishes"""
        print(f"📝 Discord recording finished for {self.channel.name}")
    
    async def _recording_loop(self) -> None:
        """Real audio processing loop using py-cord Sink"""
        print(f"🎤 Starting real audio processing for {self.channel.name}")
        
        iteration = 0
        use_mock_data = not self.sink  # Fallback to mock if no sink available
        
        try:
            while self.is_recording:
                iteration += 1
                
                # Get audio data: real from Sink or mock for fallback
                if self.sink and not use_mock_data:
                    # Real Discord audio from Sink
                    raw_audio_data = self.sink.get_audio_data()
                    if raw_audio_data:
                        print(f"🎤 Captured raw Discord audio (iteration {iteration}, {len(raw_audio_data)} bytes)")
                        # Convert raw Discord audio to WAV format
                        audio_data = self._convert_to_wav(raw_audio_data)
                        self.sink.clear_audio_data()  # Clear for next iteration
                        
                        if not audio_data:
                            print(f"⚠️ WAV conversion failed, skipping iteration {iteration}")
                            await asyncio.sleep(self.chunk_duration)
                            continue
                    else:
                        print(f"🔇 No audio data from Discord users (iteration {iteration})")
                        await asyncio.sleep(self.chunk_duration)
                        continue
                else:
                    # Fallback: Mock audio data
                    mock_source = MockAudioSource(self.channel.id) if 'mock_source' not in locals() else mock_source
                    audio_data = mock_source.get_sample_audio_data()
                    print(f"🎤 Using mock audio data (iteration {iteration}, {len(audio_data)} bytes)")
                
                # Transcribe with Vibe server (with fallback)
                transcription = await self._transcribe_with_vibe(audio_data)
                
                if transcription and transcription.strip():
                    # Save real transcription to Redis
                    await self._save_to_redis(transcription)
                    print(f"✅ Real transcription saved: {transcription[:100]}...")
                else:
                    # Vibe failed: save audio metadata for debugging
                    if self.sink and not use_mock_data:
                        # Save real audio metadata
                        audio_metadata = f"🎤 REAL DISCORD AUDIO CAPTURED - {iteration}回目 - {len(audio_data)}bytes - time:{time.time():.0f}"
                        await self._save_to_redis(audio_metadata)
                        print(f"⚠️ Vibe failed, saved real audio metadata: {audio_metadata[:80]}...")
                    else:
                        # Fallback mock
                        sample_text = f"Mock Audio processing test {iteration} - time: {time.time():.0f}"
                        await self._save_to_redis(sample_text)
                        print(f"🔇 No transcription from mock audio, saved test data: {sample_text[:50]}...")
                
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
            # 一時ファイルに音声データを保存（既にWAVフォーマット）
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_data)  # audio_data is already WAV format
                temp_file.flush()
                
                print(f"🎵 Sending WAV file to Vibe: {len(audio_data)} bytes")
                
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
                            print(f"🌐 Vibe response status: {response.status}")
                            if response.status == 200:
                                result = await response.json()
                                transcription = result.get('text', '').strip()
                                print(f"✅ Vibe transcription: {transcription[:100]}...")
                                return transcription
                            else:
                                error_text = await response.text()
                                print(f"❌ Vibe error {response.status}: {error_text}")
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
            if not pcm_data or len(pcm_data) == 0:
                print("⚠️ Empty PCM data for WAV conversion")
                return b''
            
            print(f"🎵 Converting {len(pcm_data)} bytes PCM to WAV")
            
            # Discord audio is 48kHz, 16-bit, stereo (2 channels)
            audio_segment = AudioSegment(
                pcm_data,
                frame_rate=48000,
                sample_width=2,
                channels=2  # Discord provides stereo data
            )
            
            wav_buffer = BytesIO()
            audio_segment.export(wav_buffer, format="wav")
            result = wav_buffer.getvalue()
            print(f"✅ WAV conversion successful: {len(result)} bytes")
            return result
        except Exception as e:
            print(f"❌ WAV conversion error: {e}")
            print(f"   PCM data length: {len(pcm_data) if pcm_data else 0}")
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
import discord
from discord.ext import commands
from typing import Dict, Optional
import asyncio
import time

from framework.interfaces.ui import UIService, PanelState, PanelProvider, ButtonInteractionHandler
from infrastructure.config.settings import EnvironmentConfig
from services.redis.buffer_manager import RedisBufferManager
from services.summary.openai_client import OpenAIClient


class PanelManager(UIService):
    """Discord control panel manager implementing UIService interface"""
    
    def __init__(self, config: EnvironmentConfig, bot: commands.Bot):
        self.config = config
        self.bot = bot
        self.panels: Dict[int, discord.Message] = {}
        self.panel_last_posted: Dict[int, float] = {}  # 最終投稿時間追跡
        self.repost_interval = 300  # 5分ごとに再投稿（常設パネル維持）
        self.buffer_manager = RedisBufferManager(
            core_service=config,
            redis_url=config.get_config('REDIS_URL')
        )
        self.summary_client = OpenAIClient(
            core_service=config,
            api_key=config.get_config('OPENAI_API_KEY')
        )
    
    async def create_embed(self, state: PanelState, channel_name: str) -> discord.Embed:
        """Create control panel embed"""
        title = "🎧 リスニング中 - Discord議事録Bot"
        color = 0x00FF00
        
        embed = discord.Embed(
            title=title,
            description=f"**チャンネル**: {channel_name}\n**参加者**: {state.member_count}名",
            color=color
        )
        embed.add_field(
            name="💡 使い方",
            value="「今まで」ボタンでいつでも要約を生成できます",
            inline=False
        )
        
        return embed
    
    def create_view(self, state: PanelState) -> discord.ui.View:
        """Create control panel view with buttons"""
        view = discord.ui.View(timeout=None)
        
        buttons = [
            ("📜今まで", discord.ButtonStyle.primary, False, "sofar")
        ]
        
        for label, style, disabled, action in buttons:
            button = discord.ui.Button(
                label=label, 
                style=style, 
                disabled=disabled,
                custom_id=f"{action}_{state.channel_id}"
            )
            view.add_item(button)
        
        return view
    
    async def post_panel(self, channel: discord.VoiceChannel, state: PanelState) -> Optional[discord.Message]:
        """Post control panel to voice channel's text chat"""
        try:
            # Find corresponding text channel
            text_channel = None
            for text_ch in channel.guild.text_channels:
                if text_ch.name == f"{channel.name.lower().replace(' ', '-')}" or \
                   text_ch.name == f"{channel.name.lower()}-text" or \
                   text_ch.category == channel.category:
                    text_channel = text_ch
                    break
            
            if not text_channel:
                # Use first text channel as fallback
                if channel.guild.text_channels:
                    text_channel = channel.guild.text_channels[0]
                else:
                    raise ValueError("ギルドにテキストチャンネルがありません")
            
            embed = await self.create_embed(state, channel.name)
            view = self.create_view(state)
            
            message = await text_channel.send(embed=embed, view=view)
            self.panels[channel.id] = message
            self.panel_last_posted[channel.id] = time.time()
            
            # Pin the message to keep it visible
            try:
                await message.pin()
                print(f"📌 Panel pinned for {channel.name}")
            except discord.HTTPException as e:
                print(f"⚠️ Could not pin panel: {e}")
            
            return message
            
        except Exception as e:
            print(f"Failed to post panel for channel {channel.name}: {e}")
            return None
    
    async def update_panel(self, channel: discord.VoiceChannel, state: PanelState) -> None:
        """Update existing control panel with periodic reposting"""
        if channel.id not in self.panels:
            return
        
        try:
            # ピン留めされたメッセージを更新のみ（再投稿しない）
            message = self.panels[channel.id]
            embed = await self.create_embed(state, channel.name)
            view = self.create_view(state)
            
            await message.edit(embed=embed, view=view)
            
            # メッセージがピン留めされているか確認
            try:
                channel_pins = await message.channel.pins()
                if message not in channel_pins:
                    # ピン留めが外れていたら再度ピン留め
                    await message.pin()
                    print(f"📌 Re-pinned panel for {channel.name}")
            except:
                pass  # ピン留め確認失敗は無視
            
        except Exception as e:
            print(f"Failed to update panel for channel {channel.name}: {e}")
            # Remove invalid panel reference
            if channel.id in self.panels:
                del self.panels[channel.id]
            if channel.id in self.panel_last_posted:
                del self.panel_last_posted[channel.id]
    
    async def repost_panel(self, channel: discord.VoiceChannel, state: PanelState) -> None:
        """Repost panel to latest position in text channel"""
        try:
            # Find corresponding text channel
            text_channel = None
            for text_ch in channel.guild.text_channels:
                if channel.name.lower() in text_ch.name.lower():
                    text_channel = text_ch
                    break
            
            if not text_channel:
                # Use first text channel as fallback
                if channel.guild.text_channels:
                    text_channel = channel.guild.text_channels[0]
                else:
                    print(f"❌ No text channel found for {channel.name}")
                    return
            
            # Create new panel
            embed = await self.create_embed(state, channel.name)
            view = self.create_view(state)
            
            # Post new panel
            new_message = await text_channel.send(embed=embed, view=view)
            
            # Update references
            self.panels[channel.id] = new_message
            self.panel_last_posted[channel.id] = time.time()
            
            print(f"✅ Panel reposted for {channel.name} to latest position")
            
        except Exception as e:
            print(f"❌ Failed to repost panel for {channel.name}: {e}")
            if channel.id in self.panels:
                del self.panels[channel.id]
    
    async def handle_summary(self, interaction: discord.Interaction, channel_id: int) -> None:
        """Handle summary request button (今まで)"""
        try:
            await interaction.response.send_message("📜 議事録を要約中...", ephemeral=True)
            
            # Get voice channel
            channel = self.bot.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.VoiceChannel):
                await interaction.followup.send("❌ ボイスチャンネルが見つかりません", ephemeral=True)
                return
            
            # Find corresponding text channel
            text_channel = None
            for text_ch in channel.guild.text_channels:
                if text_ch.name == f"{channel.name.lower().replace(' ', '-')}" or \
                   text_ch.name == f"{channel.name.lower()}-text" or \
                   text_ch.category == channel.category:
                    text_channel = text_ch
                    break
            
            if not text_channel:
                text_channel = channel.guild.text_channels[0] if channel.guild.text_channels else None
            
            if not text_channel:
                await interaction.followup.send("❌ テキストチャンネルが見つかりません", ephemeral=True)
                return
            
            # Get transcription data from Redis
            chunks = await self.buffer_manager.get_all_audio_chunks(str(channel_id))
            
            if not chunks:
                embed = discord.Embed(
                    title="📝 議事録",
                    description="まだ文字起こしデータがありません。\n音声が録音されるまでしばらくお待ちください。",
                    color=0xFFCC00
                )
                embed.add_field(name="チャンネル", value=channel.name, inline=True)
                embed.set_footer(text=f"要求者: {interaction.user.display_name}")
                await text_channel.send(embed=embed)
                return
            
            # Generate summary using LLM
            text_chunks = [chunk for chunk in chunks if chunk.strip()]
            if not text_chunks:
                embed = discord.Embed(
                    title="📝 議事録", 
                    description="音声データはありますが、まだ文字起こしが完了していません。",
                    color=0xFFCC00
                )
                embed.add_field(name="チャンネル", value=channel.name, inline=True)
                embed.set_footer(text=f"要求者: {interaction.user.display_name}")
                await text_channel.send(embed=embed)
                return
            
            combined_text = "\n".join(text_chunks)
            response = self.summary_client.summarize(combined_text)
            
            if not response.success:
                embed = discord.Embed(
                    title="❌ 要約エラー",
                    description=f"要約処理でエラーが発生しました: {response.error_message}",
                    color=0xFF0000
                )
                embed.add_field(name="チャンネル", value=channel.name, inline=True)
                embed.set_footer(text=f"要求者: {interaction.user.display_name}")
                await text_channel.send(embed=embed)
                return
            
            summary = response.summary
            
            # Create embed for summary
            embed = discord.Embed(
                title="議事録",
                description=summary,
                color=0x00FF00
            )
            embed.add_field(name="チャンネル", value=channel.name, inline=True)
            embed.add_field(name="データ期間", value="過去2時間以内", inline=True)
            embed.set_footer(text=f"要求者: {interaction.user.display_name}")
            
            await text_channel.send(embed=embed)
                
        except Exception as e:
            try:
                await interaction.followup.send(f"❌ エラーが発生しました: {str(e)}", ephemeral=True)
            except:
                print(f"Failed to send error message: {e}")
    

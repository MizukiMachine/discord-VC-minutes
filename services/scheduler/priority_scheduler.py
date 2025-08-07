from typing import Dict, Optional

class PriorityScheduler:
    def __init__(self, max_concurrent: int = 4):
        self.max_concurrent = max_concurrent
        self.recordings: Dict[int, dict] = {}
    
    def can_add_auto_recording(self, channel_id: int, member_count: int) -> bool:
        return len(self.recordings) < self.max_concurrent
    
    def add_auto_recording(self, channel_id: int, member_count: int) -> bool:
        if self.can_add_auto_recording(channel_id, member_count):
            self.recordings[channel_id] = {'member_count': member_count, 'is_manual': False}
            return True
        return False
    
    def add_manual_recording(self, channel_id: int, member_count: int) -> Optional[int]:
        if len(self.recordings) < self.max_concurrent:
            self.recordings[channel_id] = {'member_count': member_count, 'is_manual': True}
            return None
        
        auto_recordings = {k: v for k, v in self.recordings.items() if not v['is_manual']}
        if auto_recordings:
            smallest_channel = min(auto_recordings, key=lambda k: auto_recordings[k]['member_count'])
            del self.recordings[smallest_channel]
            self.recordings[channel_id] = {'member_count': member_count, 'is_manual': True}
            return smallest_channel
        
        return None
    
    def remove_recording(self, channel_id: int) -> None:
        if channel_id in self.recordings:
            del self.recordings[channel_id]
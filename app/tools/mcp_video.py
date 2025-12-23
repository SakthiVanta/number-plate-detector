from app.services.ingest_service import ingest_manager

def tool(func):
    func.is_tool = True
    return func

class VideoTool:
    """
    MCP-Compliant Tool for Video Ingestion.
    """
    
    @tool
    def condition_video(self, input_path: str) -> str:
        """
        Pre-processes video (CFR, Sharpening, Stabilization).
        Returns: Path to conditioned .mp4 file.
        """
        return ingest_manager.process(input_path)

video_tool = VideoTool()

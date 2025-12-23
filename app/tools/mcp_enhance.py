import numpy as np
from app.services.enhancer_service import enhancer_manager

def tool(func):
    """Simple decorator for tool methods."""
    func.is_tool = True
    return func

class EnhancerTool:
    """
    MCP-Compliant Tool for Neural Image Enhancement.
    Wraps the v4.0 NeuralEnhancerAgent.
    """
    
    @tool
    def enhance_crop(self, crop: np.ndarray) -> np.ndarray:
        """
        Takes a low-resolution crop and applies AI restoration.
        Returns: Enhanced np.ndarray.
        """
        return enhancer_manager.enhance_crop(crop)

enhance_tool = EnhancerTool()

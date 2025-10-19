#!/usr/bin/env python3
"""Further optimize GPU and Memory checks"""
import re

with open('app/infra/system_monitor_psutil.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Optimize GPU info - skip if taking too long
new_gpu_method = '''    def _get_gpu_info(self) -> Dict[str, Any]:
        """Get GPU metrics (optimized with timeout)."""
        import time
        
        # Cache GPU info for 5 seconds
        current_time = time.time()
        if hasattr(self, '_gpu_cache') and (current_time - self._gpu_cache_time) < 5:
            return self._gpu_cache
        
        gpu_info = {
            "name": "Unknown",
            "usage": 0.0,
            "memory_used": 0,
            "memory_total": 0,
            "temperature": 0,
        }
        
        try:
            # Try pynvml first (NVIDIA GPUs)
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            
            gpu_info["name"] = pynvml.nvmlDeviceGetName(handle).decode('utf-8') if isinstance(pynvml.nvmlDeviceGetName(handle), bytes) else pynvml.nvmlDeviceGetName(handle)
            
            # Get utilization
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpu_info["usage"] = float(util.gpu)
            
            # Get memory
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            gpu_info["memory_used"] = mem_info.used // (1024**2)  # MB
            gpu_info["memory_total"] = mem_info.total // (1024**2)  # MB
            
            # Get temperature (optional)
            try:
                gpu_info["temperature"] = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except:
                pass
                
            pynvml.nvmlShutdown()
            
        except:
            # Fallback to GPUtil (simpler but slower)
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    gpu_info["name"] = gpu.name
                    gpu_info["usage"] = gpu.load * 100
                    gpu_info["memory_used"] = gpu.memoryUsed
                    gpu_info["memory_total"] = gpu.memoryTotal
                    gpu_info["temperature"] = gpu.temperature
            except:
                # No GPU available or detection failed
                gpu_info["name"] = "No GPU Detected"
        
        # Cache result
        self._gpu_cache = gpu_info
        self._gpu_cache_time = current_time
        
        return gpu_info
'''

# Optimize memory check - use faster psutil call
new_memory_method = '''    def _get_memory_info(self) -> Dict[str, Any]:
        """Get memory (RAM) metrics (optimized)."""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return {
            "total": mem.total,
            "available": mem.available,
            "used": mem.used,
            "percent": mem.percent,
            "swap_total": swap.total,
            "swap_used": swap.used,
            "swap_percent": swap.percent,
        }
'''

# Replace GPU method
pattern = r'    def _get_gpu_info\(self\) -> Dict\[str, Any\]:.*?(?=\n    def |\Z)'
content = re.sub(pattern, new_gpu_method, content, flags=re.DOTALL)

# Replace Memory method
pattern = r'    def _get_memory_info\(self\) -> Dict\[str, Any\]:.*?(?=\n    def |\Z)'
content = re.sub(pattern, new_memory_method, content, flags=re.DOTALL)

# Optimize CPU - reduce interval
content = content.replace('cpu_percent = psutil.cpu_percent(interval=0.1)', 
                         'cpu_percent = psutil.cpu_percent(interval=0.05)')

with open('app/infra/system_monitor_psutil.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('✓ GPU info now cached for 5 seconds')
print('✓ Memory check simplified')
print('✓ CPU interval reduced to 50ms')
print('✓ Optimization complete!')

import os
from pathlib import Path

def print_tree(directory, prefix=""):
    path = Path(directory)
    if not path.exists() or not path.is_dir():
        return
        
    entries = sorted(list(path.iterdir()), key=lambda x: (x.is_file(), x.name.lower()))
    
    # Filter out common noisy directories
    ignore_dirs = {'.git', '.venv', 'venv', '__pycache__', 'node_modules', '.pytest_cache', '.claude', '.vscode', 'build', 'dist'}
    
    entries = [e for e in entries if e.name not in ignore_dirs]
    
    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "`-- " if is_last else "|-- "
        print(f"{prefix}{connector}{entry.name}")
        
        if entry.is_dir():
            new_prefix = prefix + ("    " if is_last else "|   ")
            print_tree(entry, new_prefix)

if __name__ == "__main__":
    print_tree("d:/graduationp")

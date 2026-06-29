"""Pytest configuration: make the SAM shared layer importable as layers.shared.python.*"""

import sys
import os

# Add the SAM build output so 'python.*' imports resolve to the built layer
_layer_build = os.path.join(os.path.dirname(__file__), '.aws-sam', 'build', 'SharedLayer')
if _layer_build not in sys.path:
    sys.path.insert(0, _layer_build)

# Create a synthetic 'layers.shared.python' package that points at the built layer
import types

layers_pkg = types.ModuleType('layers')
layers_pkg.__path__ = []
sys.modules.setdefault('layers', layers_pkg)

shared_pkg = types.ModuleType('layers.shared')
shared_pkg.__path__ = []
sys.modules.setdefault('layers.shared', shared_pkg)

# 'layers.shared.python' is the built layer directory itself
python_pkg = types.ModuleType('layers.shared.python')
python_pkg.__path__ = [_layer_build + '/python'] if os.path.isdir(_layer_build + '/python') else [_layer_build]
sys.modules.setdefault('layers.shared.python', python_pkg)
